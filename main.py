import sys, os, requests, json, subprocess, threading, socket, wmi, webview, logging, time, winreg

import ctypes
from ctypes import wintypes
import dns.resolver
from forcediphttpsadapter.adapters import ForcedIPHTTPSAdapter

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

def cleanup_temp_folders():
    temp_dir = os.environ.get('TEMP')
    if temp_dir:
        for folder_name in os.listdir(temp_dir):
            folder_path = os.path.join(temp_dir, folder_name)
            if os.path.isdir(folder_path) and ("EBWebView" in os.listdir(folder_path)):
                try:
                    subprocess.run(['rmdir', '/S', '/Q', folder_path], shell=True, check=True)
                except subprocess.CalledProcessError as e:
                    logging.info(f"Failed to remove webview temp files in {folder_path}: {e}")

CURRENT_VERSION = "1.2.6"
WINDOW_TITLE = f"SteamDL v{CURRENT_VERSION}"
GITHUB_RELEASE_URL = "https://github.com/lostact/SteamDL-Client/releases/latest/download/steamdl_installer.exe"

CACHE_DOMAIN = "dl.steamdl.ir"
API_DOMAIN = "api.steamdl.ir"
FILES_DOMAIN = "files.steamdl.ir"

PROXY_EXEC_PATH = resource_path('assets/http_proxy.exe')
PROXY_ADDON_PATH = resource_path('assets/addon.py')

INDEX_PATH = resource_path('assets/web/index.html')
FORM_PATH = resource_path('assets/web/form.html')
UPDATE_PATH = resource_path('assets/web/update.html')

SEARCH_IP_BYTES = socket.inet_aton("127.0.0.1")
ANTI_SANCTION_TEST_DOMAIN = "www.epicgames.com"
ANTI_SANCTION_TEST_PATH = "/id/api/authenticate"

# ANTI_SANCTION_TEST_DOMAIN = "packages.gitlab.com"
# ANTI_SANCTION_TEST_PATH = "/gitlab/gitlab-ce/packages/el/7/gitlab-ce-16.8.0-ce.0.el7.x86_64.rpm/download.rpm"

