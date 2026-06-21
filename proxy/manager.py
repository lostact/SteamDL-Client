"""Proxy manager — orchestrates startup/shutdown of all proxy components.

Manages the lifecycle of:
  1. Port-80 conflict detection and mitigation
  2. Phantom IP setup/teardown
  3. DNS interceptor thread
  4. Transparent HTTP proxy (asyncio)
"""
import asyncio
import logging
import socket
import subprocess
import threading

from .phantom_ip import PHANTOM_IP, setup_phantom_ip, teardown_phantom_ip
from .patterns import compile_patterns
from .dns_interceptor import DNSInterceptor
from .transparent_proxy import TransparentProxy

logger = logging.getLogger(__name__)


# ── Port-80 conflict helpers ──────────────────────────────────────────

def _check_port_80_available(ip):
    """Try to bind to *ip*:80 to verify the port is free.

    Returns ``True`` if binding succeeds (port is available), ``False``
    if binding fails (port is already in use).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip, 80))
            return True
    except OSError:
        return False


def _get_port_80_owner():
    """Identify which process owns the ``0.0.0.0:80`` listener.

    Returns:
        ``"system"`` if the owner is PID 4 (Windows System / HTTP.sys),
        otherwise the process name (e.g. ``"nginx"``), or ``None`` if
        nothing is found or inspection fails.
    """
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if (
                len(parts) >= 5
                and parts[0] == "TCP"
                and parts[1] == "0.0.0.0:80"
            ):
                pid = parts[4]
                if pid == "4":
                    return "system"
                # Look up process name for any other PID
                try:
                    task = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                        capture_output=True, text=True, timeout=5,
                    )
                    # CSV output: "name","pid","session","mem"
                    first_line = task.stdout.strip().splitlines()[0]
                    return first_line.split(",")[0].strip('"')
                except Exception:
                    return f"pid:{pid}"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("Failed to inspect port 80 occupancy: %s", exc)
    return None


def _mitigate_system():
    """Narrow HTTP.sys to 127.0.0.1 so the phantom IP is freed."""
    try:
        result = subprocess.run(
            ["netsh", "http", "add", "iplisten", "127.0.0.1"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            logger.info("HTTP.sys listener narrowed to 127.0.0.1")
            return True
        logger.warning(
            "netsh failed (rc=%d): %s %s",
            result.returncode, result.stdout.strip(), result.stderr.strip(),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Failed to run netsh: %s", exc)
    return False


def _ensure_port_80_usable(ip):
    """Make sure *ip*:80 is available for our proxy to bind.

    First tries a direct socket bind. If that fails, identifies the
    process that owns ``0.0.0.0:80`` and applies the appropriate
    mitigation.

    Raises:
        RuntimeError: If the port cannot be freed.
    """
    if _check_port_80_available(ip):
        logger.debug("Port 80 is free on %s", ip)
        return

    logger.warning("Port 80 on %s is occupied - investigating...", ip)
    owner = _get_port_80_owner()

    if owner == "system":
        logger.warning(
            "System process (PID 4 / HTTP.sys) owns 0.0.0.0:80 - "
            "narrowing listener to 127.0.0.1"
        )
        if _mitigate_system():
            return
        raise RuntimeError(
            "Failed to narrow HTTP.sys listener to 127.0.0.1. "
            "Run the application as Administrator."
        )

    raise RuntimeError(
        f"Cannot bind to {ip}:80 - port is owned by "
        f"{owner or 'an unknown process'}. No automatic mitigation available."
    )


class ProxyManager:
    """Orchestrates all proxy components.

    Args:
        server_config: Dict from server config JSON with keys:
            - "cache_ip": str
            - "cache_domain": str
            - "domains": list of domain pattern dicts
        token: User authentication token string.
    """

    def __init__(self, server_config, token, debug=False):
        self.cache_ip = server_config["cache_ip"]
        self.cache_domain = server_config["cache_domain"]
        self.domains = server_config.get("domains", [])
        self.token = token
        self.debug = debug
        self._dns_interceptor = None
        self._proxy = None
        self._proxy_thread = None
        self._loop = None

    def start(self):
        """Start all proxy components.

        1. Compile domain patterns from server config.
        2. Setup phantom IP on loopback adapter.
        3. Ensure port 80 is free on the phantom IP (mitigate conflicts).
        4. Start DNS interceptor thread.
        5. Start transparent proxy in a background thread with its own event loop.

        Raises:
            RuntimeError: If phantom IP setup or port-80 mitigation fails.
        """
        # 0. Configure proxy logger to write to its own file
        proxy_logger = logging.getLogger("proxy")
        if not proxy_logger.handlers:
            fh = logging.FileHandler("proxy.log")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            proxy_logger.addHandler(fh)
            proxy_logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
            proxy_logger.propagate = False  # don't duplicate into app.log

        # 1. Compile patterns
        domain_patterns, _ = compile_patterns(self.domains)
        logger.info(f"Compiled {len(domain_patterns)} domain patterns")

        # 2. Setup phantom IP
        setup_phantom_ip()

        # 3. Ensure port 80 is available on the phantom IP
        _ensure_port_80_usable(PHANTOM_IP)

        # 4. Start DNS interceptor
        self._dns_interceptor = DNSInterceptor(domain_patterns, PHANTOM_IP)
        self._dns_interceptor.start()

        # 5. Create transparent proxy (listens on port 80 for HTTP with header
        #    modification, and on port 443 for raw TCP passthrough)
        self._proxy = TransparentProxy(
            listen_ip=PHANTOM_IP,
            cache_ip=self.cache_ip,
            cache_domain=self.cache_domain,
            token=self.token,
            debug=self.debug,
        )

        # Run the asyncio event loop in a background thread so the caller
        # (which runs the UI event loop) is not blocked.
        self._loop = asyncio.new_event_loop()
        self._proxy_thread = threading.Thread(
            target=self._run_proxy_loop, daemon=True, name="TransparentProxy"
        )
        self._proxy_thread.start()
        logger.info("Proxy manager started")

    def _run_proxy_loop(self):
        """Run the asyncio event loop for the transparent proxy."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._proxy.start())
        except Exception as e:
            if "Event loop stopped" not in str(e):
                logger.error(f"Proxy event loop error: {e}")

    def stop(self):
        """Stop all proxy components and clean up resources."""
        logger.info("Stopping proxy manager...")

        # Stop transparent proxy
        if self._proxy:
            self._proxy.stop()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._proxy_thread and self._proxy_thread.is_alive():
            self._proxy_thread.join(timeout=3)

        # Stop DNS interceptor
        if self._dns_interceptor:
            self._dns_interceptor.stop()
            self._dns_interceptor.join(timeout=3)

        # Teardown phantom IP
        teardown_phantom_ip()

        logger.info("Proxy manager stopped")

    def is_alive(self):
        """Check if the proxy components are running.

        Returns:
            True if both the DNS interceptor and proxy thread are alive.
        """
        dns_alive = self._dns_interceptor and self._dns_interceptor.is_alive()
        proxy_alive = self._proxy_thread and self._proxy_thread.is_alive()
        return dns_alive and proxy_alive
