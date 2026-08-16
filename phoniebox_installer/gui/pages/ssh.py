"""SSH credentials page — connect, then run and show the system check."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QScrollArea, QWidget,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.gui.widgets import CustomCheckBox
from phoniebox_installer.app.events import SshEvents, WizardEvents, CheckEvents
from phoniebox_installer.installer.checks import CHECKS


class SshCredentialsPage(BasePage):
    page_id = "ssh"
    title = "Connect to Your Raspberry Pi"
    subtitle = "Enter your SSH credentials and test the connection."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._pending_auto_advance = False
        self._check_results = {}
        self._check_done = False
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
        self._show_pw_checkbox = CustomCheckBox("Show")
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

        # Pressing Enter in any field tests the connection (like the button).
        self._username_input.returnPressed.connect(self._test_connection)
        self._password_input.returnPressed.connect(self._test_connection)
        self._key_input.returnPressed.connect(self._test_connection)

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

        # System check results (run automatically after a successful connect).
        self._check_status = QLabel("")
        self._check_status.setWordWrap(True)
        layout.addWidget(self._check_status)

        # One check per line, styled like the connection status above.
        self._check_label = QLabel("")
        self._check_label.setWordWrap(True)
        layout.addWidget(self._check_label)

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
        self.event_bus.subscribe(CheckEvents.CHECK_COMPLETED, self._on_check_completed)

        if self.state.ssh_authenticated:
            # Re-entering the page: refresh the system check results.
            self._set_status(f"✅ Connected to {self.state.target_host}", "green")
            self._run_system_check()
        else:
            self._set_status("", "black")
            self._reset_check_results()

    def _on_connecting(self, payload):
        self._set_status("⏳ Connecting...", "blue")

    def _on_connected(self, payload):
        self._set_status(f"✅ Connected to {payload.get('host', '')}", "green")
        # Run the system check immediately after a successful connection.
        self._run_system_check()

    def _on_auth_failed(self, payload):
        self._pending_auto_advance = False
        self._set_status("❌ Authentication failed. Check credentials.", "red")

    def _on_error(self, payload):
        self._pending_auto_advance = False
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
        reply = QMessageBox.question(
            self,
            "Host Key Changed",
            f"The host key for '{payload.get('host', '')}' has changed.\n\n"
            f"New key type: {payload.get('key_type', 'unknown')}\n"
            f"New fingerprint (SHA256): {payload.get('fingerprint', 'unknown')}\n\n"
            f"This can happen after re-flashing the Raspberry Pi's OS.\n"
            f"Accept the new key and continue connecting?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if self.controller is not None:
            self.controller.confirm_host_key(reply == QMessageBox.Yes)

    def _on_host_key_rejected(self, payload):
        self._pending_auto_advance = False
        self._set_status("❌ Connection cancelled (host key not trusted).", "red")

    def _on_check_completed(self, payload):
        self._check_results.update(payload)
        self._check_done = True
        self._update_check_results()

        fails = self._critical_fails()
        if fails:
            self._check_status.setText(f"❌ Critical checks failed: {', '.join(fails)}")
            self._pending_auto_advance = False
        else:
            self._check_status.setText("✅ System checks passed.")
            if self._pending_auto_advance:
                self._pending_auto_advance = False
                self.event_bus.publish(WizardEvents.ADVANCE, {"page_id": self.page_id})

    def _update_check_results(self):
        status = self._check_results.get("status", {})
        lines = []
        for key, label, _, _ in CHECKS:
            value = str(self._check_results.get(key, ""))
            st = status.get(key, "pending")
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "pending": "⏳"}[st]
            lines.append(f"{icon} {label} -> {value}")
        self._check_label.setText("\n".join(lines))

    def _critical_fails(self):
        status = self._check_results.get("status", {})
        return [k for k, _, _, _ in CHECKS if status.get(k) == "fail"]

    def _run_system_check(self):
        self._check_done = False
        self._check_status.setText("Running system checks…")
        self._check_label.setText("\n".join(
            f"⏳ {label} -> …" for _, label, _, _ in CHECKS
        ))
        if self.controller is not None:
            self.controller.run_system_check()
        else:
            self._check_status.setText("⚠️ Controller not available.")

    def _reset_check_results(self):
        self._check_results = {}
        self._check_done = False
        self._check_status.setText("")
        self._check_label.setText("")

    def validate(self):
        if not self._username_input.text().strip():
            return (False, "Username must not be empty.")
        if not self._password_input.text() and not self._key_input.text().strip():
            return (False, "Please enter a password or select an SSH key.")
        if not self.state.ssh_authenticated:
            if not self._pending_auto_advance:
                # Auto-test on "Next" instead of asking the user to test
                # manually. The page advances automatically on success.
                self._test_connection()
                self._pending_auto_advance = True
            return (False, "")
        if not self._check_done:
            return (False, "System check is still running…")
        fails = self._critical_fails()
        if fails:
            return (False, f"Critical checks failed: {', '.join(fails)}")
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
        self.event_bus.unsubscribe(CheckEvents.CHECK_COMPLETED, self._on_check_completed)
