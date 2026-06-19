"""Update management for SteamDL Client"""
import os
import subprocess
import logging
import requests
from .config import CURRENT_VERSION, REPO_PATH

def _parse_version(v):
    """Parse a version string like '3.1.6' or '3.2.0-beta.1' into a comparable tuple."""
    # Strip pre-release suffix (e.g. "-beta.1") for numeric comparison
    base = v.lstrip("v").split("-")[0]
    return tuple(map(int, base.split(".")))

def check_for_update(beta=False, mirror_config=None):
    """Check if a new version is available.

    Tries the GitHub Releases API first. If that fails (e.g. connectivity
    issues), falls back to the mirror config fetched from client_config.json.
    """
    # --- 1. Try GitHub ---
    try:
        url = f"https://api.github.com/repos/{REPO_PATH}/releases"
        response = requests.get(url, timeout=5)
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

        current_tuple = _parse_version(CURRENT_VERSION)
        latest_tuple = _parse_version(latest_version)
        logging.info("current version: " + CURRENT_VERSION + " - latest version: " + latest_version)
        if latest_tuple and latest_tuple > current_tuple and download_url:
            return True, download_url
        return False, None
    except Exception as e:
        logging.info(f"GitHub update check failed: {e}")

    # --- 2. Fallback to mirror ---
    if not mirror_config:
        return False, None

    try:
        channel = mirror_config.get("beta") if beta and "beta" in mirror_config else mirror_config.get("stable")
        if not channel:
            return False, None

        mirror_version = channel.get("version")
        mirror_url = channel.get("download_url")
        if not mirror_version or not mirror_url:
            return False, None

        current_tuple = _parse_version(CURRENT_VERSION)
        mirror_tuple = _parse_version(mirror_version)
        logging.info(f"Mirror update check: current={CURRENT_VERSION}, mirror={mirror_version}")
        if mirror_tuple > current_tuple:
            return True, mirror_url
    except Exception as e:
        logging.error(f"Mirror update check failed: {e}")

    return False, None

def apply_update(download_url, progress_callback):
    """Download and apply update"""
    installer_name = "steamdl_installer.msi"
    try:
        response = requests.get(download_url, allow_redirects=True, stream=True, timeout=10)
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
