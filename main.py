import webview, sys, os, requests, json, subprocess, threading

from random import choices
from string import ascii_lowercase, digits

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

VERSION = "0.4"
WINDOW_TITLE = "SteamDL v{}".format(VERSION)

SUB_URL = "https://dl.gamegk.ir/sub/"

SINGBOX_PATH = resource_path('assets/sing-box.exe')
INDEX_PATH = resource_path('assets/web/index.html')
FORM_PATH = resource_path('assets/web/form.html')
CONFIG_PATH = resource_path('assets/sing-box.json')

class Api:
    def __init__(self):
        self._window = None
        self._token = None
        self._singbox_process = None

    def set_window(self, window):
        self._window = window

    def set_token(self, token):
        self._token = token

    def save_interface_name(self):
        with open(CONFIG_PATH, "r") as singbox_config_file:
            singbox_config = json.loads(singbox_config_file.read())

        interface_name = "".join(choices(ascii_lowercase, k=3)) + "".join(choices(digits, k=2))
        singbox_config["inbounds"][0]["interface_name"] = interface_name 

        with open(CONFIG_PATH, "w") as singbox_config_file:
            singbox_config_file.write(json.dumps(singbox_config, indent=4))

    def submit_token(self, token):
        self._token = token
        success = api.update_config()
        if not success:
            window.evaluate_js("document.getElementById('error').style.display = 'block';")
            return

        with open("account.txt", "w") as account_file:
            account_file.write(token)

        self.update_index()
        self._window.load_url(INDEX_PATH)

    def toggle_vpn(self):
        running = self.check_vpn_status()
        if running:
            self._singbox_process.terminate()
        else:
            self.save_interface_name()
            self._singbox_process = subprocess.Popen((SINGBOX_PATH + ' run -c ' + CONFIG_PATH), close_fds=True, creationflags=134217728)

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

    def update_index(self):
        html = requests.get(SUB_URL + self._token, headers={'Accept': "text/html"}).text
        with open(INDEX_PATH, "w", encoding="utf-8") as index_file:
            index_file.write(html)
            print("updated index")

    def update_config(self):
        try:
            config_json = json.loads(requests.get(SUB_URL + self._token + "/sing-box").text)
            if config_json:
                with open(CONFIG_PATH, "w") as singbox_config_file:
                    singbox_config_file.write(json.dumps(config_json, indent=4))
                    return True
        except:
            return False

    def update_window(self):
        self.update_index()
        threading.Timer(60, self.update_window).start()

if __name__ == '__main__':
    api = Api()

    success = False
    if os.path.isfile("account.txt"):
        with open("account.txt", "r") as account_file:
            token = account_file.read()
            if token:
                api.set_token(token)
                success = api.update_config()

    if success:
        api.update_index()
        window = webview.create_window(WINDOW_TITLE, INDEX_PATH, width=400,height=600,js_api=api, frameless=True)
        api.set_window(window) 
        threading.Timer(60, api.update_window).start()
    else:
        window = webview.create_window(WINDOW_TITLE, FORM_PATH, width=400,height=600,js_api=api, frameless=True)
        api.set_window(window)

    webview.start()