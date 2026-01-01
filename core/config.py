"""Configuration constants for SteamDL Client"""
import sys
import os

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Version information
CURRENT_VERSION = "2.5.2"
WINDOW_TITLE = f"SteamDL v{CURRENT_VERSION}"
REPO_PATH = "lostact/SteamDL-Client"

# Domain configuration
CACHE_DOMAIN = "dl.steamdl.ir"
API_DOMAIN = "api.steamdl.ir"
FILES_DOMAIN = "files.steamdl.ir"

# Path configuration
PROXY_EXEC_PATH = resource_path('assets\\http_proxy.exe')
PROXY_ADDON_PATH = resource_path('assets\\addon.py')
INDEX_PATH = resource_path('assets\\web\\index.html')
FORM_PATH = resource_path('assets\\web\\form.html')
UPDATE_PATH = resource_path('assets\\web\\update.html')
PREFERENCES_PATH = resource_path('preferences.json')

# Network configuration
SEARCH_IP_BYTES = b"\x7f\x00\x00\x01"  # 127.0.0.1 in bytes
ANTI_SANCTION_TEST_DOMAIN = "www.epicgames.com"
ANTI_SANCTION_TEST_PATH = "/id/api/authenticate"
