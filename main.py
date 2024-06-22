import sys, os, requests, json, subprocess, threading, socket, wmi, webview, logging

# Configure logging
log_file = 'app.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

# log uncaught exceptions
def log_uncaught_exceptions(exctype, value, tb):
    logging.error("Uncaught exception", exc_info=(exctype, value, tb))
sys.excepthook = log_uncaught_exceptions

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


def configure_network_dns(action, network_name, dns_servers=None):
    wmi_service = wmi.WMI()
    network = wmi_service.Win32_NetworkAdapterConfiguration(IPEnabled=True, Description=network_name)[0]
    network.SetDNSServerSearchOrder(dns_servers) if action == "change" else network.SetDNSServerSearchOrder()

CURRENT_VERSION = "1.1.2"
WINDOW_TITLE = "SteamDL v{}".format(CURRENT_VERSION)
GITHUB_RELEASE_URL = "https://github.com/lostact/SteamDL-Client/releases/latest/download/steamdl_installer.exe"

CACHE_DOMAIN = "dl.steamdl.ir"
API_DOMAIN = "api.steamdl.ir"

PROXY_EXEC_PATH = resource_path('assets/http_proxy.exe')
PROXY_ADDON_PATH = resource_path('assets/addon.py')

INDEX_PATH = resource_path('assets/web/index.html')
FORM_PATH = resource_path('assets/web/form.html')
UPDATE_PATH = resource_path('assets/web/update.html')

SEARCH_IP_BYTES = socket.inet_aton("127.0.0.1")

def check_for_update():
    try:
        response = requests.head(GITHUB_RELEASE_URL, allow_redirects=False)
        redirect_url = response.headers["Location"]

        latest_version = redirect_url.split('/')[-2]
        current_tuple, latest_tuple = tuple(map(int, (CURRENT_VERSION.split(".")))), tuple(map(int, (latest_version.split("."))))
        logging.info(str(current_tuple) +  str(latest_tuple))
        if latest_tuple and latest_tuple > current_tuple:
            return True, redirect_url
        return False, None
    except requests.RequestException as e:
        logging.info(f"Failed to check for update: {e}")
        return False, None

def apply_update(download_url, progress_callback):
    installer_path = "steamdl_installer.exe"
    try:
        response = requests.get(download_url, allow_redirects=True, stream=True)
        response.raise_for_status()
        total_length = response.headers.get('content-length')
        if total_length is None:  # no content length header
            installer_path = None
        else:
            total_length = int(total_length)
            dl = 0
            with open(installer_path, "wb") as installer_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        dl += len(chunk)
                        installer_file.write(chunk)
                        done = int(100 * dl / total_length)
                        progress_callback(done)
            logging.info("Downloading update finished.")
            subprocess.Popen([installer_path, "/S"], close_fds=True, creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW)
            os._exit(0)
    except requests.RequestException as e:
        logging.error(f"Failed to apply update: {e}")
        return None

