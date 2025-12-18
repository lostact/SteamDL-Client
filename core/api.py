"""API class for SteamDL Client"""
import os
import json
import logging
import time
import threading
import requests
from .config import (
    API_DOMAIN, FILES_DOMAIN, CACHE_DOMAIN, PREFERENCES_PATH,
    ANTI_SANCTION_TEST_DOMAIN, ANTI_SANCTION_TEST_PATH, PROXY_ADDON_PATH, INDEX_PATH
)
from .network import (
    find_programs_listening_on_ports, get_active_adapter, 
    get_dns_settings, set_dns_settings, get_default_interface_ip
)
from .dns_server import DNSServer
from .proxy import build_proxy_args, create_proxy_process
from .utils import (
    run_cmd, validate_dns_ip, optimize_epicgames, 
    is_in_startup, add_to_startup, remove_from_startup, test_anti_sanction
)

class Api:
    """Main API class for managing the SteamDL application"""
    
    def __init__(self):
        self._window = None
        self._token = None
        self._user_data = None
        self._anti_sanction_data = None

        self._cache_ip = None
        self._local_ip = None
        self._anti_sanction_ip = None

        self._proxy_process = None
        self._dns_server = None
        self._running = None
        self._health_check_thread = None
        self._optimized_epicgames = None
        self._active_adapter_name = None
        self._dns_backup = []
        self._preferences = {"auto_connect": False, "dns_server": "automatic", "update": "latest"}
        self.load_preferences()

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

    def show_port_in_use_warning(self):
        """Show warning about ports in use"""
        try:
            programs = find_programs_listening_on_ports()
            if programs:
                programs_list = "\\n".join(programs)
                text = f":برنامه های زیر با نرم افزار استیم دی ال اختلال دارند\\n\\n{programs_list}\\n\\n.لطفا پس از بستن برنامه های فوق دوباره امتحان کنید"
                self._window.evaluate_js(f"alert('{text}')")
        except Exception as e:
            pass

    def optimize_epicgames(self):
        """Optimize Epic Games Launcher settings"""
        self._optimized_epicgames = optimize_epicgames()

    def get_anti_sanction_data(self):
        """Get anti-sanction DNS data"""
        try:
            response = requests.get(f"https://{FILES_DOMAIN}/anti_sanction_dns.json")
            if response:
                self._anti_sanction_data = json.loads(response.content)
                self._anti_sanction_ip = self._anti_sanction_data[0]['ip']
                
                if 'custom_dns_servers' in self._preferences:
                    self._anti_sanction_data.extend(self._preferences['custom_dns_servers'])
                
                return self._anti_sanction_data
        except Exception as e:
            logging.error(f"Failed to get anti sanction data: {e}")

    def change_anti_sanction(self, anti_sanction_name):
        """Change anti-sanction DNS server"""
        if anti_sanction_name:
            for anti_sanction_dns in self._anti_sanction_data:
                if anti_sanction_dns["name"] == anti_sanction_name:
                    self._anti_sanction_ip = anti_sanction_dns["ip"]
                    break
            self._preferences['dns_server'] = anti_sanction_name
            self.save_preferences()

    def change_update_option(self, update_option):
        """Change update option"""
        self._preferences["update"] = update_option
        self.save_preferences()

    def validate_dns_ip(self, ip):
        """Validate DNS IP format"""
        return validate_dns_ip(ip)

    def add_custom_dns(self, persian_name, primary_ip):
        """Add a custom DNS server"""
        is_valid, message = validate_dns_ip(primary_ip)
        if not is_valid:
            return False, message, None
        
        if 'custom_dns_servers' not in self._preferences:
            self._preferences['custom_dns_servers'] = []
        
        name = f"custom_dns_{len(self._preferences['custom_dns_servers']) + 1}"
        counter = 1
        while any(dns['name'] == name for dns in self._preferences['custom_dns_servers']):
            counter += 1
            name = f"custom_dns_{counter}"
        
        custom_dns = {
            'name': name,
            'persian_name': persian_name,
            'ip': primary_ip,
            'is_custom': True
        }
        
        self._preferences['custom_dns_servers'].append(custom_dns)
        self.save_preferences()
        self.get_anti_sanction_data()
        
        return True, "سرور DNS با موفقیت اضافه شد", name

    def edit_custom_dns(self, old_name, persian_name, primary_ip):
        """Edit an existing custom DNS server"""
        is_valid, message = validate_dns_ip(primary_ip)
        if not is_valid:
            return False, message
        
        if 'custom_dns_servers' not in self._preferences:
            return False, "سرور یافت نشد"
        
        for dns in self._preferences['custom_dns_servers']:
            if dns['name'] == old_name:
                dns['persian_name'] = persian_name
                dns['ip'] = primary_ip
                
                self.save_preferences()
                self.get_anti_sanction_data()
                
                return True, "سرور DNS با موفقیت ویرایش شد"
        
        return False, "سرور یافت نشد"

    def delete_custom_dns(self, name):
        """Delete a custom DNS server"""
        if 'custom_dns_servers' not in self._preferences:
            return False, "سرور یافت نشد"
        
        for i, dns in enumerate(self._preferences['custom_dns_servers']):
            if dns['name'] == name:
                self._preferences['custom_dns_servers'].pop(i)
                self.save_preferences()
                self.get_anti_sanction_data()
                
                if self._preferences['dns_server'] == name:
                    self._preferences['dns_server'] = 'automatic'
                    self.save_preferences()
                    if self._window:
                        self._window.evaluate_js("document.getElementById('dns_select').value='automatic';")
                
                return True, "سرور DNS با موفقیت حذف شد"
        
        return False, "سرور یافت نشد"

    def test_anti_sanction(self):
        """Test anti-sanction DNS servers"""
        dns_name, dns_ip = test_anti_sanction(
            self._anti_sanction_data, 
            ANTI_SANCTION_TEST_DOMAIN, 
            ANTI_SANCTION_TEST_PATH, 
            self._window
        )
        self.change_anti_sanction(dns_name)

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
            self._running = False
            logging.info("Stopping Proxy...")
            try:
                self._proxy_process.terminate()
            except Exception as e:
                logging.error(f"Failed to stop proxy: {e}")

            self._dns_server.stop()

            logging.info("Restoring system DNS servers...")
            try:
                set_dns_settings(self._active_adapter_name, self._dns_backup)
            except Exception as e:
                logging.error(f"Failed to restore system DNS servers: {e}")

            logging.info("Enabling IPV6...")
            try:
                run_cmd(["powershell", "-Command", "Enable-NetAdapterBinding", "-Name", f"'{self._active_adapter_name}'", "-ComponentID", "ms_tcpip6"])
            except Exception as e:
                logging.error(f"Failed to enable IPV6: {e}")
            logging.info("Service stopped successfully.")
        else:
            logging.info("Starting Proxy...")
            try:
                token = self._token
                cache_ip = self._cache_ip
                local_ip = self._local_ip = get_default_interface_ip(cache_ip)

                proxy_args = build_proxy_args(CACHE_DOMAIN, cache_ip, local_ip, PROXY_ADDON_PATH, token)
                self._proxy_process = create_proxy_process(proxy_args)
                self._proxy_process.start()
            except Exception as e:
                logging.error(f"Failed to start Proxy: {e}")
                return

            logging.info("Starting DNS server...")
            try:
                self._dns_server = DNSServer(local_ip, cache_ip, self._anti_sanction_ip)
                dns_thread = threading.Thread(target=self._dns_server.start, daemon=True)
                dns_thread.start()
            except Exception as e:
                logging.error(f"Failed to start DNS server: {e}")
                self._proxy_process.terminate()
                return

            logging.info("Changing system DNS servers...")
            try:
                if not self._dns_backup:
                    self._active_adapter_name = get_active_adapter()
                    self._dns_backup = get_dns_settings(self._active_adapter_name)
                set_dns_settings(self._active_adapter_name, [local_ip, "1.1.1.1"])
            except Exception as e:
                logging.error(f"Failed to change system DNS servers: {e}")
                self._proxy_process.terminate()
                self._dns_server.stop()
                return

            logging.info("Disabling IPV6...")
            try:
                run_cmd(["powershell", "-Command", "Disable-NetAdapterBinding", "-Name", f"'{self._active_adapter_name}'", "-ComponentID", "ms_tcpip6"])
            except Exception as e:
                logging.error(f"Failed to disable IPV6: {e}")

            if self._optimized_epicgames == None:
                logging.info("Optimizing epicgames configuration...")
                self._optimized_epicgames = False
                try:
                    self.optimize_epicgames()
                except Exception as e:
                    logging.error(f"Failed to optimize epicgames configuration: {e}")

            self._running = True

            health_check_running = False
            if self._health_check_thread:
                if self._health_check_thread.is_alive():
                    health_check_running = True
            if not health_check_running:
                self._health_check_thread = threading.Thread(target=self.health_check, daemon=True)
                self._health_check_thread.start()

            logging.info("Service started successfully.")
            return local_ip

    def health_check(self):
        """Health check for running services"""
        while self._running:
            running = True
            if not self._proxy_process.is_alive():
                logging.info("Proxy process is not running, switching off...")
                self.show_port_in_use_warning()
                running = False
            elif not self._dns_server.is_running():
                logging.info("DNS server is not running, switching off...")
                running = False
            else:
                old_ip = self._local_ip
                new_ip = get_default_interface_ip(self._cache_ip)
                if old_ip != new_ip:
                    logging.info(f"Default interface ip has changed, old ip: {old_ip} - new ip: {new_ip}. switching off...")
                    running = False
            if not running:
                self._window.evaluate_js("$('#power_button').addClass('disabled')")
                self.toggle_proxy()
                self._window.evaluate_js("$('#power_button').removeClass('on')")
                if self._preferences["auto_connect"]:
                    success = self.toggle_proxy()
                    if success:
                        self._window.evaluate_js("$('#power_button').addClass('on')")
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
        """Close window"""
        self._window.destroy()

    def get_version(self):
        """Get application version"""
        from .config import CURRENT_VERSION
        return CURRENT_VERSION
