"""API class for SteamDL Client"""
import os
import json
import logging
import time
import threading
import requests
from .config import (
    API_DOMAIN, CONFIG_URL, PREFERENCES_PATH,
    INDEX_PATH
)
from proxy.manager import ProxyManager
from .utils import (
    is_in_startup, add_to_startup, remove_from_startup
)

class Api:
    """Main API class for managing the SteamDL application"""
    
    def __init__(self):
        self._window = None
        self._token = None
        self._user_data = None

        self._cache_ip = None
        self._server_config = None

        self._proxy_manager = None
        self._running = None
        self._health_check_thread = None
        self._update_cancel_event = None
        self._preferences = {"auto_connect": False, "update": "latest", "debug": False}
        self.load_preferences()
        self.fetch_server_config()

    def load_preferences(self):
        """Load preferences from file"""
        if os.path.isfile(PREFERENCES_PATH):
            try:
                with open(PREFERENCES_PATH, 'r') as file:
                    new_preferences = json.load(file)
                    for key in self._preferences:
                        if key not in new_preferences:
                            new_preferences[key] = self._preferences[key]
                    self._preferences = new_preferences
            except Exception as e:
                logging.error(f"Error loading preferences: {e}")

    def get_preferences(self):
        """Get current preferences"""
        return self._preferences

    def save_preferences(self):
        """Save preferences to file"""
        try:
            with open(PREFERENCES_PATH, 'w') as file:
                json.dump(self._preferences, file, indent=4)
        except Exception as e:
            logging.error(f"Error saving preferences: {e}")

    def is_in_startup(self):
        """Check if application is in startup"""
        return is_in_startup()

    def add_to_startup(self):
        """Add application to startup"""
        return add_to_startup()

    def remove_from_startup(self):
        """Remove application from startup"""
        return remove_from_startup()

    def fetch_server_config(self, retries=3):
        """Fetch server configuration including domain patterns."""
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(CONFIG_URL, timeout=5)
                response.raise_for_status()
                self._server_config = response.json()
                self._cache_ip = self._server_config.get("cache_ip")
                return self._server_config
            except Exception as e:
                logging.error(f"Failed to fetch server config (attempt {attempt}/{retries}): {e}")
                if attempt < retries:
                    time.sleep(2)
        return None

    def change_update_option(self, update_option):
        """Change update option"""
        self._preferences["update"] = update_option
        self.save_preferences()

    def set_window(self, window):
        """Set the window instance"""
        self._window = window

    def submit_token(self, token, change_window=True):
        """Submit authentication token"""
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
        """Toggle auto-connect setting"""
        self._preferences["auto_connect"] = not self._preferences["auto_connect"]
        self.save_preferences()

    def toggle_proxy(self):
        """Toggle proxy on/off"""
        if self._running:
            # --- STOP ---
            self._running = False
            logging.info("Stopping Proxy...")
            try:
                self._proxy_manager.stop()
            except Exception as e:
                logging.error(f"Failed to stop proxy: {e}")
            self._proxy_manager = None
            logging.info("Service stopped successfully.")
        else:
            # --- START ---
            logging.info("Starting Proxy...")
            try:
                if not self._server_config:
                    logging.error("Cannot start: server config not available")
                    return
                config = self._server_config

                cache_ip = self._cache_ip

                self._proxy_manager = ProxyManager(
                    config, self._token,
                    debug=self._preferences.get("debug", False),
                )
                self._proxy_manager.start()
            except Exception as e:
                logging.error(f"Failed to start Proxy: {e}")
                return

            self._running = True

            # Start health check
            health_check_running = False
            if self._health_check_thread:
                if self._health_check_thread.is_alive():
                    health_check_running = True
            if not health_check_running:
                self._health_check_thread = threading.Thread(target=self.health_check, daemon=True)
                self._health_check_thread.start()

            logging.info("Service started successfully.")
            return cache_ip

    def health_check(self):
        """Health check for running services"""
        while self._running:
            if not self._proxy_manager.is_alive():
                logging.info("Proxy is not running, switching off...")
                running = False
            else:
                running = True

            if not running:
                self._window.evaluate_js("$('#power_button').addClass('disabled')")
                self.toggle_proxy()
                self._window.evaluate_js("$('#power_button').removeClass('on')")
                self._window.evaluate_js("$('#statusText').text('خاموش').removeClass('status-on status-changing').addClass('status-off')")
                if self._preferences["auto_connect"]:
                    success = self.toggle_proxy()
                    if success:
                        self._window.evaluate_js("$('#power_button').addClass('on')")
                        self._window.evaluate_js("$('#statusText').text('روشن').removeClass('status-off status-changing').addClass('status-on')")
                self._window.evaluate_js("$('#power_button').removeClass('disabled')")
                break
            time.sleep(5)

    def get_user_data(self):
        """Get user data"""
        logging.info("User Data: " + str(self._user_data))
        return self._user_data

    def get_rx(self):
        """Get received bytes count"""
        try:
            if os.path.isfile('rx.txt'):
                with open('rx.txt', 'r') as rx_file:
                    rx = int(rx_file.read().strip())
                    return rx
        except Exception as e:
            logging.error(f"Failed to read rx: {e}")
        return 0

    def minimize(self):
        """Minimize window"""
        self._window.minimize()

    def close(self):
        """Close window and cancel any running update"""
        if self._update_cancel_event:
            self._update_cancel_event.set()
        self._window.destroy()

    def get_version(self):
        """Get application version"""
        from .config import CURRENT_VERSION
        return CURRENT_VERSION
