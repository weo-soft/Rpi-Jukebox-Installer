"""SSH credentials page."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QCheckBox, QFileDialog, QMessageBox,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import SshEvents


class SshCredentialsPage(BasePage):
    page_id = "ssh"
    title = "Connect to Your Raspberry Pi"
    subtitle = "Enter your SSH credentials and test the connection."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Target
        self._target_label = QLabel("")
        layout.addWidget(self._target_label)

        # Username
        layout.addWidget(QLabel("Username:"))
        self._username_input = QLineEdit("pi")
        layout.addWidget(self._username_input)

        # Password
        layout.addWidget(QLabel("Password:"))
        pw_row = QHBoxLayout()
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.Password)
        pw_row.addWidget(self._password_input)
        self._show_pw_checkbox = QCheckBox("Show")
        self._show_pw_checkbox.toggled.connect(self._toggle_password_visibility)
        pw_row.addWidget(self._show_pw_checkbox)
        layout.addLayout(pw_row)

        # SSH key (optional)
        layout.addWidget(QLabel("SSH Key (optional):"))
        key_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Path to private key")
        key_row.addWidget(self._key_input)
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._browse_key)
        key_row.addWidget(self._browse_btn)
        layout.addLayout(key_row)

        # Test connection
        self._test_btn = QPushButton("🔌  Test Connection")
        self._test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self._test_btn)

        # Status
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Auto-detected hostname
        self._hostname_label = QLabel("")
        layout.addWidget(self._hostname_label)

        layout.addStretch()

    def _toggle_password_visibility(self, checked):
        self._password_input.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select SSH private key")
        if path:
            self._key_input.setText(path)

    def _test_connection(self):
        self._save_to_state()
        if self.controller is not None:
            self.controller.test_connection()
        else:
            self._set_status("⚠️ Controller not available.", "orange")

    def _save_to_state(self):
        self.state.ssh_user = self._username_input.text().strip()
        self.state.ssh_password = self._password_input.text()
        self.state.ssh_key_file = self._key_input.text().strip() or None

    def _set_status(self, text, color):
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color};")

    def on_enter(self):
        self._target_label.setText(f"Target: {self.state.target_host}")
        self._username_input.setText(self.state.ssh_user or "pi")
        self._password_input.setText(self.state.ssh_password)
        if self.state.ssh_key_file:
            self._key_input.setText(self.state.ssh_key_file)

        self.event_bus.subscribe(SshEvents.CONNECTING, self._on_connecting)
        self.event_bus.subscribe(SshEvents.CONNECTED, self._on_connected)
        self.event_bus.subscribe(SshEvents.AUTH_FAILED, self._on_auth_failed)
        self.event_bus.subscribe(SshEvents.ERROR, self._on_error)
        self.event_bus.subscribe(SshEvents.HOST_KEY_UNKNOWN, self._on_host_key_unknown)
        self.event_bus.subscribe(SshEvents.HOST_KEY_CHANGED, self._on_host_key_changed)
        self.event_bus.subscribe(SshEvents.HOST_KEY_REJECTED, self._on_host_key_rejected)

    def _on_connecting(self, payload):
        self._set_status("⏳ Connecting...", "blue")

    def _on_connected(self, payload):
        self._set_status(f"✅ Connected to {payload.get('host', '')}", "green")

    def _on_auth_failed(self, payload):
        self._set_status("❌ Authentication failed. Check credentials.", "red")

    def _on_error(self, payload):
        self._set_status(f"⚠️ {payload.get('error', 'Connection error')}", "orange")

    def _on_host_key_unknown(self, payload):
        reply = QMessageBox.question(
            self,
            "Unknown Host Key",
            f"The authenticity of host '{payload['host']}' can't be established.\n\n"
            f"Key type: {payload['key_type']}\n"
            f"Fingerprint (SHA256): {payload['fingerprint']}\n\n"
            f"Trust this host and continue connecting?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if self.controller is not None:
            self.controller.confirm_host_key(reply == QMessageBox.Yes)

    def _on_host_key_changed(self, payload):
        self._set_status(
            f"⚠️ Host key changed for {payload.get('host', '')} — possible MITM. Aborted.",
            "orange",
        )

    def _on_host_key_rejected(self, payload):
        self._set_status("❌ Connection cancelled (host key not trusted).", "red")

    def validate(self):
        if not self._username_input.text().strip():
            return (False, "Username must not be empty.")
        if not self._password_input.text() and not self._key_input.text().strip():
            return (False, "Please enter a password or select an SSH key.")
        if not self.state.ssh_authenticated:
            return (False, "Please test the connection before continuing.")
        return (True, "")

    def on_leave(self):
        self._save_to_state()
        self.event_bus.unsubscribe(SshEvents.CONNECTING, self._on_connecting)
        self.event_bus.unsubscribe(SshEvents.CONNECTED, self._on_connected)
        self.event_bus.unsubscribe(SshEvents.AUTH_FAILED, self._on_auth_failed)
        self.event_bus.unsubscribe(SshEvents.ERROR, self._on_error)
        self.event_bus.unsubscribe(SshEvents.HOST_KEY_UNKNOWN, self._on_host_key_unknown)
        self.event_bus.unsubscribe(SshEvents.HOST_KEY_CHANGED, self._on_host_key_changed)
        self.event_bus.unsubscribe(SshEvents.HOST_KEY_REJECTED, self._on_host_key_rejected)
