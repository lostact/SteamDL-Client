"""Utility functions for SteamDL Client"""
import subprocess
import logging
import os
import re
import dns.resolver

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

def validate_dns_ip(ip):
    """Validate DNS IP format"""
    ip_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(ip_pattern, ip)
    if not match:
        return False, "فرمت آی پی نامعتبر است"
    
    for octet in match.groups():
        if int(octet) > 255:
            return False, "فرمت آی پی نامعتبر است"
    
    return True, "فرمت آی پی معتبر است"

def optimize_epicgames():
    """Optimize Epic Games Launcher settings"""
    engine_file_dir = os.environ.get('LOCALAPPDATA') + "\\EpicGamesLauncher\\Saved\\Config\\Windows"
    if os.path.isdir(engine_file_dir):
        engine_text = "[HTTP]\nHttpTimeout=10\nHttpConnectionTimeout=10\nHttpReceiveTimeout=10\nHttpSendTimeout=10\n[Portal.BuildPatch]\nChunkDownloads=16\nChunkRetries=20\nRetryTime=0.5"
        engine_file_path = engine_file_dir + "\\Engine.ini"
        with open(engine_file_path, 'w') as file:
            file.write(engine_text)
        return True
    else:
        logging.info("Epicgames installation not found...")
        return False

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

def test_anti_sanction(anti_sanction_data, anti_sanction_test_domain, anti_sanction_test_path, window):
    """Test anti-sanction DNS servers and return the best one"""
    custom_resolver = dns.resolver.Resolver()
    for anti_sanction_dns in anti_sanction_data:
        dns_ip = anti_sanction_dns["ip"]
        dns_name = anti_sanction_dns["name"]
        custom_resolver.nameservers = [dns_ip]
        try:
            destination_ip = str(custom_resolver.resolve(anti_sanction_test_domain, 'A')[0])
            url = f"https://{anti_sanction_test_domain}{anti_sanction_test_path}"
            command = f"curl --resolve {anti_sanction_test_domain}:443:{destination_ip} {url}  -H \"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0\" -f -s -o nul"
            process = run_cmd(command)
            if process.returncode == 0:
                logging.info(f"Successfully connected to epic at {destination_ip} using {dns_ip})")
                if window:
                    window.evaluate_js(f"document.getElementById('dns_select').value=\"{dns_name}\";")
                    window.evaluate_js("adjustWidth(document.getElementById('dns_select'));")
                return dns_name, dns_ip
        except Exception as e:
            logging.error(f"Failed to try dns server {dns_name} with error: {e}")
    
    logging.error("None of anti sanction servers worked, falling back to first one...")
    dns_name = anti_sanction_data[0]['name']
    dns_ip = anti_sanction_data[0]['ip']
    if window:
        window.evaluate_js(f"document.getElementById('dns_select').value=\"{dns_name}\";")
    return dns_name, dns_ip
