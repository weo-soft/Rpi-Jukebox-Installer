"""Network utilities: mDNS discovery and port scanning."""

import logging
import socket
import threading

from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

from phoniebox_installer.app.events import DiscoveryEvents, DeviceInfo

logger = logging.getLogger(__name__)

MDNS_SERVICE_TYPE = "_ssh._tcp.local."


class MdnsDiscovery:
    """Discovers Raspberry Pis via mDNS/Bonjour (zeroconf).

    mDNS is continuous by nature, but already-present devices answer
    immediately, so the browse is bounded by `timeout` and then signals
    SCAN_COMPLETED.
    """

    def __init__(self, event_bus, timeout: float = 5.0):
        self._event_bus = event_bus
        self._timeout = timeout
        self._zeroconf = None
        self._browser = None

    def scan(self):
        """Start async mDNS scan in background thread."""
        self._event_bus.publish(DiscoveryEvents.SCAN_STARTED, {"method": "mdns"})
        thread = threading.Thread(target=self._scan_sync, daemon=True)
        thread.start()

    def _scan_sync(self):
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(
            self._zeroconf, MDNS_SERVICE_TYPE,
            handlers=[self._on_service_state_change]
        )
        # Bound the browse window, then stop + signal completion.
        threading.Timer(self._timeout, self._finish).start()

    def _finish(self):
        if self._zeroconf is not None:
            self.stop()
        self._event_bus.publish(DiscoveryEvents.SCAN_COMPLETED, {"method": "mdns"})

    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            try:
                info = zeroconf.get_service_info(service_type, name)
            except Exception:
                info = None
            if info:
                addresses = [
                    socket.inet_ntoa(addr) for addr in info.addresses
                ]
                hostname = info.server.rstrip('.')
                for addr in addresses:
                    device = DeviceInfo(
                        ip_address=addr,
                        hostname=hostname,
                        discovery_method="mdns",
                    )
                    self._event_bus.publish(
                        DiscoveryEvents.DEVICE_FOUND,
                        {"device": device}
                    )

    def stop(self):
        if self._browser is not None:
            self._browser.cancel()
            self._browser = None
        if self._zeroconf is not None:
            self._zeroconf.close()
            self._zeroconf = None


class PortScanner:
    """Scans local subnet for hosts with SSH port 22 open."""

    def __init__(self, event_bus, timeout: float = 0.5):
        self._event_bus = event_bus
        self._timeout = timeout

    def scan_subnet(self, subnet: str = None):
        """Start subnet scan in background thread."""
        subnet = subnet or self._detect_subnet()
        thread = threading.Thread(
            target=self._scan_subnet_sync, args=(subnet,), daemon=True
        )
        thread.start()

    def _detect_subnet(self) -> str:
        """Detect local subnet (e.g., 192.168.1)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return '.'.join(ip.split('.')[:3])
        except Exception:
            return '192.168.1'

    def _scan_subnet_sync(self, subnet: str):
        """Synchronous port scan of /24 subnet."""
        logger.info(f"Scanning {subnet}.0/24 for SSH...")
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._timeout)
                result = sock.connect_ex((ip, 22))
                sock.close()
                if result == 0:
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        hostname = ip
                    device = DeviceInfo(
                        ip_address=ip,
                        hostname=hostname,
                        discovery_method="scan",
                    )
                    self._event_bus.publish(
                        DiscoveryEvents.DEVICE_FOUND,
                        {"device": device}
                    )
            except Exception:
                pass

        self._event_bus.publish(DiscoveryEvents.SCAN_COMPLETED, {"method": "scan"})
