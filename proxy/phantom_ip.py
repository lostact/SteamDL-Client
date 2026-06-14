"""Phantom IP address management for transparent proxy.

Adds/removes a private IP address on the Windows Loopback adapter so the
kernel handles TCP connections to the phantom IP locally.

Uses 10.255.255.1 (RFC 1918 private range) so that Steam recognises it
as a LAN address for content-cache detection.
"""
import logging
import subprocess

PHANTOM_IP = "10.255.255.1"
LOOPBACK_INTERFACE = "Loopback"


def setup_phantom_ip():
    """Add phantom IP to loopback adapter. Idempotent.

    Checks if the address already exists (e.g., from a previous crash)
    before adding it.
    """
    try:
        result = subprocess.run(
            ["netsh", "interface", "ip", "show", "addresses", LOOPBACK_INTERFACE],
            capture_output=True, text=True
        )
        if PHANTOM_IP in result.stdout:
            logging.info(f"Phantom IP {PHANTOM_IP} already exists on {LOOPBACK_INTERFACE}")
            return

        subprocess.run(
            [
                "netsh", "interface", "ip", "add", "address",
                LOOPBACK_INTERFACE, PHANTOM_IP, "255.255.255.255"
            ],
            check=True
        )
        logging.info(f"Added phantom IP {PHANTOM_IP} to {LOOPBACK_INTERFACE}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to setup phantom IP: {e}")
        raise RuntimeError(
            f"Could not add phantom IP {PHANTOM_IP} to {LOOPBACK_INTERFACE}. "
            "Ensure the application is running as administrator."
        ) from e


def teardown_phantom_ip():
    """Remove phantom IP from loopback adapter.

    Does not raise if the address is already removed.
    """
    try:
        subprocess.run(
            [
                "netsh", "interface", "ip", "delete", "address",
                LOOPBACK_INTERFACE, PHANTOM_IP
            ],
            check=False
        )
        logging.info(f"Removed phantom IP {PHANTOM_IP} from {LOOPBACK_INTERFACE}")
    except Exception as e:
        logging.warning(f"Failed to teardown phantom IP (non-fatal): {e}")
