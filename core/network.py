"""Network-related functions for SteamDL Client"""
import re
import socket
import logging
from .utils import run_cmd

def find_programs_listening_on_ports():
    """Find programs listening on ports 80 and 443"""
    results = []
    for port_number in [80, 443]:
        result = run_cmd(["powershell", "Get-Process", "-Id", f"(Get-NetTCPConnection -LocalPort {port_number}).OwningProcess"])
        if result.returncode == 0:
            results.append(result.stdout)
    programs = []
    for result in results:
        lines = result.splitlines()
        for line in lines:
            values = line.split()
            if len(values) >= 8:
                if values[5].isnumeric() and values[5] != "0":
                    programs.append(values[7])
    return programs

def get_active_adapter():
    """Get the active network adapter with internet connection"""
    disconnected_interfaces = []
    result = run_cmd(["netsh", "interface", "show", "interface"])
    if result.returncode != 0:
        logging.error("Failed to get interface status list.")
    else:
        interface_pattern = r'\s*Enabled\s+Disconnected\s+\S+\s+(.+)'
        interfaces = re.finditer(interface_pattern, result.stdout)
        for interface in interfaces:
            disconnected_interfaces.append(interface.group(1).strip())

    result = run_cmd(["netsh", "interface", "ipv4", "show", "config"])
    if result.returncode != 0:
        logging.error("Failed to get network configuration.")
        return
    
    interface_pattern = r"Configuration for interface \"([^\"]+)\"\n(.*\n?)+?(\n|$)"
    interfaces = re.finditer(interface_pattern, result.stdout)

    active_adapter = None
    minimum_metric = float('inf')
    for interface in interfaces:
        adapter_name = interface.group(1)
        gateway_pattern = r"Default Gateway:\s+([\d\.]+)"
        gateway_match = re.search(gateway_pattern, interface.group(0))
        metric_pattern = r"Gateway Metric:\s+(\d+)"
        metric_match = re.search(metric_pattern, interface.group(0))
        if gateway_match and metric_match:
            gateway = gateway_match.group(1)
            metric = int(metric_match.group(1))
            if gateway and gateway != "0.0.0.0" and adapter_name not in disconnected_interfaces and metric < minimum_metric:
                active_adapter = adapter_name
                minimum_metric = metric

    if active_adapter:
        return active_adapter
    else:
        logging.error("No active adapter with an internet connection found.")

def get_dns_settings(adapter_name):
    """Get DNS settings for a network adapter"""
    if not adapter_name:
        return []

    dns_servers = []
    try:
        result = run_cmd(["netsh", "interface", "ipv4", "show", "dnsservers", adapter_name])
        if result.returncode != 0:
            logging.error(f"Failed to get DNS settings for adapter: {adapter_name}")
        
        if "Statically Configured DNS Servers" in result.stdout:
            dns_pattern = r"(\d+\.\d+\.\d+\.\d+)"
            dns_servers = re.findall(dns_pattern, result.stdout, re.MULTILINE)
    except:
        logging.error(f"Failed to get DNS settings for adapter: {adapter_name}")
        
    return dns_servers

def set_dns_settings(adapter_name, dns_servers):
    """Set DNS settings for a network adapter"""
    if not dns_servers:
        run_cmd(["netsh", "interface", "ipv4", "set", "dnsservers", adapter_name, "dhcp"])
    else:
        run_cmd(["netsh", "interface", "ipv4", "set", "dnsservers", adapter_name, "static", dns_servers[0]])
        # Set secondary DNS if provided
        if len(dns_servers) > 1:
            run_cmd(["netsh", "interface", "ipv4", "add", "dnsservers", adapter_name, dns_servers[1], "index=2"])

    run_cmd(["ipconfig", "/flushdns"])

def get_default_interface_ip(cache_ip):
    """Get the IP address of the default network interface"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((cache_ip, 53))
            ip_address = s.getsockname()[0]
        return ip_address
    except Exception as e:
        logging.error(f"Error obtaining default interface IP: {e}")
        return None
