import sys, os, requests, json, re, subprocess, threading, multiprocessing, socket, webview, logging, time, dns.resolver 

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

import subprocess

def run_cmd(command):
    return subprocess.run(command, capture_output=True, text=True, close_fds=True, creationflags=134217728)

def find_programs_listening_on_ports():
    results = []
    for port_number in [80,443]:
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
    result = run_cmd(["netsh", "interface", "ipv4", "show", "config"])
    
    if result.returncode != 0:
        logging.error("Failed to get network configuration.")
    
    interface_pattern = r"Configuration for interface \"([\w\s]+)\""
    gateway_pattern = r"Default Gateway:\s+([\d\.]+)"
    
    interfaces = re.finditer(interface_pattern, result.stdout)
    active_adapter = None
    
    for interface in interfaces:
        adapter_name = interface.group(1)
        gateway_match = re.search(gateway_pattern, result.stdout[interface.end():])
        if gateway_match:
            gateway = gateway_match.group(1)
            if gateway and gateway != "0.0.0.0":
                active_adapter = adapter_name
                break

    if active_adapter:
        return active_adapter
    else:
        logging.error("No active adapter with an internet connection found.")

def get_dns_settings():
    adapter_name = get_active_adapter()
    result = run_cmd(["netsh", "interface", "ipv4", "show", "dnsservers", adapter_name])
    if result.returncode != 0:
        logging.error(f"Failed to get DNS settings for adapter: {adapter_name}")
    
    dns_pattern = r"(\d+\.\d+\.\d+\.\d+)"
    dns_servers = re.findall(dns_pattern, result.stdout, re.MULTILINE)
    
    if dns_servers:
        return {adapter_name: dns_servers}
    else:
        logging.error(f"No DNS servers found for adapter: {adapter_name}")

def set_dns_settings(dns_settings):
    for adapter_name in dns_settings:
        run_cmd(["netsh", "interface", "ipv4", "set", "dnsservers", adapter_name, "static", dns_settings[adapter_name][0]])

    # Set secondary DNS if provided
    if len(dns_settings[adapter_name]) > 1:
        run_cmd(["netsh", "interface", "ipv4", "add", "dnsservers", adapter_name, dns_settings[adapter_name][1], "index=2"])

def cleanup_temp_folders():
    temp_dir = os.environ.get('TEMP')
    if temp_dir:
        for folder_name in os.listdir(temp_dir):
            folder_path = os.path.join(temp_dir, folder_name)
            if os.path.isdir(folder_path) and ("EBWebView" in os.listdir(folder_path)):
                try:
                    run_cmd(['rmdir', '/S', '/Q', folder_path])
                except subprocess.CalledProcessError as e:
                    logging.info(f"Failed to remove webview temp files in {folder_path}: {e}")

def start_proxy(mitm_args):
    from mitmproxy.tools.main import mitmdump
    logging.basicConfig(
        level=logging.WARN,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler('proxy.log')
        ]
    )
    mitmdump(args=mitm_args)

CURRENT_VERSION = "2.0.0"
WINDOW_TITLE = f"SteamDL v{CURRENT_VERSION}"
GITHUB_RELEASE_URL = "https://github.com/lostact/SteamDL-Client/releases/latest/download/steamdl_installer.exe"

CACHE_DOMAIN = "dl.steamdl.ir"
API_DOMAIN = "api.steamdl.ir"
FILES_DOMAIN = "files.steamdl.ir"

