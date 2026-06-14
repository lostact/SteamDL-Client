"""Asyncio-based transparent HTTP proxy.

Accepts TCP connections on the phantom IP on two ports:

  Port 80  — reads HTTP request headers, modifies them (Host → cache_domain,
              adds Real-Host and Auth-Token headers), then relays the
              connection bidirectionally to the cache server.  Handles
              HTTP/1.1 keep-alive by looping over all requests in a
              connection, modifying headers on every one.

  Port 443 — raw TCP passthrough to cache_ip:443 (no header modification).

All bulk download data flows through the kernel's native TCP stack with
zero per-packet user-space overhead — only the HTTP request headers of
each request are processed in Python.
"""
import asyncio
import logging
import os
from time import time

logger = logging.getLogger(__name__)

# Chunk size for bidirectional relay — 256 KiB for high-throughput relay
# (fewer syscalls at 1 Gbit/s; ~500 reads/sec at 125 MB/s)
RELAY_CHUNK_SIZE = 262144

# Maximum request header block size before the connection is dropped
_MAX_HEADER_SIZE = 65536   # 64 KB

# Seconds to wait for a complete HTTP request header block
_HEADER_TIMEOUT = 30.0


class TransparentProxy:
    """Asyncio transparent HTTP proxy.

    Listens on listen_ip:80 for HTTP (with header modification) and on
    listen_ip:443 for raw TCP passthrough to the cache server.

    Args:
        listen_ip:    IP address to bind to (phantom IP).
        cache_ip:     Cache server IP address to forward requests to.
        cache_domain: Cache server domain to set as Host header.
        token:        Authentication token to add as Auth-Token header.
        debug:        If True, log every intercepted HTTP request and
                      TLS connection at INFO level.
    """

    def __init__(self, listen_ip, cache_ip, cache_domain, token, debug=False):
        self.listen_ip = listen_ip
        self.cache_ip = cache_ip
        self.cache_domain = cache_domain
        self.token = token
        self.debug = debug
        self.total_rx = 0
        self._server_80 = None
        self._server_443 = None
        self._last_rx_write_time = 0
        # Restore previous usage counter if it exists
        try:
            if os.path.isfile("rx.txt"):
                with open("rx.txt", "r") as rx_file:
                    self.total_rx = int(rx_file.read().strip())
        except Exception:
            pass

    async def start(self):
        """Start both proxy servers. Runs until cancelled."""
        self._server_80 = await asyncio.start_server(
            self._handle_client, self.listen_ip, 80
        )
        self._server_443 = await asyncio.start_server(
            self._handle_tls_passthrough, self.listen_ip, 443
        )
        addr_80 = self._server_80.sockets[0].getsockname()
        addr_443 = self._server_443.sockets[0].getsockname()
        logger.info(f"HTTP proxy listening on {addr_80[0]}:{addr_80[1]}")
        logger.info(f"TLS passthrough listening on {addr_443[0]}:{addr_443[1]}")
        async with self._server_80, self._server_443:
            await asyncio.gather(
                self._server_80.serve_forever(),
                self._server_443.serve_forever(),
            )

    def stop(self):
        """Stop both proxy servers."""
        if self._server_80:
            self._server_80.close()
        if self._server_443:
            self._server_443.close()
        logger.info("Transparent proxy stopped")

    # ------------------------------------------------------------------
    # Port 80 — HTTP with header modification
    # ------------------------------------------------------------------

    async def _handle_client(self, client_reader, client_writer):
        """Handle a single HTTP client connection.

        Opens one upstream connection and loops over all HTTP requests
        on the keep-alive connection, modifying headers on every request.
        When either direction closes, the other is cancelled.
        """
        try:
            try:
                upstream_reader, upstream_writer = await asyncio.wait_for(
                    asyncio.open_connection(self.cache_ip, 80),
                    timeout=10,
                )
            except Exception as e:
                logger.debug(f"Failed to connect to upstream {self.cache_ip}:80: {e}")
                client_writer.close()
                return

            request_task = asyncio.ensure_future(
                self._request_loop(client_reader, upstream_writer)
            )
            relay_task = asyncio.ensure_future(
                self._relay(upstream_reader, client_writer, count_rx=True)
            )

            done, pending = await asyncio.wait(
                {request_task, relay_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            for task in done:
                if not task.cancelled():
                    exc = task.exception()
                    if exc and not isinstance(
                        exc, (ConnectionResetError, BrokenPipeError, OSError)
                    ):
                        logger.debug(f"Handler task error: {exc}")

            self._write_rx_file()

        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.debug(f"Client connection error: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Unexpected error handling client: {e}")
        finally:
            try:
                client_writer.close()
            except Exception:
                pass

    async def _request_loop(self, client_reader, upstream_writer):
        """Read HTTP requests one by one, modify headers, forward to upstream.

        Handles HTTP/1.1 keep-alive: loops until the client closes the
        connection or signals Connection: close.
        """
        try:
            while True:
                buf = await self._read_request_headers(client_reader)
                if buf is None:
                    break

                header_end = buf.index(b"\r\n\r\n") + 4
                headers_raw = buf[:header_end]
                body_start = buf[header_end:]  # bytes overshot beyond \r\n\r\n

                if self.debug:
                    self._log_request(headers_raw)

                modified_headers = self._modify_headers(headers_raw)
                upstream_writer.write(modified_headers)
                await upstream_writer.drain()

                keep_alive = await self._forward_request_body(
                    headers_raw, body_start, client_reader, upstream_writer
                )
                if not keep_alive:
                    break

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        except asyncio.CancelledError:
            raise
        finally:
            try:
                upstream_writer.close()
            except Exception:
                pass

    async def _read_request_headers(self, reader):
        """Read HTTP request headers until \\r\\n\\r\\n.

        Enforces a maximum size (_MAX_HEADER_SIZE) and a total timeout
        (_HEADER_TIMEOUT).  Returns the raw bytes buffer (which may include
        a few bytes of the body if the client sent them in the same TCP
        segment), or None on EOF, timeout, or size-limit violation.
        """
        async def _inner():
            buf = b""
            while b"\r\n\r\n" not in buf:
                if len(buf) >= _MAX_HEADER_SIZE:
                    logger.debug("Request headers exceed size limit, closing connection")
                    return None
                chunk = await reader.read(4096)
                if not chunk:
                    return None
                buf += chunk
            return buf

        try:
            return await asyncio.wait_for(_inner(), timeout=_HEADER_TIMEOUT)
        except asyncio.TimeoutError:
            logger.debug("Timeout reading request headers")
            return None

    async def _forward_request_body(self, headers_raw, body_start, reader, writer):
        """Forward any remaining request body bytes to upstream.

        Args:
            headers_raw: Raw HTTP request header block (ends at \\r\\n\\r\\n).
            body_start:  Body bytes already read (overshoot from header read),
                         not yet written to upstream.
            reader:      client_reader.
            writer:      upstream_writer.

        Returns:
            True if the connection should remain alive, False if it should close.
        """
        text = headers_raw.decode("utf-8", errors="replace")
        lines = text.split("\r\n")

        keep_alive = True
        is_chunked = False
        content_length = 0

        for line in lines[1:]:
            ll = line.lower()
            if ll == "connection: close":
                keep_alive = False
            elif ll.startswith("transfer-encoding:") and "chunked" in ll:
                is_chunked = True
            elif ll.startswith("content-length:"):
                try:
                    content_length = int(ll.split(":", 1)[1].strip())
                except ValueError:
                    pass

        try:
            if is_chunked:
                await self._forward_chunked_body(body_start, reader, writer)
            elif content_length > 0:
                # Forward body_start, then read exactly the remaining bytes
                remaining = content_length
                if body_start:
                    writer.write(body_start)
                    await writer.drain()
                    remaining -= len(body_start)
                while remaining > 0:
                    chunk = await reader.read(min(remaining, RELAY_CHUNK_SIZE))
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
                    remaining -= len(chunk)
            elif body_start:
                # No framing headers but we have buffered bytes — forward them
                writer.write(body_start)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

        return keep_alive

    async def _forward_chunked_body(self, body_start, reader, writer):
        """Forward a chunked-encoded request body.

        Args:
            body_start: Bytes already read beyond the header block.
            reader:     client_reader.
            writer:     upstream_writer.
        """
        buf = body_start
        try:
            while True:
                # Accumulate until we have a complete chunk-size line
                while b"\r\n" not in buf:
                    data = await reader.read(4096)
                    if not data:
                        if buf:
                            writer.write(buf)
                            await writer.drain()
                        return
                    buf += data

                crlf_idx = buf.index(b"\r\n")
                size_line = buf[:crlf_idx]
                buf = buf[crlf_idx + 2:]

                try:
                    chunk_size = int(size_line.split(b";")[0].strip(), 16)
                except ValueError:
                    # Malformed chunk — forward what we have and give up
                    writer.write(size_line + b"\r\n" + buf)
                    await writer.drain()
                    return

                writer.write(size_line + b"\r\n")

                if chunk_size == 0:
                    # Terminal chunk — forward any trailer and final CRLF
                    writer.write(buf)
                    await writer.drain()
                    return

                # Read chunk_size data bytes + the trailing \r\n (chunk_size + 2)
                need = chunk_size + 2
                while len(buf) < need:
                    data = await reader.read(need - len(buf))
                    if not data:
                        writer.write(buf)
                        await writer.drain()
                        return
                    buf += data

                writer.write(buf[:need])
                await writer.drain()
                buf = buf[need:]

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

    # ------------------------------------------------------------------
    # Port 443 — raw TCP passthrough
    # ------------------------------------------------------------------

    async def _handle_tls_passthrough(self, client_reader, client_writer):
        """Raw TCP passthrough: phantom_ip:443 → cache_ip:443.

        No header inspection or modification — bytes are relayed as-is.
        """
        if self.debug:
            peer = client_writer.get_extra_info("peername")
            logger.info(f"[DEBUG] TLS passthrough: {peer[0]}:{peer[1]} -> {self.cache_ip}:443")
        try:
            try:
                upstream_reader, upstream_writer = await asyncio.wait_for(
                    asyncio.open_connection(self.cache_ip, 443),
                    timeout=10,
                )
            except Exception as e:
                logger.debug(f"Failed to connect to upstream {self.cache_ip}:443: {e}")
                client_writer.close()
                return

            relay_down = asyncio.ensure_future(
                self._relay(client_reader, upstream_writer)
            )
            relay_up = asyncio.ensure_future(
                self._relay(upstream_reader, client_writer, count_rx=True)
            )

            done, pending = await asyncio.wait(
                {relay_down, relay_up},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            self._write_rx_file()

        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.debug(f"TLS passthrough error: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Unexpected TLS passthrough error: {e}")
        finally:
            try:
                client_writer.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    async def _relay(self, reader, writer, count_rx=False):
        """Relay data from reader to writer.

        Args:
            reader:   asyncio.StreamReader to read from.
            writer:   asyncio.StreamWriter to write to.
            count_rx: If True, increment self.total_rx on each chunk
                      for live traffic accounting (Option 1).
        """
        try:
            while True:
                data = await reader.read(RELAY_CHUNK_SIZE)
                if not data:
                    break
                if count_rx:
                    # Commit to the shared counter immediately so live
                    # speed readings are correct (GIL makes += atomic).
                    self.total_rx += len(data)
                    self._write_rx_file()
                writer.write(data)
                # Only drain when the write buffer is large, not every chunk,
                # to avoid a ping-pong stall at high throughput.
                if writer.transport.get_write_buffer_size() > RELAY_CHUNK_SIZE:
                    await writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        except asyncio.CancelledError:
            raise
        finally:
            try:
                writer.close()
            except Exception:
                pass

    def _modify_headers(self, headers_raw):
        """Parse and modify HTTP request headers.

        - Replaces the Host header with cache_domain.
        - Adds Host: cache_domain if no Host header was present.
        - Adds Real-Host preserving the original Host value.
        - Adds Auth-Token.

        Args:
            headers_raw: Raw HTTP header block bytes (including \\r\\n\\r\\n).

        Returns:
            Modified headers as bytes.
        """
        try:
            text = headers_raw.decode("utf-8", errors="replace")
            lines = text.split("\r\n")
            # Drop trailing empty strings produced by the \r\n\r\n terminator
            while lines and not lines[-1]:
                lines.pop()

            request_line = lines[0]
            header_lines = lines[1:]

            original_host = None
            host_line_idx = None

            for i, line in enumerate(header_lines):
                if line.lower().startswith("host:"):
                    original_host = line.split(":", 1)[1].strip()
                    host_line_idx = i
                    break

            if original_host is None:
                original_host = self.cache_domain

            # Rebuild header lines, replacing Host in-place
            new_headers = []
            host_replaced = False
            for i, line in enumerate(header_lines):
                if not line:
                    continue
                if i == host_line_idx:
                    new_headers.append(f"Host: {self.cache_domain}")
                    host_replaced = True
                else:
                    new_headers.append(line)

            if not host_replaced:
                # No Host header present — insert one right after the request line
                new_headers.insert(0, f"Host: {self.cache_domain}")

            new_headers.append(f"Real-Host: {original_host}")
            new_headers.append(f"Auth-Token: {self.token}")

            return (
                "\r\n".join([request_line] + new_headers).encode("utf-8")
                + b"\r\n\r\n"
            )
        except Exception as e:
            logger.error(f"Failed to modify headers: {e}")
            return headers_raw

    def _log_request(self, headers_raw):
        """Log an intercepted HTTP request (only called when debug is on).

        Extracts the method, host, and path from the raw request line
        and Host header and logs them at INFO level.
        """
        try:
            text = headers_raw.decode("utf-8", errors="replace")
            first_line = text.split("\r\n", 1)[0]
            # first_line is like "GET /path HTTP/1.1"
            parts = first_line.split()
            method = parts[0] if len(parts) > 0 else "?"
            path = parts[1] if len(parts) > 1 else "?"

            host = None
            for line in text.split("\r\n")[1:]:
                if line.lower().startswith("host:"):
                    host = line.split(":", 1)[1].strip()
                    break

            logger.info(f"[DEBUG] HTTP {method} {host or '?'}{path}")
        except Exception as e:
            logger.debug(f"[DEBUG] Failed to log request: {e}")

    def _write_rx_file(self):
        """Write cumulative rx bytes to rx.txt, throttled to every 1 second."""
        now = time()
        if now - self._last_rx_write_time > 1:
            self._last_rx_write_time = now
            try:
                with open("rx.txt", "w") as f:
                    f.write(str(self.total_rx))
            except Exception as e:
                logger.debug(f"Failed to write rx.txt: {e}")
