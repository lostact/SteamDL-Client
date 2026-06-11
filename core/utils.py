"""Utility functions for SteamDL Client"""
import subprocess
import logging
import os


def run_cmd(command):
    """Execute a command and return the result"""
    return subprocess.run(command, capture_output=True, text=True, close_fds=True, creationflags=134217728)


def cleanup_temp_folders():
    """Clean up temporary webview folders"""
    temp_dir = os.environ.get('TEMP')
    if temp_dir:
        for folder_name in os.listdir(temp_dir):
            folder_path = os.path.join(temp_dir, folder_name)
            if os.path.isdir(folder_path) and ("EBWebView" in os.listdir(folder_path)):
                try:
                    run_cmd(['rmdir', '/S', '/Q', folder_path])
                except subprocess.CalledProcessError as e:
                    logging.info(f"Failed to remove webview temp files in {folder_path}: {e}")


def log_uncaught_exceptions(exctype, value, tb):
    """Log uncaught exceptions"""
    logging.error("Uncaught exception", exc_info=(exctype, value, tb))


def is_in_startup():
    """Check if application is in startup"""
    try:
        result = run_cmd(["schtasks", "/Query", "/TN", "steamdl"])
        return result.returncode == 0
    except Exception as e:
        logging.error(f"Error checking startup status: {e}")
        return False


def add_to_startup():
    """Add application to startup"""
    try:
        result = run_cmd(["schtasks", "/Create", "/TN", "steamdl", "/XML", "assets\\startup.xml", "/F"])
        return result.returncode == 0
    except Exception as e:
        logging.error(f"Error adding to startup: {e}")
        return False


def remove_from_startup():
    """Remove application from startup"""
    try:
        result = run_cmd(["schtasks", "/Delete", "/TN", "steamdl", "/F"])
        return result.returncode == 0
    except FileNotFoundError:
        logging.error("The application was not in the startup list.")
        return False
    except Exception as e:
        logging.error(f"Error removing from startup: {e}")
        return False
