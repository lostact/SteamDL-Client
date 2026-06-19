"""Transparent proxy package for SteamDL Client.

Replaces the mitmproxy-based proxy stack with a lightweight transparent proxy
that uses DNS-level interception (pydivert/WinDivert) combined with a phantom
IP address and a simple asyncio TCP proxy.
"""
from .manager import ProxyManager

__all__ = ["ProxyManager"]
