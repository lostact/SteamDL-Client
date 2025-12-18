"""Update management for SteamDL Client"""
import os
import subprocess
import logging
import requests
from .config import CURRENT_VERSION, REPO_PATH

def check_for_update(beta=False):
    """Check if a new version is available"""
    try:
        url = f"https://api.github.com/repos/{REPO_PATH}/releases"
        response = requests.get(url)
        releases = response.json()
        for release in releases:
            if not release["prerelease"] or beta:
                latest_version = release["tag_name"]
                download_url = None
                for asset in release["assets"]:
                    if asset["name"].endswith(".msi"):
                        download_url = asset["browser_download_url"]
                        break
                break

        current_tuple, latest_tuple = tuple(map(int, (CURRENT_VERSION.split(".")))), tuple(map(int, (latest_version.split("."))))
        logging.info("current version: " + CURRENT_VERSION + " - latest version: " + latest_version)
        if latest_tuple and latest_tuple > current_tuple and download_url:
            return True, download_url
    except Exception as e:
        logging.info(f"Failed to check for update: {e}")

    return False, None

def apply_update(download_url, progress_callback):
    """Download and apply update"""
    installer_name = "steamdl_installer.msi"
    try:
        response = requests.get(download_url, allow_redirects=True, stream=True)
        response.raise_for_status()
        total_size = response.headers.get('content-length')
        if total_size:
            total_size = int(total_size)
            downloaded_size = 0
            temp_path = os.environ.get('TEMP')
            installer_path = os.path.join(temp_path, installer_name)
            logging.info(f"Downloading update to {installer_path}")
            with open(installer_path, "wb") as installer_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        installer_file.write(chunk)
                        done_percent = int(100 * downloaded_size / total_size)
                        progress_callback(done_percent)
            logging.info("Downloading update finished.")
            subprocess.Popen(["msiexec", "/i", installer_path, "/q"], close_fds=True, creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
            os._exit(0)
    except Exception as e:
        logging.error(f"Failed to apply update: {e}")
        return None
