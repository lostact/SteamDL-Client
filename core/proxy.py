"""Proxy management for SteamDL Client"""
import re
import logging
import multiprocessing
from mitmproxy.tools.main import mitmdump


def start_proxy(mitm_args):
    """Start the mitmproxy with given arguments"""
    file_handler = logging.FileHandler('proxy.log')
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    root_logger.addHandler(file_handler)
    mitmdump(args=mitm_args)


def build_allow_host_patterns(domains):
    """Build --allow-hosts regex patterns from server config domains.
    
    For each domain:
      - Always add port 80 pattern (HTTP interception)
      - If block_https=True, also add port 443 pattern (HTTPS blocking)
    """
    patterns = []
    for entry in domains:
        pattern = entry["pattern"]
        block_https = entry.get("block_https", False)

        escaped = re.escape(pattern.lstrip("."))

        if pattern.startswith("."):
            # ".domain.com" matches "domain.com" and all subdomains
            base_regex = rf"(.*\.)?{escaped}"
        else:
            # "domain.com" matches only "domain.com"
            base_regex = rf"^{escaped}"

        # Always intercept HTTP (port 80) for caching
        patterns.append(f"{base_regex}:80$")

        # Only intercept HTTPS (port 443) if block_https is enabled
        if block_https:
            patterns.append(f"{base_regex}:443$")

    return patterns


def build_proxy_args(addon_dir, allow_patterns, cache_domain, cache_ip, token):
    """Build mitmproxy arguments for local capture mode."""
    addon_path = f"{addon_dir}/addon.py"
    args = [
        '--mode', 'local',
        '-s', addon_path,
        '--set', 'connection_strategy=lazy',
        '--set', 'termlog_verbosity=error',
        '--set', 'flow_detail=0',
        '--set', 'stream_large_bodies=100k',
        '--set', f'cache_domain={cache_domain}',
        '--set', f'cache_ip={cache_ip}',
        '--set', f'token={token}',
    ]
    for pattern in allow_patterns:
        args.extend(['--allow-hosts', pattern])
    # Allow DNS traffic (port 53) for interception
    args.extend(['--allow-hosts', r'.*:53$'])
    return args


def create_proxy_process(args):
    """Create and return a proxy process"""
    proxy_process = multiprocessing.Process(target=start_proxy, args=(args,))
    proxy_process.daemon = True
    return proxy_process
