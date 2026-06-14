"""DNS packet interception and rewriting using pydivert and dnslib.

Intercepts UDP port 53 DNS response packets at the packet level,
rewrites A-records for matching CDN domains to point to the phantom IP,
then re-injects the modified packet.

All matching domains are redirected to the phantom IP. The transparent
proxy handles port 80 (HTTP with header modification) and port 443
(raw TCP passthrough) on the phantom IP.
"""
import logging
import threading

import pydivert
from dnslib import DNSRecord, QTYPE, A

from .patterns import matches_any

logger = logging.getLogger(__name__)

# WinDivert filter: only inbound UDP port 53 responses need to be rewritten.
# Outbound queries (DstPort == 53) are left alone — intercepting them added
# overhead without any benefit because we never modify them.
DNS_FILTER = "udp.SrcPort == 53"


class DNSInterceptor(threading.Thread):
    """Daemon thread that intercepts and rewrites DNS responses.

    Args:
        domain_patterns: List of compiled regex patterns for domains to rewrite.
        phantom_ip: IP address to rewrite matching A-records to.
    """

    daemon = True

    def __init__(self, domain_patterns, phantom_ip):
        super().__init__(name="DNSInterceptor")
        self.domain_patterns = domain_patterns
        self.phantom_ip = phantom_ip
        self._stop_event = threading.Event()
        self._windivert_handle = None

    def run(self):
        """Main loop: intercept DNS packets and rewrite matching responses."""
        logger.info("DNS interceptor started")
        try:
            with pydivert.WinDivert(DNS_FILTER) as w:
                self._windivert_handle = w
                for packet in w:
                    if self._stop_event.is_set():
                        break
                    try:
                        if packet.is_inbound and packet.payload:
                            self._rewrite_dns(packet)
                    except Exception as e:
                        logger.debug(f"DNS packet processing error: {e}")
                    try:
                        w.send(packet)
                    except Exception as e:
                        logger.debug(f"DNS packet send error: {e}")
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"DNS interceptor fatal error: {e}")
        finally:
            self._windivert_handle = None
            logger.info("DNS interceptor stopped")

    def stop(self):
        """Signal the interceptor to stop."""
        self._stop_event.set()
        # Close the WinDivert handle to unblock the iteration
        if self._windivert_handle:
            try:
                self._windivert_handle.close()
            except Exception:
                pass

    def _rewrite_dns(self, packet):
        """Parse DNS response and rewrite A-records for matching domains.

        Also handles domains that resolve through CNAME chains (e.g.
        ``lancache.steamcontent.com``) by checking the original query name —
        if the queried domain matches our patterns, all A-records in the
        answer are rewritten regardless of their ``rr.rname``.

        AAAA (IPv6) records are stripped from matching responses so that
        clients only see the rewritten IPv4 address.

        Args:
            packet: pydivert Packet object containing a DNS response.
        """
        try:
            dns_record = DNSRecord.parse(packet.payload)
        except Exception as e:
            logger.debug(f"Failed to parse DNS packet: {e}")
            return

        # Check if the original query name matches any pattern.
        # This catches domains that resolve via CNAME chains where the
        # final A-record name differs from the query.
        queried_name = str(dns_record.q.qname).rstrip(".")
        query_matches = matches_any(queried_name, self.domain_patterns)

        modified = False
        new_rr = []
        for rr in dns_record.rr:
            name = str(rr.rname).rstrip(".")
            is_match = query_matches or matches_any(name, self.domain_patterns)

            if is_match and rr.rtype == QTYPE.AAAA:
                # Strip AAAA records from matching domains
                logger.debug(f"DNS strip AAAA: {name} (query: {queried_name})")
                modified = True
                continue

            if is_match and rr.rtype == QTYPE.A:
                rr.rdata = A(self.phantom_ip)
                logger.debug(f"DNS rewrite: {name} -> {self.phantom_ip} (query: {queried_name})")
                modified = True

            new_rr.append(rr)

        if modified:
            dns_record.rr = new_rr
            packet.payload = dns_record.pack()
