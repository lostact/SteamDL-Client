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
CURRENT_VERSION = "3.2.0"
WINDOW_TITLE = f"SteamDL v{CURRENT_VERSION}"
REPO_PATH = "lostact/SteamDL-Client"

# Domain configuration
API_DOMAIN = "api.steamdl.ir"
FILES_DOMAIN = "files.steamdl.ir"

# Server config JSON URL
CONFIG_URL = f"https://{FILES_DOMAIN}/client_config.json"

# Path configuration
ASSETS_DIR = resource_path('assets')
INDEX_PATH = resource_path('assets\\web\\index.html')
FORM_PATH = resource_path('assets\\web\\form.html')
UPDATE_PATH = resource_path('assets\\web\\update.html')
PREFERENCES_PATH = resource_path('preferences.json')
