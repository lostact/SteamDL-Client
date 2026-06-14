"""Proxy management for SteamDL Client.

Replaces the previous mitmproxy-based proxy with a transparent proxy
that uses DNS-level interception and an asyncio TCP proxy.
"""
from proxy.manager import ProxyManager


def create_proxy_manager(server_config, token, debug=False):
    """Create and return a ProxyManager for the given server config.

    Args:
        server_config: Dict from server config JSON with keys:
            - "cache_ip": str
            - "cache_domain": str
            - "domains": list of domain pattern dicts
        token: User authentication token string.
        debug: If True, enable request-level logging in the transparent proxy.

    Returns:
        ProxyManager instance ready to call .start()
    """
    return ProxyManager(server_config, token, debug=debug)
