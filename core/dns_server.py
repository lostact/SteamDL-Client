"""DNS server implementation for SteamDL Client"""
import socket
import threading
import logging

import dns.message
import dns.rcode
import dns.rdata
import dns.rdataclass
import dns.rdatatype

# Maximum UDP payload size we accept (EDNS0 allows larger-than-512 messages).
DNS_MAX_UDP_SIZE = 4096

# Timeouts (seconds)
CACHE_DNS_TIMEOUT = 5
ANTI_SANCTION_DNS_TIMEOUT = 3

LOOPBACK_IP = "127.0.0.1"


class DNSServer:
    """DNS server that forwards requests and replaces specific IPs"""

    def __init__(self, local_ip, cache_ip, anti_sanction_ip):
        self.local_ip = local_ip
        self.cache_ip = cache_ip
        self.anti_sanction_ip = anti_sanction_ip
        self.dns_running = False
        self.dns_socket = None

    def _replace_a_record_ips(self, response_data):
        """Replace 127.0.0.1 with the local IP in A-record answers only.

        Parses the DNS message properly instead of doing a raw byte search,
        so the 4-byte loopback pattern is never matched inside transaction
        IDs, domain labels or AAAA records. All matching A records are
        replaced (round-robin responses included).

        Returns a tuple ``(data, modified)`` where *data* is the (possibly
        rewritten) wire data and *modified* indicates whether any A record
        was replaced. Malformed data is returned unchanged.
        """
        try:
            message = dns.message.from_wire(response_data)
        except Exception:
            return response_data, False

        modified = False
        for rrset in message.answer:
            if rrset.rdtype != dns.rdatatype.A:
                continue
            for rdata in list(rrset):
                if rdata.address == LOOPBACK_IP:
                    rrset.remove(rdata)
                    rrset.add(
                        dns.rdata.from_text(
                            dns.rdataclass.IN, dns.rdatatype.A, self.local_ip
                        )
                    )
                    modified = True

        if not modified:
            return response_data, False

        try:
            return message.to_wire(max_size=DNS_MAX_UDP_SIZE), True
        except Exception:
            return response_data, False

    def _send_servfail(self, query_data, client_address):
        """Send a SERVFAIL response for *query_data* to the client.

        This makes upstream failures visible to the client immediately
        instead of leaving it waiting for its own resolver timeout or
        handing it a stale answer.
        """
        try:
            query = dns.message.from_wire(query_data)
            response = dns.message.make_response(query)
            response.set_rcode(dns.rcode.SERVFAIL)
            self._send_response(response.to_wire(max_size=DNS_MAX_UDP_SIZE), client_address)
        except Exception as e:
            logging.error(f"Failed to send SERVFAIL response: {e}")

    def _send_response(self, data, client_address):
        """Send *data* to the client through a dedicated per-thread socket.

        Each worker thread uses its own socket (bound to the same address
        as the listener so replies originate from port 53) instead of
        sharing the listening socket across threads.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as response_socket:
                response_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                response_socket.bind((self.local_ip, 53))
                response_socket.sendto(data, client_address)
        except OSError as e:
            # Fall back to the main listening socket if a dedicated socket
            # cannot be bound on this platform.
            if self.dns_socket:
                try:
                    self.dns_socket.sendto(data, client_address)
                except OSError as fallback_error:
                    logging.error(f"Failed to send DNS response: {fallback_error}")
            else:
                logging.error(f"Failed to send DNS response: {e}")

    def process_dns_request(self, data, client_address):
        """Process a single DNS request"""
        try:
            # Query the cache DNS server first.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket:
                upstream_socket.settimeout(CACHE_DNS_TIMEOUT)
                upstream_socket.sendto(data, (self.cache_ip, 53))
                try:
                    response_data, _ = upstream_socket.recvfrom(DNS_MAX_UDP_SIZE)
                except socket.timeout:
                    logging.warning("Cache DNS query timed out, sending SERVFAIL.")
                    self._send_servfail(data, client_address)
                    return

            response_data, modified = self._replace_a_record_ips(response_data)

            if not modified and self.anti_sanction_ip != self.cache_ip:
                # The cache server did not claim this domain - fall back to
                # the anti-sanction DNS server.
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as anti_sanction_socket:
                    anti_sanction_socket.settimeout(ANTI_SANCTION_DNS_TIMEOUT)
                    anti_sanction_socket.sendto(data, (self.anti_sanction_ip, 53))
                    try:
                        response_data, _ = anti_sanction_socket.recvfrom(DNS_MAX_UDP_SIZE)
                    except socket.timeout:
                        logging.warning("Anti-sanction DNS query timed out, sending SERVFAIL.")
                        self._send_servfail(data, client_address)
                        return

            self._send_response(response_data, client_address)
        except Exception as e:
            logging.error(f"Error processing DNS request: {e}")
            self._send_servfail(data, client_address)

    def start(self):
        """Start the DNS server"""
        self.dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dns_socket.bind((self.local_ip, 53))
        self.dns_socket.settimeout(1)
        self.dns_running = True

        logging.info(f"DNS server listening on {self.local_ip}:53")
        while self.dns_running:
            try:
                data, client_address = self.dns_socket.recvfrom(DNS_MAX_UDP_SIZE)
                client_thread = threading.Thread(
                    target=self.process_dns_request,
                    args=(data, client_address),
                    daemon=True,
                )
                client_thread.start()
            except socket.timeout:
                pass
            except Exception as e:
                logging.error(f"DNS server error: {e}")

        self.dns_socket.close()
        self.dns_socket = None
        logging.info("DNS server stopped.")

    def stop(self):
        """Stop the DNS server"""
        self.dns_running = False

    def is_running(self):
        """Check if DNS server is running"""
        return self.dns_running