PROXY_EXEC_PATH = resource_path('assets\\http_proxy.exe')
PROXY_ADDON_PATH = resource_path('assets\\addon.py')
INDEX_PATH = resource_path('assets\\web\\index.html')
FORM_PATH = resource_path('assets\\web\\form.html')
UPDATE_PATH = resource_path('assets\\web\\update.html')
PREFERENCES_PATH = resource_path('preferences.json')

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
        self._anti_sanction_ip = None

        self._proxy_process = None
        self._dns_running = None
        # self._proxy_log_file = None
        self._dns_thread = None
        self._dns_backup = None
        self._preferences = None
        self._port_in_use_warning_shown = None

    def load_preferences(self):
        try:
            with open(PREFERENCES_PATH, 'r') as file:
                self._preferences = json.load(file)
                return self._preferences
        except Exception as e:
            logging.error(f"Error loading preferences: {e}")

    def save_preferences(self):
        try:
            with open(PREFERENCES_PATH, 'w') as file:
                json.dump(self._preferences, file, indent=4)
        except Exception as e:
            logging.error(f"Error saving preferences: {e}")

    def is_in_startup(self):
        try:
            result = run_cmd(["schtasks", "/Query", "/TN", "steamdl"])

            if result.returncode == 0:
                return True
            else:
                return False
        except Exception as e:
            logging.error(f"Error checking startup status: {e}")
            return False

    def add_to_startup(self):
        try:
            result = run_cmd(["schtasks", "/Create", "/TN", "steamdl", "/XML","assets\\startup.xml", "/F"])
            if result.returncode == 0:
                return True
            else:
                return False
        except Exception as e:
            logging.error(f"Error adding to startup: {e}")
            return False

    def remove_from_startup(self):
        try:
            result = run_cmd(["schtasks", "/Delete", "/TN", "steamdl", "/F"])
            if result.returncode == 0:
                return True
            else:
                return False
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
                self._anti_sanction_ip = self._anti_sanction_data[0]['ip']
                return self._anti_sanction_data
        except Exception as e:
            logging.error(f"Failed to get anti sanction data: {e}")

    def change_anti_sanction(self, anti_sanction_name):
        if anti_sanction_name:
            for anti_sanction_dns in self._anti_sanction_data:
                if anti_sanction_dns["name"] == anti_sanction_name:
                    self._anti_sanction_ip = anti_sanction_dns["ip"]
                    break
            self._preferences['dns_server'] = anti_sanction_name
            self.save_preferences()

    def test_anti_sanction(self):
        custom_resolver = dns.resolver.Resolver()
        for index,anti_sanction_dns in enumerate(self._anti_sanction_data):
            dns_ip = anti_sanction_dns["ip"]
            dns_name = anti_sanction_dns["name"]
            custom_resolver.nameservers = [dns_ip]
            try:
                destination_ip = str(custom_resolver.resolve(ANTI_SANCTION_TEST_DOMAIN, 'A')[0])
                self._anti_sanction_ip = dns_ip
                url = f"https://{ANTI_SANCTION_TEST_DOMAIN}{ANTI_SANCTION_TEST_PATH}"
                command = f"curl --resolve {ANTI_SANCTION_TEST_DOMAIN}:443:{destination_ip} {url}  -H \"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0\" -f -s -o nul"
                process = run_cmd(command)
                if process.returncode == 0:
                    logging.info(f"Successfully connected to epic at {destination_ip} using {dns_ip})")
                    self.change_anti_sanction(dns_name)
                    self._window.evaluate_js(f"document.getElementById('dns_select').value=\"{dns_name}\";")
                    self._window.evaluate_js("adjustWidth(document.getElementById('dns_select'));")
                    return
            except Exception as e:
                logging.error(f"Failed to try dns server {dns_name} with error: {e}")
        logging.error("None of anti sanction servers worked, falling back to first one...")
        dns_name = self._anti_sanction_data[0]['name']
        self.change_anti_sanction(dns_name)
        self._window.evaluate_js(f"document.getElementById('dns_select').value=\"{dns_name}\";")

    def process_dns_request(self, data, client_address, dns_socket):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket:
                upstream_socket.sendto(data, (self._cache_ip, 53))
                response_data_bytes, _ = upstream_socket.recvfrom(512)
                response_data = bytearray(response_data_bytes)
                start = response_data.find(SEARCH_IP_BYTES)
                if start != -1:
                    response_data[start:start+len(SEARCH_IP_BYTES)] = self._local_ip_bytes
                    response_data_bytes = bytes(response_data)
                elif self._anti_sanction_ip != self._cache_ip:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket_second:
                        upstream_socket_second.sendto(data, (self._anti_sanction_ip, 53))
                        response_data_bytes, _ = upstream_socket_second.recvfrom(512)
                dns_socket.sendto(response_data_bytes, client_address)
        except Exception as e:
            logging.error(f"Error processing DNS request: {e}")

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
            except Exception as e:
                logging.error(f"DNS server error: {e}")

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
        except Exception as e:
            logging.error(f"Failed to get user data: {e}")
        

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
            # self._window.resize(450,900, fix_point= webview.window.FixPoint.NORTH | webview.window.FixPoint.EAST)
            self._window.load_url(INDEX_PATH)
            

    def toggle_autoconnect(self):
        self._preferences["auto_connect"] = not self._preferences["auto_connect"]
        self.save_preferences()

    def toggle_proxy(self, running=None):
        local_ip = ""

        if running == None:
            running = self.check_proxy_status()

        if running:
            # Kill proxy:
            logging.info("Killing Proxy...")
            try:
                # subprocess.call(['taskkill', '/IM', 'http_proxy.exe', '/T', '/F'], close_fds=True, creationflags=134217728, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self._proxy_process.terminate()
            except Exception as e:
                logging.error(f"Failed to kill proxy: {e}")

            # Kill DNS:
            self._dns_running = False

            # Restore system DNS servers:
            logging.info("Restoring system DNS servers...")
            try:
                set_dns_settings(self._dns_backup)
            except Exception as e:
                logging.error(f"Failed to restore system DNS servers: {e}")

            # Enable ipv6:
            logging.info("Enabling IPV6...")
            try:
                for adapter_name in self._dns_backup:
                    run_cmd(["powershell", "-Command", "Enable-NetAdapterBinding", "-Name", adapter_name, "-ComponentID", "ms_tcpip6"])
            except Exception as e:
                logging.error(f"Failed to disable IPV6: {e}")

        else:
            self._port_in_use_warning_shown = False
            token = self._token
            cache_ip = self._cache_ip
            local_ip = self._local_ip = self.get_default_interface_ip()
            local_ip_bytes = self._local_ip_bytes = socket.inet_aton(local_ip)

            # Run Proxy:
            logging.info("Starting Proxy...")
            self._proxy_process = multiprocessing.Process(target=start_proxy,  args=([['--mode', f"reverse:http://{CACHE_DOMAIN}@{local_ip}:80",
                                                                                       '--mode', f"reverse:tcp://{cache_ip}:443@{local_ip}:443",
                                                                                       '-s', f"\"{PROXY_ADDON_PATH}\"",
                                                                                       '--set', f"allow_hosts={CACHE_DOMAIN}",
                                                                                       '--set', f"token={token}",
                                                                                       '--set', f"keep_host_header=true",
                                                                                       '--set', 'termlog_verbosity=warn',
                                                                                       '--set', 'flow_detail=0',
                                                                                       '--set', 'stream_large_bodies=100k']]))
            self._proxy_process.daemon = True
            self._proxy_process.start()

            # Run DNS reverse proxy:
            logging.info("Starting DNS server...")
            if not self._dns_running:
                dns_thread = self._dns_thread = threading.Thread(target=self.start_dns, daemon=True)
                dns_thread.start()

            # Change system DNS servers:
            logging.info("Changing system DNS servers...")
            try:
                dns_backup = self._dns_backup = get_dns_settings()
                new_dns_settings = {}
                for adapter_name in dns_backup:
                    new_dns_settings[adapter_name] = [local_ip, "1.1.1.1"]
                set_dns_settings(new_dns_settings)
            except Exception as e:
                logging.error(f"Failed to change system DNS servers: {e}")

            # Disable IPV6:
            logging.info("Disabling IPV6...")
            for adapter_name in dns_backup: 
                try:
                    run_cmd(["powershell", "-Command", "Disable-NetAdapterBinding", "-Name", adapter_name, "-ComponentID", "ms_tcpip6"])
                except Exception as e:
                    logging.error(f"Failed to disable IPV6: {e}")

            # Optimize epicgames configuration:
            engine_file_dir = os.environ.get('LOCALAPPDATA') + "\\EpicGamesLauncher\\Saved\\Config\\Windows"
            if os.path.isdir(engine_file_dir):
                logging.info("Optimizing epicgames configuration...")
                engine_text = "[HTTP]\nHttpTimeout=10\nHttpConnectionTimeout=10\nHttpReceiveTimeout=10\nHttpSendTimeout=10\n[Portal.BuildPatch]\nChunkDownloads=16\nChunkRetries=20\nRetryTime=0.5"
                engine_file_path = engine_file_dir + "\\Engine.ini"
                with open(engine_file_path, 'w') as file:
                    file.write(engine_text)
            else:
                logging.info("Epicgames installation not found...")
        return local_ip


    def check_proxy_status(self):
        if self._proxy_process:
            old_ip = self._local_ip
            new_ip = self.get_default_interface_ip()
            if self._proxy_process.is_alive() and old_ip == new_ip and self._dns_running:
                return True
            elif self._proxy_process.is_alive():
                if not self._dns_running:
                    logging.info("DNS server is not running, killing proxy...")
                else:
                    logging.info(f"Default interface ip has changed, old ip: {old_ip} - new ip: {new_ip}. killing proxy...")
                self.toggle_proxy(True)
            else:
                # logging.info("Proxy server is not running.")
                if not self._port_in_use_warning_shown:
                    self._port_in_use_warning_shown = True
                    try:
                        programs = find_programs_listening_on_ports()
                        if programs:
                            programs_list = "\\n".join(programs)
                            text = f":برنامه های زیر با نرم افزار استیم دی ال اختلال دارند\\n\\n{programs_list}\\n\\n.لطفا پس از بستن برنامه های فوق دوباره امتحان کنید"
                            self._window.evaluate_js(f"alert('{text}')")
                    except Exception as e:
                        self._port_in_use_warning_shown = False
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

# def get_scaling_factor():
#     hdc = ctypes.windll.user32.GetDC(0)
#     dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 = LOGPIXELSX
#     ctypes.windll.user32.ReleaseDC(0, hdc)
#     return dpi / 96.0  # Default DPI is 96

if __name__ == '__main__':
    multiprocessing.freeze_support()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
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
        if api._user_data:
            window = webview.create_window(WINDOW_TITLE, INDEX_PATH, width=300,height=600,js_api=api, frameless=True, easy_drag=True)
            api.set_window(window) 
        else:
            window = webview.create_window(WINDOW_TITLE, FORM_PATH, width=300,height=600,js_api=api, frameless=True, easy_drag=False)
            api.set_window(window)

    try:
        webview.start(gui='edgechromium', debug=False)
    except Exception as e:
        logging.error(f"Failed to start webview: {e}")
    finally:
        # Quit:
        time.sleep(0.5)
        # cleanup_temp_folders()
        if api.check_proxy_status():
            api.toggle_proxy()

        sys.exit()




