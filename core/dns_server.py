"""DNS server implementation for SteamDL Client"""
import socket
import threading
import logging
from .config import SEARCH_IP_BYTES

class DNSServer:
    """DNS server that forwards requests and replaces specific IPs"""
    
    def __init__(self, local_ip, cache_ip, anti_sanction_ip):
        self.local_ip = local_ip
        self.cache_ip = cache_ip
        self.anti_sanction_ip = anti_sanction_ip
        self.local_ip_bytes = socket.inet_aton(local_ip)
        self.dns_running = False
        self.dns_socket = None
        
    def process_dns_request(self, data, client_address, dns_socket):
        """Process a single DNS request"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket:
                upstream_socket.sendto(data, (self.cache_ip, 53))
                response_data_bytes, _ = upstream_socket.recvfrom(512)
                response_data = bytearray(response_data_bytes)
                start = response_data.find(SEARCH_IP_BYTES)
                if start != -1:
                    response_data[start:start+len(SEARCH_IP_BYTES)] = self.local_ip_bytes
                    response_data_bytes = bytes(response_data)
                elif self.anti_sanction_ip != self.cache_ip:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream_socket_second:
                        upstream_socket_second.settimeout(0.2)
                        upstream_socket_second.sendto(data, (self.anti_sanction_ip, 53))
                        try:
                            response_data_bytes, _ = upstream_socket_second.recvfrom(512)
                        except socket.timeout:
                            pass
                dns_socket.sendto(response_data_bytes, client_address)
        except Exception as e:
            logging.error(f"Error processing DNS request: {e}")
    
    def start(self):
        """Start the DNS server"""
        self.dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dns_socket.bind((self.local_ip, 53))
        self.dns_socket.settimeout(1)
        self.dns_running = True

        logging.info(f"DNS server listening on {self.local_ip}:53")
        while self.dns_running:
            try:
                data, client_address = self.dns_socket.recvfrom(512)
                client_thread = threading.Thread(target=self.process_dns_request, args=(data, client_address, self.dns_socket))
                client_thread.start()
            except socket.timeout:
                pass
            except Exception as e:
                logging.error(f"DNS server error: {e}")

        self.dns_socket.close()
        self.dns_running = False
        logging.info("DNS server stopped.")
    
    def stop(self):
        """Stop the DNS server"""
        self.dns_running = False
    
    def is_running(self):
        """Check if DNS server is running"""
        return self.dns_running
