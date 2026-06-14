"""Proxy manager — orchestrates startup/shutdown of all proxy components.

Manages the lifecycle of:
  1. Phantom IP setup/teardown
  2. DNS interceptor thread
  3. Transparent HTTP proxy (asyncio)
"""
import asyncio
import logging
import threading

from .phantom_ip import PHANTOM_IP, setup_phantom_ip, teardown_phantom_ip
from .patterns import compile_patterns
from .dns_interceptor import DNSInterceptor
from .transparent_proxy import TransparentProxy

logger = logging.getLogger(__name__)


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
        3. Start DNS interceptor thread.
        4. Start transparent proxy in a background thread with its own event loop.

        Raises:
            RuntimeError: If phantom IP setup fails.
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

        # 3. Start DNS interceptor
        self._dns_interceptor = DNSInterceptor(domain_patterns, PHANTOM_IP)
        self._dns_interceptor.start()

        # 4. Create transparent proxy (listens on port 80 for HTTP with header
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
