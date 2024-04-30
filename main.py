import webview, sys, os, requests, json, subprocess, threading

from random import choices
from string import ascii_lowercase, digits

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

WINDOW_TITLE = 'SteamDL v0.3'

SUB_URL = "https://dl.gamegk.ir/sub/"
DEFAULT_CONFIG_URL = "https://dl.gamegk.ir/app/singbox-config-default.json"

SINGBOX_PATH = resource_path("assets/sing-box.exe")
CONFIG_PATH = resource_path('assets/singbox-config.json')
INDEX_PATH = resource_path('assets/web/index.html')
FORM_PATH = resource_path('assets/web/form.html')


class Api:
    def __init__(self):
        self._window = None
        self._token = None
        self._singbox_process = None

    def set_window(self, window):
        self._window = window

    def set_token(self, token):
        self._token = token

    def get_uuid(self, token):
        try:
            resp = requests.get(SUB_URL + token + "/info")
            account_data = json.loads(resp.content)
            uuid = account_data["proxies"]["vless"]["id"]
            return uuid
        except:
            return


    def save_interface_name(self):
        with open(CONFIG_PATH, "r") as singbox_config_file:
            singbox_config = json.loads(singbox_config_file.read())
        interface_name = "".join(choices(ascii_lowercase, k=3)) + "".join(choices(digits, k=2))
        singbox_config["inbounds"][0]["interface_name"] = interface_name 
        with open(CONFIG_PATH, "w") as singbox_config_file:
            singbox_config_file.write(json.dumps(singbox_config, indent=4))

    def save_uuid(self,uuid):
        with open(CONFIG_PATH, "r") as singbox_config_file:
            singbox_config = json.loads(singbox_config_file.read())
        singbox_config["outbounds"][0]["uuid"] = uuid
        with open(CONFIG_PATH, "w") as singbox_config_file:
            singbox_config_file.write(json.dumps(singbox_config, indent=4))

    def submit_token(self, token):
        with open("account.txt", "w") as account_file:
            account_file.write(token)
        uuid = self.get_uuid(token)
        if not uuid:
            window.evaluate_js("document.getElementById('error').style.display = 'block';")
            return
        self.save_uuid(uuid)
        self._token = token
        self.update_index(token)
        self._window.load_url(INDEX_PATH)

    def toggle_vpn(self):
        running = self.check_vpn_status()
        if running:
            self._singbox_process.terminate()
        else:
            self.save_interface_name()
            CREATE_NO_WINDOW = 134217728
            self._singbox_process = subprocess.Popen((SINGBOX_PATH + ' run -c ' + CONFIG_PATH), close_fds=True, creationflags=CREATE_NO_WINDOW)

        # print("test")
    def check_vpn_status(self):
        if self._singbox_process:
            return self._singbox_process.poll() == None
        else:
            return False

    def close(self):
        running = self.check_vpn_status()
        if running:
            self._singbox_process.terminate()
        self._window.destroy()
        os._exit(1)

    def update_index(self, token):
        html = requests.get(SUB_URL + token, headers={'Accept': "text/html"}).text
        with open(INDEX_PATH, "w", encoding="utf-8") as index_file:
            index_file.write(html)

    def update_config(self):
        try:
            default_config = json.loads(requests.get(DEFAULT_CONFIG_URL).content)
            if default_config:
                with open(CONFIG_PATH, "w") as singbox_config_file:
                    singbox_config_file.write(json.dumps(default_config, indent=4))
        except:
            pass

    def update_window(self):
        self.update_index(self._token)
        window.evaluate_js('window.location.reload()')
        threading.Timer(60, self.update_window).start()

if __name__ == '__main__':
    api = Api()
    token = ""
    uuid = ""
    if os.path.isfile("account.txt"):
        with open("account.txt", "r") as account_file:
            token = account_file.read()

    if token:
        uuid = api.get_uuid(token)

    if uuid:
        api.update_config()
        api.save_uuid(uuid)
        api.set_token(token)
        api.update_index(token)
        window = webview.create_window(WINDOW_TITLE, INDEX_PATH, width=400,height=600,js_api=api, frameless=True)
        api.set_window(window) 
        threading.Timer(60, api.update_window).start()
    else:
        window = webview.create_window(WINDOW_TITLE, FORM_PATH, width=400,height=600,js_api=api, frameless=True)
        api.set_window(window)

    webview.start()