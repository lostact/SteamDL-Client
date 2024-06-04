import webview, sys, os, requests, json, subprocess, threading, socket, wmi

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_all_networks_and_dns_servers():
    wmi_service = wmi.WMI()

    networks_and_servers = {adaptor.Description: adaptor.DNSServerSearchOrder
                            for adaptor in wmi_service.Win32_NetworkAdapterConfiguration(IPEnabled=True)
                            if "Virtual" not in adaptor.Description}

    return networks_and_servers


def set_dns_of_network(action, network_name, dns_servers=None):
    wmi_service = wmi.WMI()
    network = wmi_service.Win32_NetworkAdapterConfiguration(IPEnabled=True, Description=network_name)[0]
    network.SetDNSServerSearchOrder(dns_servers) if action == "change" else network.SetDNSServerSearchOrder()

VERSION = "1.0.3"
WINDOW_TITLE = "SteamDL v{}".format(VERSION)

CACHE_DOMAIN = "dl.steamdl.ir"
API_DOMAIN = "api.steamdl.ir"

MITM_PATH = resource_path('assets/mitmdump.exe')
MITM_ADDON_PATH = resource_path('assets/addon.py')
MITM_RX_PATH = 'rx.txt'

INDEX_PATH = resource_path('assets/web/index.html')
FORM_PATH = resource_path('assets/web/form.html')

SEARCH_IP_BYTES = socket.inet_aton("127.0.0.1")

class Api:
    def __init__(self):
        self._window = None
        self._token = None
        self._user_data = None

        self._cache_ip = None
        self._local_ip = None
        self._local_ip_bytes = None

        self._mitm_process = None
        self._dns_thread = None
        self._dns_backup = None

    def get_default_interface_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self._cache_ip, 53))
                ip_address = s.getsockname()[0]
            return ip_address
        except Exception as e:
            print(f"Error obtaining default interface IP: {e}")
            return None

    def handle_dns_client(self, data, client_address, dns_socket):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket:
            upstream_socket.sendto(data, (self._cache_ip, 53))
            response_data_bytes, _ = upstream_socket.recvfrom(512)
            response_data = bytearray(response_data_bytes)
            start = response_data.find(SEARCH_IP_BYTES)
            if start != -1:
                response_data[start:start+len(SEARCH_IP_BYTES)] = self._local_ip_bytes
            dns_socket.sendto(bytes(response_data), client_address)

    def start_dns(self):
        self._dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._dns_socket.bind((self._local_ip, 53))
        print(f"UDP proxy listening on {self._local_ip}:53")
        while self.check_mitm_status():
            try:
                data, client_address = self._dns_socket.recvfrom(512)
                client_thread = threading.Thread(target=self.handle_dns_client, args=(data, client_address, self._dns_socket))
                client_thread.start()
            except:
                pass

    def set_window(self, window):
        self._window = window

    def submit_token(self, token, change_window = True):
        self._token = token
        response = requests.get(f"http://{API_DOMAIN}/get_user?token=" + self._token)
        success = False
        if response:
            success = bool(response.status_code == 200)

        if not success:
            window.evaluate_js("document.getElementById('error').style.display = 'block';")
            return

        self._user_data = json.loads(response.content)
        self._cache_ip = response.headers['X-Server-IP']
        with open("account.txt", "w") as account_file:
            account_file.write(token)

        if change_window:
            self._window.load_url(INDEX_PATH)

    def toggle_mitm(self):
        running = self.check_mitm_status()
        if running:
            local_ip = ""
            print("Stopping Service...")

            # Kill MITMProxy:
            print("Killing MITM...")
            subprocess.call(['taskkill', '/PID', str(self._mitm_process.pid), '/T', '/F'],close_fds=True, creationflags=134217728, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # Restore system DNS servers:
            print("Restoring system DNS servers...")
            for network in self._dns_backup:
                if len(self._dns_backup[network]) > 1:
                    set_dns_of_network("change", network, self._dns_backup[network])
                else:
                    set_dns_of_network("clear", network)
        else:
            print("Starting Service...")
            token = self._token
            cache_ip = self._cache_ip
            local_ip = self._local_ip = self.get_default_interface_ip()
            local_ip_bytes = self._local_ip_bytes = socket.inet_aton(local_ip)

            # Run MITMProxy:
            print("Starting MITM...")
            self._mitm_process = subprocess.Popen(f"\"{MITM_PATH}\" --mode reverse:http://{CACHE_DOMAIN}@{local_ip}:80 --mode reverse:tcp://{cache_ip}:443@{local_ip}:443 --set keep_host_header=true --set allow_hosts={CACHE_DOMAIN} -s \"{MITM_ADDON_PATH}\" --set token={token} --set flow_detail=0 --set termlog_verbosity=debug", close_fds=True, creationflags=134217728, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # result = self._mitm_process.communicate()
            # for line in result[1].decode(encoding='utf-8').strip().split('\n'):
            #     print(line)
            # with self._mitm_process.stdout:
            #     for line in iter(self._mitm_process.stdout.readline, b''):
            #         print(line.decode("utf-8").strip())


            # Run DNS reverse proxy:
            print("Starting DNS server...")
            if not self._dns_thread:
                dns_thread = self._dns_thread = threading.Thread(target=self.start_dns, daemon=True)
                dns_thread.start()

            # Change system DNS servers:
            print("Changing system DNS servers...")
            dns_backup = self._dns_backup = get_all_networks_and_dns_servers()
            for network in dns_backup:
                set_dns_of_network("change", network, (local_ip, "1.1.1.1"))
        return local_ip


    def check_mitm_status(self):
        if self._mitm_process:
            return self._mitm_process.poll() == None
        else:
            return False

    def get_user_data(self):
        print("User Data:", self._user_data)
        return self._user_data

    def get_rx(self):
        if os.path.isfile(MITM_RX_PATH):
            with open(MITM_RX_PATH, 'r') as rx_file:
                rx = int(rx_file.read().strip())
                return rx
        else:
            return 0

    def minimize(self):
        self._window.minimize()

    def close(self):
        self._window.destroy()

    def get_version(self):
        return VERSION

if __name__ == '__main__':
    api = Api()

    success = False
    if os.path.isfile("account.txt"):
        with open("account.txt", "r") as account_file:
            token = account_file.read().strip()
            if token:
                api.submit_token(token, False)

    if api._user_data:
        window = webview.create_window(WINDOW_TITLE, INDEX_PATH, width=400,height=600,js_api=api, frameless=True)
        api.set_window(window) 
    else:
        window = webview.create_window(WINDOW_TITLE, FORM_PATH, width=400,height=600,js_api=api, frameless=True)
        api.set_window(window)

    webview.start()

    # Quit:
    running = api.check_mitm_status()
    if running:
        api.toggle_mitm()