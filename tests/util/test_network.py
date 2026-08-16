"""Tests for network utilities (PortScanner)."""

import socket
import time

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import DiscoveryEvents
from phoniebox_installer.util.network import PortScanner


def _pump_until(predicate, timeout=3.0):
    """Pump the Qt event loop until ``predicate()`` is true (or timeout)."""
    from PySide6.QtCore import QCoreApplication
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QCoreApplication.processEvents()
    return bool(predicate())


class _FakeSocket:
    """Fake socket that reports ``connect_ex == 0`` only for open hosts."""

    def __init__(self, open_hosts):
        self._open_hosts = open_hosts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def settimeout(self, timeout):
        pass

    def connect_ex(self, address):
        return 0 if address[0] in self._open_hosts else 1


class TestPortScanner:
    def test_scan_finds_open_ssh_host(self, qapp, monkeypatch):
        """A host with SSH open is reported and the scan signals completion."""
        monkeypatch.setattr(
            socket, "socket",
            lambda family, type: _FakeSocket({"192.168.1.60"}),
        )
        monkeypatch.setattr(
            socket, "gethostbyaddr",
            lambda ip: ("raspberrypi", [], [ip]),
        )

        bus = EventBus()
        scanner = PortScanner(bus)

        found = []
        completed = []
        bus.subscribe(DiscoveryEvents.DEVICE_FOUND, found.append)
        bus.subscribe(DiscoveryEvents.SCAN_COMPLETED, completed.append)

        scanner._scan_subnet_sync("192.168.1")

        assert _pump_until(lambda: bool(found))
        assert [d["device"].ip_address for d in found] == ["192.168.1.60"]
        assert found[0]["device"].hostname == "raspberrypi"
        # SCAN_COMPLETED is published from the calling thread (direct connection).
        assert _pump_until(lambda: bool(completed))
        assert completed == [{"method": "scan"}]
