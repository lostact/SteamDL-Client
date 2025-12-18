"""Proxy management for SteamDL Client"""
import logging
import multiprocessing
from mitmproxy.tools.main import mitmdump

def start_proxy(mitm_args):
    """Start the mitmproxy with given arguments"""
    logging.basicConfig(
        level=logging.WARN,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler('proxy.log')
        ]
    )
    mitmdump(args=mitm_args)

def build_proxy_args(cache_domain, cache_ip, local_ip, addon_path, token):
    """Build mitmproxy arguments"""
    return [
        '--mode', f"reverse:http://{cache_domain}@{local_ip}:80",
        '--mode', f"reverse:tcp://{cache_ip}:443@{local_ip}:443",
        '-s', f"\"{addon_path}\"",
        '--set', f"allow_hosts={cache_domain}",
        '--set', f"token={token}",
        '--set', f"keep_host_header=true",
        '--set', 'termlog_verbosity=warn',
        '--set', 'flow_detail=0',
        '--set', 'stream_large_bodies=100k'
    ]

def create_proxy_process(args):
    """Create and return a proxy process"""
    proxy_process = multiprocessing.Process(target=start_proxy, args=([args]))
    proxy_process.daemon = True
    return proxy_process
