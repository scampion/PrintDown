"""Zeroconf service discovery for network printer advertising."""
import os
import socket
from zeroconf import ServiceInfo, Zeroconf


def get_local_ip():
    """Get the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


class DiscoveryService:
    """Manages Zeroconf service registration for printer discovery."""
    
    def __init__(self):
        self.zeroconf = None
        self.services = []
    
    def start(self):
        """Register the IPP, text, and image services with Zeroconf."""
        self.zeroconf = Zeroconf()
        ip_address = get_local_ip()
        hostname = socket.gethostname()
        ipp_port = int(os.getenv("IPP_PORT", "6310"))

        # IPP Service
        ipp_info = ServiceInfo(
            "_ipp._tcp.local.",
            f"{hostname}._ipp._tcp.local.",
            addresses=[socket.inet_aton(ip_address)],
            port=ipp_port,
            properties={'rp': 'ipp/print', 'ty': 'PrintDown IPP Printer'},
            server=f"{hostname}.local.",
        )
        self.zeroconf.register_service(ipp_info)
        self.services.append(ipp_info)
        print(f"Registered IPP service on {ip_address}:{ipp_port}")

        # Raw Text Service (Port 9100)
        text_info = ServiceInfo(
            "_pdl-datastream._tcp.local.",
            f"{hostname} Text._pdl-datastream._tcp.local.",
            addresses=[socket.inet_aton(ip_address)],
            port=9100,
            properties={'ty': 'PrintDown Raw Text'},
            server=f"{hostname}.local.",
        )
        self.zeroconf.register_service(text_info)
        self.services.append(text_info)
        print(f"Registered Raw Text service on {ip_address}:9100")

        # Raw Image Service (Port 9101)
        image_info = ServiceInfo(
            "_pdl-datastream._tcp.local.",
            f"{hostname} Image._pdl-datastream._tcp.local.",
            addresses=[socket.inet_aton(ip_address)],
            port=9101,
            properties={'ty': 'PrintDown Raw Image'},
            server=f"{hostname}.local.",
        )
        self.zeroconf.register_service(image_info)
        self.services.append(image_info)
        print(f"Registered Raw Image service on {ip_address}:9101")
    
    def stop(self):
        """Unregister all services and close Zeroconf."""
        if self.zeroconf:
            print("Unregistering services...")
            self.zeroconf.unregister_all_services()
            self.zeroconf.close()
            self.services.clear()

