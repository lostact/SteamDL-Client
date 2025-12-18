"""SteamDL Client - Main Entry Point"""
import sys
import os
import logging
import threading
import webview
import multiprocessing

# Set up exception logging
from core.utils import log_uncaught_exceptions
sys.excepthook = log_uncaught_exceptions

# Import configuration
from core.config import WINDOW_TITLE, INDEX_PATH, FORM_PATH, UPDATE_PATH

# Import API and update functionality
from core.api import Api
from core.updater import check_for_update, apply_update

def main():
    """Main entry point for the application"""
    multiprocessing.freeze_support()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    
    # Create API instance
    api = Api()

    # Check for updates
    updating = False
    if api._preferences["update"] != "off":
        beta = api._preferences["update"] == "beta"
        update_available, download_url = check_for_update(beta)
        if update_available:
            updating = True
            
            def progress_callback(progress):
                window.evaluate_js(f'updateProgress({progress})')

            update_thread = threading.Thread(target=apply_update, args=(download_url, progress_callback))
            update_thread.start()

            window = webview.create_window(
                WINDOW_TITLE, 
                UPDATE_PATH, 
                width=300, 
                height=250, 
                js_api=api, 
                frameless=True
            )

    if not updating:
        # Clean up old installer
        if os.path.isfile("steamdl_installer.exe"):
            os.remove("steamdl_installer.exe")

        # Try to load saved token
        if os.path.isfile("account.txt"):
            with open("account.txt", "r") as account_file:
                token = account_file.read().strip()
                if token:
                    api.submit_token(token, False)
        
        # Create window based on authentication status
        if api._user_data:
            window = webview.create_window(
                WINDOW_TITLE, 
                INDEX_PATH, 
                width=300, 
                height=600, 
                js_api=api, 
                frameless=True, 
                easy_drag=False
            )
            api.set_window(window)
        else:
            window = webview.create_window(
                WINDOW_TITLE, 
                FORM_PATH, 
                width=300, 
                height=600, 
                js_api=api, 
                frameless=True, 
                easy_drag=False
            )
            api.set_window(window)

    # Start the webview
    try:
        webview.start(gui='edgechromium', debug=False)
    except Exception as e:
        logging.error(f"Failed to start webview: {e}")
    finally:
        # Cleanup
        import time
        time.sleep(0.5)
        # from core.utils import cleanup_temp_folders
        # cleanup_temp_folders()
        if api._running:
            api.toggle_proxy()
        sys.exit()

if __name__ == '__main__':
    main()
