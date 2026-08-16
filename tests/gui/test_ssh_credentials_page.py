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
        self.check_calls = 0

    def test_connection(self):
        self.test_calls += 1

    def confirm_host_key(self, accept):
        self.host_key_confirms.append(accept)

    def run_system_check(self):
        self.check_calls += 1


def _make_page(controller=None):
    state = InstallerState(target_host="192.168.1.100")
    bus = EventBus()
    return SshCredentialsPage(state, bus, controller=controller)


def test_validate_auto_tests_connection(qapp):
    """validate() with untested credentials triggers an automatic test."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._username_input.setText("pi")
    page._password_input.setText("secret")

    valid, msg = page.validate()

    assert valid is False
    assert msg == ""  # silent block — no "test manually" prompt
    assert controller.test_calls == 1


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
    """Valid credentials + authenticated + check done → validation passes."""
    page = _make_page()
    page._username_input.setText("pi")
    page._password_input.setText("secret")
    page.state.ssh_authenticated = True
    page._check_done = True
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


def test_enter_in_password_field_tests_connection(qapp):
    """Enter in the password field tests the connection."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._username_input.setText("pi")
    page._password_input.setText("secret")

    page._password_input.returnPressed.emit()

    assert controller.test_calls == 1
    assert page.state.ssh_password == "secret"


def test_enter_in_username_field_tests_connection(qapp):
    """Enter in the username field tests the connection."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._username_input.setText("pi")
    page._password_input.setText("secret")

    page._username_input.returnPressed.emit()

    assert controller.test_calls == 1


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


def test_host_key_changed_shows_prompt(qapp, monkeypatch):
    """HOST_KEY_CHANGED → prompt; 'Yes' accepts the new key."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

    page._on_host_key_changed(
        {"host": "1.2.3.4", "key_type": "ssh-ed25519", "fingerprint": "abc"}
    )

    assert controller.host_key_confirms == [True]


def test_connected_runs_system_check(qapp):
    """CONNECTED triggers the system check (instead of advancing directly)."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page.on_enter()
    page._on_connected({"host": "1.2.3.4"})
    assert controller.check_calls == 1
    page.on_leave()


def test_check_completed_auto_advances_when_pending(qapp):
    """CHECK_COMPLETED (no critical fails) with pending auto-advance publishes ADVANCE."""
    from phoniebox_installer.app.events import WizardEvents
    from phoniebox_installer.installer.checks import CHECKS
    bus = EventBus()
    page = SshCredentialsPage(InstallerState(target_host="1.2.3.4"), bus)
    page._pending_auto_advance = True

    received = []
    bus.subscribe(WizardEvents.ADVANCE, received.append)
    payload = {"status": {key: "pass" for key, _, _, _ in CHECKS}}
    page._on_check_completed(payload)
    QCoreApplication.processEvents()

    assert received == [{"page_id": "ssh"}]


def test_validate_blocks_on_critical_fail(qapp):
    """A critical check failure blocks 'Next' even after authentication."""
    page = _make_page()
    page._username_input.setText("pi")
    page._password_input.setText("secret")
    page.state.ssh_authenticated = True
    page._check_done = True
    page._check_results = {"status": {"os_version": "fail"}}
    valid, msg = page.validate()
    assert valid is False
    assert "os_version" in msg


def test_check_completed_updates_results_label(qapp):
    """CHECK_COMPLETED renders one check per line in the results label."""
    page = _make_page()
    page._on_check_completed({
        "model": "Raspberry Pi 4",
        "status": {"model": "pass"},
    })
    assert "✅ Raspberry Pi Model -> Raspberry Pi 4" in page._check_label.text()


def test_run_system_check_shows_pending_lines(qapp):
    """Running the check shows placeholder lines until results arrive."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._run_system_check()
    assert "⏳" in page._check_label.text()
    assert "Raspberry Pi Model ->" in page._check_label.text()
