"""Device discovery page."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QGroupBox, QProgressBar,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import DiscoveryEvents


class DiscoverPage(BasePage):
    page_id = "discover"
    title = "Find Your Raspberry Pi"
    subtitle = "Discover your Raspberry Pi on the local network."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._devices = []
        self._selected_device = None
        self._completed_methods = set()
        self._active_methods = {"mdns", "scan"}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- Auto-Discovery Section ----
        auto_group = QGroupBox("Automatic Discovery")
        auto_layout = QVBoxLayout(auto_group)

        self._scan_btn = QPushButton("🔍  Scan Network")
        self._scan_btn.clicked.connect(self._start_scan)
        auto_layout.addWidget(self._scan_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        self._progress.setVisible(False)
        auto_layout.addWidget(self._progress)

        self._status_label = QLabel("")
        auto_layout.addWidget(self._status_label)

        self._device_list = QListWidget()
        self._device_list.itemClicked.connect(self._on_device_selected)
        auto_layout.addWidget(self._device_list)

        layout.addWidget(auto_group)

        # ---- Manual Entry Section ----
        manual_group = QGroupBox("Manual Entry")
        manual_layout = QHBoxLayout(manual_group)

        manual_layout.addWidget(QLabel("IP / Hostname:"))
        self._manual_input = QLineEdit()
        self._manual_input.setPlaceholderText("e.g., 192.168.1.100 or phoniebox.local")
        manual_layout.addWidget(self._manual_input)

        layout.addWidget(manual_group)

    def _start_scan(self):
        self._device_list.clear()
        self._devices.clear()
        self._completed_methods = set()
        self._progress.setVisible(True)
        self._status_label.setText("Scanning...")
        if self.controller is not None:
            self.controller.start_discovery()

    def _on_device_found(self, payload):
        device = payload["device"]
        # Deduplicate: the same device may be reported by both mDNS and scan.
        if any(d.ip_address == device.ip_address for d in self._devices):
            return
        self._devices.append(device)
        item = QListWidgetItem(
            f"{device.hostname} — {device.ip_address} ({device.discovery_method})"
        )
        self._device_list.addItem(item)

    def _on_device_selected(self, item):
        idx = self._device_list.row(item)
        self._selected_device = self._devices[idx]

    def on_enter(self):
        self.event_bus.subscribe(DiscoveryEvents.DEVICE_FOUND, self._on_device_found)
        self.event_bus.subscribe(DiscoveryEvents.SCAN_COMPLETED, self._on_scan_completed)
        # Start scan automatically
        self._start_scan()

    def _on_scan_completed(self, payload):
        """Hide the indeterminate progress bar once ALL scans finish."""
        method = payload.get("method")
        if method:
            self._completed_methods.add(method)
        if self._active_methods.issubset(self._completed_methods):
            self._progress.setVisible(False)
            self._status_label.setText("Scan complete.")

    def validate(self):
        # Check manual input first, then selected device
        manual = self._manual_input.text().strip()
        if manual:
            return (True, "")
        if self._selected_device:
            return (True, "")
        return (False, "Please select a device or enter an IP address.")

    def on_leave(self):
        self.event_bus.unsubscribe(DiscoveryEvents.DEVICE_FOUND, self._on_device_found)
        self.event_bus.unsubscribe(DiscoveryEvents.SCAN_COMPLETED, self._on_scan_completed)
        if self.controller is not None:
            self.controller.stop_discovery()
        manual = self._manual_input.text().strip()
        if manual:
            self.state.target_host = manual
        elif self._selected_device:
            self.state.target_host = self._selected_device.ip_address
            self.state.target_hostname = self._selected_device.hostname

