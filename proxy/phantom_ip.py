"""Phantom IP address management for transparent proxy.

Adds/removes a private IP address on the Windows Loopback adapter so the
kernel handles TCP connections to the phantom IP locally.

Uses 10.255.255.1 (RFC 1918 private range) so that Steam recognises it
as a LAN address for content-cache detection.
"""
import logging
import subprocess

from core.utils import run_cmd

PHANTOM_IP = "10.255.255.1"
LOOPBACK_INTERFACE = "Loopback Pseudo-Interface 1"


def _ps_add_phantom_ip():
    """Fallback: add phantom IP via PowerShell ``New-NetIPAddress``."""
    logging.info("Attempting PowerShell fallback for phantom IP assignment…")
    result = run_cmd([
        "powershell", "-NoProfile", "-Command",
        f"New-NetIPAddress -InterfaceAlias '{LOOPBACK_INTERFACE}' "
        f"-IPAddress {PHANTOM_IP} -PrefixLength 32",
    ])
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, "powershell", result.stdout, result.stderr
        )
    logging.info(f"Added phantom IP {PHANTOM_IP} via PowerShell fallback")


def _ps_remove_phantom_ip():
    """Fallback: remove phantom IP via PowerShell ``Remove-NetIPAddress``."""
    logging.info("Attempting PowerShell fallback for phantom IP removal…")
    result = run_cmd([
        "powershell", "-NoProfile", "-Command",
        f"Remove-NetIPAddress -InterfaceAlias '{LOOPBACK_INTERFACE}' "
        f"-IPAddress {PHANTOM_IP} -PrefixLength 32 "
        f"-Confirm:$false -ErrorAction SilentlyContinue",
    ])
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, "powershell", result.stdout, result.stderr
        )
    logging.info(f"Removed phantom IP {PHANTOM_IP} via PowerShell fallback")


def setup_phantom_ip():
    """Add phantom IP to loopback adapter. Idempotent.

    Checks if the address already exists (e.g., from a previous crash)
    before adding it.  Falls back to PowerShell ``New-NetIPAddress``
    when ``netsh`` fails.
    """
    try:
        result = run_cmd(
            ["netsh", "interface", "ip", "show", "addresses", LOOPBACK_INTERFACE]
        )
        if PHANTOM_IP in result.stdout:
            logging.info(f"Phantom IP {PHANTOM_IP} already exists on {LOOPBACK_INTERFACE}")
            return

        result = run_cmd(
            [
                "netsh", "interface", "ip", "add", "address",
                LOOPBACK_INTERFACE, PHANTOM_IP, "255.255.255.255"
            ]
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, "netsh", result.stdout, result.stderr
            )
        logging.info(f"Added phantom IP {PHANTOM_IP} to {LOOPBACK_INTERFACE}")
    except subprocess.CalledProcessError as e:
        logging.warning(f"netsh failed for phantom IP setup: {e}")
        try:
            _ps_add_phantom_ip()
        except subprocess.CalledProcessError as ps_err:
            logging.error(f"PowerShell fallback also failed: {ps_err}")
            raise RuntimeError(
                f"Could not add phantom IP {PHANTOM_IP} to {LOOPBACK_INTERFACE}. "
                "Ensure the application is running as administrator."
            ) from ps_err


def teardown_phantom_ip():
    """Remove phantom IP from loopback adapter.

    Does not raise if the address is already removed.  Falls back to
    PowerShell ``Remove-NetIPAddress`` when ``netsh`` fails.
    """
    try:
        result = run_cmd(
            [
                "netsh", "interface", "ip", "delete", "address",
                LOOPBACK_INTERFACE, PHANTOM_IP
            ]
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, "netsh", result.stdout, result.stderr
            )
        logging.info(f"Removed phantom IP {PHANTOM_IP} from {LOOPBACK_INTERFACE}")
    except Exception as e:
        logging.warning(f"netsh failed for phantom IP teardown: {e}")
        try:
            _ps_remove_phantom_ip()
        except Exception as ps_err:
            logging.warning(f"PowerShell fallback also failed (non-fatal): {ps_err}")
