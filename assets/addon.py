"""SteamDL mitmproxy addon for local capture mode."""
import os
from mitmproxy import ctx
from time import time


class SteamDLAddon:
    """Modifies HTTP headers and tracks usage for cache domain traffic.

    Traffic filtering is handled by mitmproxy's --allow-hosts flag.
    Config values (cache_domain, cache_ip, token) are passed via
    mitmproxy --set custom options — no config file needed.
    """

    def load(self, loader):
        """Register custom options that are set via --set flags."""
        loader.add_option("cache_domain", str, "", "Cache server domain")
        loader.add_option("cache_ip", str, "", "Cache server IP address")
        loader.add_option("token", str, "", "User authentication token")
        self.last_update_time = 0
        self.rx_bytes = 0
        # Restore previous usage counter if it exists
        try:
            if os.path.isfile("rx.txt"):
                with open("rx.txt", "r") as rx_file:
                    self.rx_bytes = int(rx_file.read().strip())
        except Exception:
            pass

    def requestheaders(self, flow):
        """Add routing and auth headers. Every request here is a cache domain
        match — no domain filtering needed (--allow-hosts handles that)."""
        original_host = flow.request.host_header or flow.request.pretty_host
        flow.request.host = ctx.options.cache_ip
        flow.request.headers["Real-Host"] = original_host
        flow.request.headers["Host"] = ctx.options.cache_domain
        flow.request.headers["Auth-Token"] = ctx.options.token

    def responseheaders(self, flow):
        """Track download usage."""
        if 200 <= flow.response.status_code <= 299:
            ua = flow.request.headers.get("User-Agent", "")
            if ua != "GamingServices":
                self.rx_bytes += int(flow.response.headers.get("Content-Length", 0))

        current_time = time()
        if current_time - self.last_update_time > 2:
            self.last_update_time = current_time
            with open("rx.txt", "w") as rx_file:
                rx_file.write(str(self.rx_bytes))


addons = [SteamDLAddon()]
