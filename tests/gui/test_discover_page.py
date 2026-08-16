"""Tests for the DiscoverPage."""

from PySide6.QtWidgets import QListWidgetItem

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.events import DeviceInfo
from phoniebox_installer.gui.pages.discover import DiscoverPage


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return DiscoverPage(state, bus)


def test_scan_finds_devices(qapp):
    """DEVICE_FOUND events populate the device list."""
    page = _make_page()
    device = DeviceInfo(
        ip_address="192.168.1.100",
        hostname="raspberrypi",
        discovery_method="mdns",
    )
    page._on_device_found({"device": device})
    assert len(page._devices) == 1
    assert page._device_list.count() == 1


def test_scan_deduplicates_devices(qapp):
    """The same device reported by two methods is only added once."""
    page = _make_page()
    mdns = DeviceInfo(ip_address="192.168.1.100", hostname="pi", discovery_method="mdns")
    scan = DeviceInfo(ip_address="192.168.1.100", hostname="pi", discovery_method="scan")
    page._on_device_found({"device": mdns})
    page._on_device_found({"device": scan})
    assert len(page._devices) == 1


def test_manual_ip_validated(qapp):
    """A manually entered IP passes validation."""
    page = _make_page()
    page._manual_input.setText("192.168.1.50")
    valid, _ = page.validate()
    assert valid is True


def test_validate_passes_with_discovered_device(qapp):
    """A selected device passes validation."""
    page = _make_page()
    device = DeviceInfo(ip_address="192.168.1.100")
    page._devices.append(device)
    page._device_list.addItem(QListWidgetItem("raspberrypi — 192.168.1.100"))
    page._selected_device = device
    valid, _ = page.validate()
    assert valid is True


def test_validate_fails_with_no_selection(qapp):
    """No selection → validation fails."""
    page = _make_page()
    valid, msg = page.validate()
    assert valid is False
    assert msg


def test_on_leave_writes_to_state(qapp):
    """on_leave() stores the selected device IP and hostname in state."""
    page = _make_page()
    device = DeviceInfo(ip_address="192.168.1.100", hostname="raspberrypi")
    page._devices.append(device)
    page._selected_device = device
    page.on_leave()
    assert page.state.target_host == "192.168.1.100"
    assert page.state.target_hostname == "raspberrypi"