class Api:
    def __init__(self):
        self._window = None
        self._token = None
        self._user_data = None

        self._cache_ip = None
        self._local_ip = None
        self._local_ip_bytes = None

        self._proxy_process = None
        self._dns_running = None
        self._proxy_log_file = None
        self._dns_thread = None
        self._dns_backup = None

    def get_default_interface_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self._cache_ip, 53))
                ip_address = s.getsockname()[0]
            return ip_address
        except Exception as e:
            logging.error(f"Error obtaining default interface IP: {e}")
            return None

    def process_dns_request(self, data, client_address, dns_socket):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket:
            upstream_socket.sendto(data, (self._cache_ip, 53))
            response_data_bytes, _ = upstream_socket.recvfrom(512)
            response_data = bytearray(response_data_bytes)
            start = response_data.find(SEARCH_IP_BYTES)
            if start != -1:
                response_data[start:start+len(SEARCH_IP_BYTES)] = self._local_ip_bytes
            dns_socket.sendto(bytes(response_data), client_address)

    def start_dns(self):
        dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_socket.bind((self._local_ip, 53))
        dns_socket.settimeout(1)
        self._dns_running = True

        logging.info(f"DNS server listening on {self._local_ip}:53")
        while self._dns_running:
            try:
                data, client_address = dns_socket.recvfrom(512)
                client_thread = threading.Thread(target=self.process_dns_request, args=(data, client_address, dns_socket))
                client_thread.start()
            except socket.timeout:
                pass
            except Exception as error:
                logging.error(f"DNS server error: {error}")

        dns_socket.close()
        logging.info("DNS server stopped.")

    def set_window(self, window):
        self._window = window

    def submit_token(self, token, change_window = True):
        self._token = token
        success = False
        try:
            response = requests.get(f"https://{API_DOMAIN}/get_user?token=" + self._token)
            if response:
                success = bool(response.status_code == 200)
        except Exception as error:
            logging.error(f"Failed to get user data: {error}")
        

        if not success:
            if self._window:
                self._window.evaluate_js("document.getElementById('error').style.display = 'block';")
            return

        self._user_data = json.loads(response.content)
        self._cache_ip = response.headers['X-Server-IP']
        with open("account.txt", "w") as account_file:
            account_file.write(token)

        if change_window:
            self._window.load_url(INDEX_PATH)

    def toggle_proxy(self, running=None):
        local_ip = ""

        if running == None:
            running = self.check_proxy_status()

        # Kill Proxy (even if we think it isn't running, to make sure we can run it again):
        logging.info("Killing Proxy...")
        subprocess.call(['taskkill', '/IM', 'http_proxy.exe', '/T', '/F'], close_fds=True, creationflags=134217728, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        if running:
            # Kill DNS:
            self._dns_running = False

            # Restore system DNS servers:
            logging.info("Restoring system DNS servers...")
            for network in self._dns_backup:
                if len(self._dns_backup[network]) > 1:
                    configure_network_dns("change", network, self._dns_backup[network])
                else:
                    configure_network_dns("clear", network)
        else:
            token = self._token
            cache_ip = self._cache_ip
            local_ip = self._local_ip = self.get_default_interface_ip()
            local_ip_bytes = self._local_ip_bytes = socket.inet_aton(local_ip)

            # Run Proxy:
            logging.info("Starting Proxy...")
            if not self._proxy_log_file:
                self._proxy_log_file = open('proxy.log', 'a')
            self._proxy_process = subprocess.Popen(f"\"{PROXY_EXEC_PATH}\" --mode reverse:http://{CACHE_DOMAIN}@{local_ip}:80 --mode reverse:tcp://{cache_ip}:443@{local_ip}:443 --set keep_host_header=true --set allow_hosts={CACHE_DOMAIN} -s \"{PROXY_ADDON_PATH}\" --set token={token} --set termlog_verbosity=warn --set flow_detail=0 --set stream_large_bodies=100k", close_fds=True, creationflags=134217728, stdout=self._proxy_log_file, stderr=self._proxy_log_file)

            # Run DNS reverse proxy:
            logging.info("Starting DNS server...")
            if not self._dns_running:
                dns_thread = self._dns_thread = threading.Thread(target=self.start_dns, daemon=True)
                dns_thread.start()
            else:
                print(self._dns_thread)

            # Change system DNS servers:
            logging.info("Changing system DNS servers...")
            dns_backup = self._dns_backup = get_all_networks_and_dns_servers()
            for network in dns_backup:
                configure_network_dns("change", network, (local_ip, "1.1.1.1"))
        
        return local_ip


    def check_proxy_status(self):
        if self._proxy_process:
            if self._proxy_process.poll() == None and self.get_default_interface_ip() == self._local_ip and self._dns_running:
                return True
            elif self._proxy_process.poll() == None:
                self.toggle_proxy(True)
                return False
            else:
                return False
        else:
            return False

    def get_user_data(self):
        logging.info("User Data: " + str(self._user_data))
        return self._user_data

    def get_rx(self):
        if os.path.isfile('rx.txt'):
            with open('rx.txt', 'r') as rx_file:
                rx = int(rx_file.read().strip())
                return rx
        else:
            return 0

    def minimize(self):
        self._window.minimize()

    def close(self):
        self._window.destroy()

    def get_version(self):
        return CURRENT_VERSION

if __name__ == '__main__':
    api = Api()

    update_available, download_url = check_for_update()
    if update_available:
        def progress_callback(progress):
            window.evaluate_js(f'updateProgress({progress})')

        update_thread = threading.Thread(target=apply_update, args=(download_url, progress_callback))
        update_thread.start()

        window = webview.create_window(WINDOW_TITLE, UPDATE_PATH, width=300,height=210,js_api=api, frameless=True)
        try:
            webview.start(gui="edgehtml")
        except:
            webview.start(gui="edgechromium")
        sys.exit()
    elif os.path.isfile("steamdl_installer.exe"):
        os.remove("steamdl_installer.exe")

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

    try:
        webview.start(gui="edgehtml")
    except:
        webview.start(gui="edgechromium")

    # Quit:
    if api.check_proxy_status():
        api.toggle_proxy()

    sys.exit()