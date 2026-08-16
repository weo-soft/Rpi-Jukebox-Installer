"""Tests for the SshCredentialsPage."""

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QLineEdit, QMessageBox

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.events import SshEvents
from phoniebox_installer.gui.pages.ssh import SshCredentialsPage


class _FakeController:
    def __init__(self):
        self.test_calls = 0
        self.host_key_confirms = []

    def test_connection(self):
        self.test_calls += 1

    def confirm_host_key(self, accept):
        self.host_key_confirms.append(accept)


def _make_page(controller=None):
    state = InstallerState(target_host="192.168.1.100")
    bus = EventBus()
    return SshCredentialsPage(state, bus, controller=controller)


def test_validate_fails_before_test_connection(qapp):
    """validate() blocks until the connection has been tested."""
    page = _make_page()
    page._username_input.setText("pi")
    page._password_input.setText("secret")
    valid, _ = page.validate()
    assert valid is False


def test_validate_fails_with_empty_username(qapp):
    """Empty username → validation fails."""
    page = _make_page()
    page._username_input.setText("")
    page._password_input.setText("secret")
    page.state.ssh_authenticated = True
    valid, _ = page.validate()
    assert valid is False


def test_validate_fails_without_password_or_key(qapp):
    """Neither password nor key → validation fails."""
    page = _make_page()
    page._username_input.setText("pi")
    page._password_input.setText("")
    page._key_input.setText("")
    page.state.ssh_authenticated = True
    valid, _ = page.validate()
    assert valid is False


def test_validate_passes_after_successful_connection(qapp):
    """Valid credentials + authenticated → validation passes."""
    page = _make_page()
    page._username_input.setText("pi")
    page._password_input.setText("secret")
    page.state.ssh_authenticated = True
    valid, _ = page.validate()
    assert valid is True


def test_test_connection_triggers_ssh_connect(qapp):
    """'Test Connection' calls the controller and saves credentials to state."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._username_input.setText("pi")
    page._password_input.setText("secret")

    page._test_connection()

    assert controller.test_calls == 1
    assert page.state.ssh_user == "pi"
    assert page.state.ssh_password == "secret"


def test_show_hide_password_toggle(qapp):
    """Show/hide checkbox toggles password echo mode."""
    page = _make_page()
    assert page._password_input.echoMode() == QLineEdit.Password
    page._show_pw_checkbox.setChecked(True)
    assert page._password_input.echoMode() == QLineEdit.Normal


def test_status_updates_on_events(qapp):
    """CONNECTED event updates the status label."""
    page = _make_page()
    page.on_enter()
    page.event_bus.publish(SshEvents.CONNECTED, {"host": "1.2.3.4"})
    QCoreApplication.processEvents()
    assert "Connected" in page._status_label.text()
    page.on_leave()


def test_host_key_unknown_shows_prompt(qapp, monkeypatch):
    """HOST_KEY_UNKNOWN → prompt, 'Yes' confirms the key."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

    page._on_host_key_unknown(
        {"host": "h", "key_type": "ssh-ed25519", "fingerprint": "abc"}
    )

    assert controller.host_key_confirms == [True]


def test_host_key_confirm_calls_controller(qapp, monkeypatch):
    """HOST_KEY_UNKNOWN → prompt, 'No' rejects the key."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)

    page._on_host_key_unknown(
        {"host": "h", "key_type": "ssh-ed25519", "fingerprint": "abc"}
    )

    assert controller.host_key_confirms == [False]


def test_host_key_changed_shows_error(qapp):
    """HOST_KEY_CHANGED → warning in the status label."""
    page = _make_page()
    page._on_host_key_changed({"host": "1.2.3.4"})
    assert "Host key changed" in page._status_label.text()