def check_for_update():
    try:
        response = requests.head(GITHUB_RELEASE_URL, allow_redirects=False)
        redirect_url = response.headers["Location"]

        latest_version = redirect_url.split('/')[-2]
        current_tuple, latest_tuple = tuple(map(int, (CURRENT_VERSION.split(".")))), tuple(map(int, (latest_version.split("."))))
        logging.info("current version: " + CURRENT_VERSION + " - latest version: " + latest_version)
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
            subprocess.Popen([installer_path, "/S"], close_fds=True, creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
            os._exit(0)
    except requests.RequestException as e:
        logging.error(f"Failed to apply update: {e}")
        return None

class Api:
    def __init__(self):
        self._window = None
        self._token = None
        self._user_data = None
        self._anti_sanction_data = None

        self._cache_ip = None
        self._local_ip = None
        self._local_ip_bytes = None
        self._anti_sanction_dns = None

        self._proxy_process = None
        self._dns_running = None
        self._proxy_log_file = None
        self._dns_thread = None
        self._dns_backup = None
        self._auto_connect = False

    def is_in_startup(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            value, reg_type = winreg.QueryValueEx(key, "steamdl")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logging.error(f"Error checking startup status: {e}")
            return False

    def add_to_startup(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "steamdl", 0, winreg.REG_SZ, sys.executable)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            logging.error(f"Error adding to startup: {e}")
            return False

    def remove_from_startup(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "steamdl")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            logging.error("The application was not in the startup list.")
            return False
        except Exception as e:
            logging.error(f"Error removing from startup: {e}")
            return False

    def get_default_interface_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self._cache_ip, 53))
                ip_address = s.getsockname()[0]
            return ip_address
        except Exception as e:
            logging.error(f"Error obtaining default interface IP: {e}")
            return None

    def get_anti_sanction_data(self):
        try:
            response = requests.get(f"https://{FILES_DOMAIN}/anti_sanction_dns.json")
            if response:
                self._anti_sanction_data = json.loads(response.content)
                self._anti_sanction_dns = self._anti_sanction_data[0]['ip']
                return self._anti_sanction_data
        except Exception as error:
            logging.error(f"Failed to get anti sanction data: {error}")

    def change_anti_sanction(self, anti_sanction_index):
        self._anti_sanction_dns = self._anti_sanction_data[int(anti_sanction_index) - 1]["ip"]

    def test_anti_sanction(self):
        successful_resolutions = {}
        custom_resolver = dns.resolver.Resolver()
        for index,anti_sanction_dns in enumerate(self._anti_sanction_data):
            successful_resolutions[anti_sanction_dns["name"]] = False
            dns_ip = anti_sanction_dns["ip"]
            custom_resolver.nameservers = [dns_ip]
            try:
                destination_ip = str(custom_resolver.resolve(ANTI_SANCTION_TEST_DOMAIN, 'A')[0])
                self._anti_sanction_dns = dns_ip
                url = f"https://{ANTI_SANCTION_TEST_DOMAIN}{ANTI_SANCTION_TEST_PATH}"
                command = f"curl --resolve {ANTI_SANCTION_TEST_DOMAIN}:443:{destination_ip} {url}  -H \"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0\" -f -s -o nul"
                process = subprocess.run(command, capture_output=True, text=True, shell=True)
                if process.returncode == 0:
                    logging.info(f"Successfully connected to epic at {destination_ip} using {dns_ip})")
                    successful_resolutions[anti_sanction_dns["name"]] = True
                    self.change_anti_sanction(index)
                    self._window.evaluate_js(f"document.getElementById('dns_select').value={index + 1};")
                    self._window.evaluate_js("adjustWidth(document.getElementById('dns_select'));")
                    return
            except Exception as error:
                logging.error(f"Failed to try dns server {anti_sanction_dns} with error: {error}")
        logging.error("None of anti sanction servers worked, falling back to first one...")
        self.change_anti_sanction(0)
        self._window.evaluate_js("document.getElementById('dns_select').value=1;")

    def process_dns_request(self, data, client_address, dns_socket):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket:
            upstream_socket.sendto(data, (self._cache_ip, 53))
            response_data_bytes, _ = upstream_socket.recvfrom(512)
            response_data = bytearray(response_data_bytes)
            start = response_data.find(SEARCH_IP_BYTES)
            if start != -1:
                response_data[start:start+len(SEARCH_IP_BYTES)] = self._local_ip_bytes
                response_data_bytes = bytes(response_data)
            elif self._anti_sanction_dns != self._cache_ip:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket_second:
                    upstream_socket_second.sendto(data, (self._anti_sanction_dns, 53))
                    response_data_bytes, _ = upstream_socket_second.recvfrom(512)
            dns_socket.sendto(response_data_bytes, client_address)

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
        self._dns_running = False
        logging.info("DNS server stopped.")

    def set_window(self, window):
        self._window = window

    def submit_token(self, token, change_window = True):
        self._token = token
        success = False
        user_data = {}
        try:
            response = requests.get(f"https://{API_DOMAIN}/get_user?token=" + self._token)
            success = bool(response.status_code == 200)
            user_data = json.loads(response.content)
        except Exception as error:
            logging.error(f"Failed to get user data: {error}")
        

        if not success:
            if self._window:
                if user_data.get('status') == 'inactive':
                    expired = True
                    subscription_id = user_data["subscription_id"]
                    self._window.evaluate_js(f"document.getElementById('renew-link').setAttribute('href', 'https://steamdl.ir/my-account/view-subscription/{subscription_id}/');")
                    self._window.evaluate_js("document.getElementById('expired').style.display = 'block';")
                else:
                    self._window.evaluate_js("document.getElementById('error').style.display = 'block';")
            return

        self._user_data = json.loads(response.content)
        self._cache_ip = response.headers['X-Server-IP']
        with open("account.txt", "w") as account_file:
            account_file.write(token)

        if change_window:
            self._window.load_url(INDEX_PATH)

    def toggle_autoconnect(self):
        self._auto_connect = not self._auto_connect

    def toggle_proxy(self, running=None):
        local_ip = ""

        if running == None:
            running = self.check_proxy_status()

        if running:
            # Kill proxy:
            logging.info("Killing Proxy...")
            try:
                subprocess.call(['taskkill', '/IM', 'http_proxy.exe', '/T', '/F'], close_fds=True, creationflags=134217728, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            except Exception as e:
                logging.info(f"Failed to kill proxy: {e}")

            # Kill DNS:
            self._dns_running = False

            # Restore system DNS servers:
            logging.info("Restoring system DNS servers...")
            try:
                for network in self._dns_backup:
                    if len(self._dns_backup[network]) > 1:
                        configure_network_dns("change", network, self._dns_backup[network])
                    else:
                        configure_network_dns("clear", network)
            except Exception as e:
                logging.error(f"Failed to restore system DNS servers: {e}")

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
            try:
                dns_backup = self._dns_backup = get_all_networks_and_dns_servers()
                for network in dns_backup:
                    configure_network_dns("change", network, (local_ip, "1.1.1.1"))
            except Exception as e:
                logging.error(f"Failed to change system DNS servers: {e}")

        return local_ip


    def check_proxy_status(self):
        if self._proxy_process:
            old_ip = self._local_ip
            new_ip = self.get_default_interface_ip()
            if self._proxy_process.poll() == None and old_ip == new_ip and self._dns_running:
                return True
            elif self._proxy_process.poll() == None:
                if not self._dns_running:
                    logging.info("DNS server is not running, killing proxy...")
                else:
                    logging.info(f"Default interface ip has changed, old ip: {old_ip} - new ip: {new_ip}. killing proxy...")
                self.toggle_proxy(True)
            else:
                logging.info("Proxy server is not running.")

        return False

    def get_user_data(self):
        logging.info("User Data: " + str(self._user_data))
        return self._user_data

    def get_rx(self):
        try:
            if os.path.isfile('rx.txt'):
                with open('rx.txt', 'r') as rx_file:
                    rx = int(rx_file.read().strip())
                    return rx
        except Exception as e:
            logging.error(f"Failed to read rx: {e}")
        return 0

    def minimize(self):
        self._window.minimize()

    def close(self):
        self._window.destroy()

    def get_version(self):
        return CURRENT_VERSION

def get_scaling_factor():
    hdc = ctypes.windll.user32.GetDC(0)
    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 = LOGPIXELSX
    ctypes.windll.user32.ReleaseDC(0, hdc)
    return dpi / 96.0  # Default DPI is 96

if __name__ == '__main__':
    api = Api()

    update_available, download_url = check_for_update()
    if update_available:
        def progress_callback(progress):
            window.evaluate_js(f'updateProgress({progress})')

        update_thread = threading.Thread(target=apply_update, args=(download_url, progress_callback))
        update_thread.start()

        window = webview.create_window(WINDOW_TITLE, UPDATE_PATH, width=300,height=210,js_api=api, frameless=True)
    else:
        if os.path.isfile("steamdl_installer.exe"):
            os.remove("steamdl_installer.exe")

        if os.path.isfile("account.txt"):
            with open("account.txt", "r") as account_file:
                token = account_file.read().strip()
                if token:
                    api.submit_token(token, False)
        # print(ctypes.windll.shcore.GetScaleFactorForDevice(0), get_scaling_factor())
        if api._user_data:
            subprocess.call(['taskkill', '/IM', 'http_proxy.exe', '/T', '/F'], close_fds=True, creationflags=134217728, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            window = webview.create_window(WINDOW_TITLE, INDEX_PATH, width=400,height=695,js_api=api, frameless=True)
            # 695 -> 655 100%
            # 695 -> 806 125%
            # 695 -> 952 150%
            # 695 -> 1102 150%
            api.set_window(window) 
        else:
            window = webview.create_window(WINDOW_TITLE, FORM_PATH, width=400,height=675,js_api=api, frameless=True)
            api.set_window(window)

    try:
        webview.start(debug=True)
    except Exception as e:
        logging.error(f"Failed to start webview: {e}")
    finally:
        # Quit:
        time.sleep(0.5)
        cleanup_temp_folders()
        if api.check_proxy_status():
            api.toggle_proxy()

        sys.exit()




