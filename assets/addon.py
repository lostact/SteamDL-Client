from mitmproxy import ctx
from time import time
import os 

class SteamDL:
    def load(self, loader):
        loader.add_option(name="token",typespec=str,default="",help="User Token")
        mode_string = ctx.options.mode[0]
        domain_start = mode_string.find("//") + 2
        self.cache_domain = mode_string[domain_start:].split("@")[0]
        self.last_update_time = 0
        self.rx_bytes = 0
        if os.path.isfile("rx.txt"):
            with open("rx.txt", 'r') as rx_file:
                self.rx_bytes = int(rx_file.read().strip())
        
    def requestheaders(self, flow):
        if flow.request.method == "GET":
            flow.request.headers["Real-Host"] = flow.request.host_header
            flow.request.headers["Host"] = self.cache_domain    
            flow.request.headers["Auth-Token"] = ctx.options.token

    def response(self,flow):
        self.rx_bytes += len(flow.response.content)
        current_time = time()
        if current_time - self.last_update_time > 2:
            self.last_update_time = current_time
            with open("rx.txt", "w") as rx_file:
                rx_file.write(str(self.rx_bytes))

addons = [SteamDL()]
