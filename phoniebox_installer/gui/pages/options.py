"""Installation options page."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QCheckBox, QComboBox, QGroupBox, QScrollArea, QWidget,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.util.validation import parse_github_branch_url

RFID_READERS = [
    "pn532_i2c_py532",
    "rc522_spi",
    "rdm6300_serial",
    "mfrc522_i2c",
    "generic_nfcpy",
    "generic_usb",
]

HIFIBERRY_BOARDS = [
    "hifiberry-dacplus",
    "hifiberry-digi",
    "hifiberry-dac",
    "hifiberry-amp",
]

WEBAPP_BUNDLE_MODES = ["release-only", "true"]


class OptionsPage(BasePage):
    page_id = "options"
    title = "Configure Your Installation"
    subtitle = "Customize how Phoniebox is installed."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # ---- Phoniebox Source ----
        source_group = QGroupBox("Phoniebox Source")
        source_layout = QVBoxLayout(source_group)
        source_layout.addWidget(QLabel("Branch URL (paste to auto-fill fork + branch):"))
        self._git_url_input = QLineEdit()
        self._git_url_input.setPlaceholderText(
            "https://github.com/<owner>/RPi-Jukebox-RFID/tree/<branch>"
        )
        self._git_url_input.editingFinished.connect(self._on_url_changed)
        source_layout.addWidget(self._git_url_input)
        source_layout.addWidget(QLabel("Git Project/Fork:"))
        self._git_fork_input = QLineEdit("MiczFlor")
        source_layout.addWidget(self._git_fork_input)
        source_layout.addWidget(QLabel("Git Branch:"))
        self._git_branch_input = QLineEdit("future3/main")
        source_layout.addWidget(self._git_branch_input)
        layout.addWidget(source_group)

        # ---- System Options ----
        sys_group = QGroupBox("System Options")
        sys_layout = QVBoxLayout(sys_group)
        self._static_ip_checkbox = self._add_checkbox(sys_layout, "Static IP", True)
        self._ipv6_checkbox = self._add_checkbox(sys_layout, "Disable IPv6", True)
        self._autohotspot_checkbox = self._add_checkbox(sys_layout, "Autohotspot", False)
        self._bluetooth_checkbox = self._add_checkbox(sys_layout, "Disable Bluetooth", True)
        self._onboard_audio_checkbox = self._add_checkbox(
            sys_layout, "Disable on-chip audio", False
        )
        self._mpd_checkbox = self._add_checkbox(sys_layout, "Setup MPD", True)
        self._mpd_overwrite_checkbox = self._add_checkbox(sys_layout, "Overwrite MPD config", True)
        self._update_os_checkbox = self._add_checkbox(sys_layout, "Update OS", False)
        layout.addWidget(sys_group)

        # ---- Services ----
        services_group = QGroupBox("Services")
        services_layout = QVBoxLayout(services_group)

        rfid_row = QHBoxLayout()
        self._rfid_checkbox = QCheckBox("RFID Reader")
        self._rfid_checkbox.setChecked(True)
        rfid_row.addWidget(self._rfid_checkbox)
        self._rfid_reader_combo = QComboBox()
        self._rfid_reader_combo.addItem("Select reader…", "")
        for reader in RFID_READERS:
            self._rfid_reader_combo.addItem(reader, reader)
        rfid_row.addWidget(self._rfid_reader_combo, stretch=1)
        services_layout.addLayout(rfid_row)

        self._samba_checkbox = self._add_checkbox(services_layout, "Samba", False)
        self._webapp_checkbox = self._add_checkbox(services_layout, "WebApp", True)
        self._kiosk_checkbox = self._add_checkbox(
            services_layout, "Kiosk Mode (full-screen WebUI)", False
        )
        layout.addWidget(services_group)

        # ---- Audio ----
        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout(audio_group)
        audio_layout.addWidget(QLabel("HiFiBerry Board:"))
        self._hifiberry_combo = QComboBox()
        self._hifiberry_combo.addItem("None", "")
        for board in HIFIBERRY_BOARDS:
            self._hifiberry_combo.addItem(board, board)
        audio_layout.addWidget(self._hifiberry_combo)
        audio_layout.addWidget(QLabel("ℹ️  Select the audio HAT overlay (optional)"))
        layout.addWidget(audio_group)

        # ---- WebApp bundle / advanced ----
        adv_group = QGroupBox("Advanced")
        adv_layout = QVBoxLayout(adv_group)
        adv_layout.addWidget(QLabel("WebApp bundle:"))
        self._webapp_bundle_combo = QComboBox()
        for mode in WEBAPP_BUNDLE_MODES:
            self._webapp_bundle_combo.addItem(mode, mode)
        adv_layout.addWidget(self._webapp_bundle_combo)
        self._advanced_btn = QPushButton("Erweitert...")
        adv_layout.addWidget(self._advanced_btn)
        layout.addWidget(adv_group)

        layout.addStretch()

        self._wire_dependencies()

    def _add_checkbox(self, layout, label, default):
        cb = QCheckBox(label)
        cb.setChecked(default)
        layout.addWidget(cb)
        return cb

    def _wire_dependencies(self):
        self._rfid_checkbox.toggled.connect(
            lambda checked: self._rfid_reader_combo.setEnabled(checked)
        )
        self._webapp_checkbox.toggled.connect(self._on_webapp_toggled)
        self._autohotspot_checkbox.toggled.connect(self._on_autohotspot_toggled)

    def _on_webapp_toggled(self, checked):
        self._kiosk_checkbox.setEnabled(checked)
        if not checked:
            self._kiosk_checkbox.setChecked(False)

    def _on_autohotspot_toggled(self, checked):
        # Static IP and Autohotspot are mutually exclusive.
        if checked:
            self._static_ip_checkbox.setChecked(False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        """Pre-fill fields from state (restore on back-navigation)."""
        self._git_fork_input.setText(self.state.git_user)
        self._git_branch_input.setText(self.state.git_branch)
        self._static_ip_checkbox.setChecked(self.state.enable_static_ip)
        self._ipv6_checkbox.setChecked(self.state.disable_ipv6)
        self._autohotspot_checkbox.setChecked(self.state.enable_autohotspot)
        self._bluetooth_checkbox.setChecked(self.state.disable_bluetooth)
        self._onboard_audio_checkbox.setChecked(self.state.disable_onboard_audio)
        self._mpd_checkbox.setChecked(self.state.setup_mpd)
        self._mpd_overwrite_checkbox.setChecked(self.state.enable_mpd_overwrite_install)
        self._update_os_checkbox.setChecked(self.state.update_raspi_os)
        self._rfid_checkbox.setChecked(self.state.enable_rfid_reader)
        self._samba_checkbox.setChecked(self.state.enable_samba)
        self._webapp_checkbox.setChecked(self.state.enable_webapp)
        self._kiosk_checkbox.setChecked(self.state.enable_kiosk_mode)
        self._set_combo_data(self._rfid_reader_combo, self.state.rfid_reader_module)
        self._set_combo_data(self._hifiberry_combo, self.state.audio_hifiberry_board)
        self._set_combo_data(self._webapp_bundle_combo, self.state.enable_webapp_prod_download)

    def _set_combo_data(self, combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_url_changed(self):
        """Fill fork + branch fields from a pasted GitHub branch URL."""
        url = self._git_url_input.text().strip()
        if not url:
            return
        parsed = parse_github_branch_url(url)
        if parsed is None:
            return
        owner, _, branch = parsed
        self._git_fork_input.setText(owner)
        if branch:
            self._git_branch_input.setText(branch)

    def validate(self):
        if not self._git_fork_input.text().strip():
            return (False, "Git fork must not be empty.")
        if not self._git_branch_input.text().strip():
            return (False, "Git branch must not be empty.")
        url = self._git_url_input.text().strip()
        if url:
            parsed = parse_github_branch_url(url)
            if parsed is None:
                return (False, "Could not parse the branch URL. Use a GitHub URL like "
                               "https://github.com/<owner>/RPi-Jukebox-RFID/tree/<branch>.")
            _, repo, _ = parsed
            if repo != "RPi-Jukebox-RFID":
                return (False, f"The URL points to repository '{repo}', but the "
                               "installer installs RPi-Jukebox-RFID. Please use a "
                               "URL for RPi-Jukebox-RFID.")
        if self._rfid_checkbox.isChecked() and not self._rfid_reader_combo.currentData():
            return (False, "RFID reader is enabled — please select a reader type "
                           "or disable the RFID reader.")
        return (True, "")

    def on_leave(self):
        """Save all field values back to state."""
        self.state.git_user = self._git_fork_input.text().strip()
        self.state.git_branch = self._git_branch_input.text().strip()
        self.state.enable_static_ip = self._static_ip_checkbox.isChecked()
        self.state.disable_ipv6 = self._ipv6_checkbox.isChecked()
        self.state.enable_autohotspot = self._autohotspot_checkbox.isChecked()
        self.state.disable_bluetooth = self._bluetooth_checkbox.isChecked()
        self.state.disable_onboard_audio = self._onboard_audio_checkbox.isChecked()
        self.state.setup_mpd = self._mpd_checkbox.isChecked()
        self.state.enable_mpd_overwrite_install = self._mpd_overwrite_checkbox.isChecked()
        self.state.update_raspi_os = self._update_os_checkbox.isChecked()
        self.state.enable_rfid_reader = self._rfid_checkbox.isChecked()
        self.state.rfid_reader_module = self._rfid_reader_combo.currentData() or ""
        self.state.enable_samba = self._samba_checkbox.isChecked()
        self.state.enable_webapp = self._webapp_checkbox.isChecked()
        self.state.enable_kiosk_mode = self._kiosk_checkbox.isChecked()
        self.state.audio_hifiberry_board = self._hifiberry_combo.currentData() or ""
        self.state.enable_webapp_prod_download = (
            self._webapp_bundle_combo.currentData() or "release-only"
        )
