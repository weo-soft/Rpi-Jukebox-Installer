"""Tests for the ReaderConfigPage (post-install interactive reader configuration)."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import SshEvents
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.reader_config import ReaderConfigPage


class _FakeController:
    """Records calls; no real SSH involved."""

    def __init__(self):
        self.calls = []

    def needs_reader_config(self):
        return True

    def reconnect_ssh(self):
        self.calls.append("reconnect_ssh")

    def start_reader_config_session(self, on_output=None, on_exit=None):
        self.calls.append(("start_reader_config_session", on_output, on_exit))

    def send_reader_config_input(self, data):
        self.calls.append(("send_reader_config_input", data))

    def stop_reader_config_session(self):
        self.calls.append("stop_reader_config_session")


def _make_page(module="generic_usb", controller=None):
    state = InstallerState()
    state.enable_rfid_reader = True
    state.rfid_reader_module = module
    bus = EventBus()
    ctrl = controller or _FakeController()
    return ReaderConfigPage(state, bus, controller=ctrl), state, bus, ctrl


def test_relevant_only_for_manual_readers(qapp):
    state = InstallerState()
    state.enable_rfid_reader = True
    state.rfid_reader_module = "generic_usb"
    assert ReaderConfigPage.relevant(state) is True

    state.rfid_reader_module = "pn532_i2c_py532"
    assert ReaderConfigPage.relevant(state) is False

    state.rfid_reader_module = "generic_usb"
    state.enable_rfid_reader = False
    assert ReaderConfigPage.relevant(state) is False


def test_on_enter_starts_reconnect(qapp):
    page, _state, _bus, ctrl = _make_page()
    page.on_enter()
    assert ctrl.calls[0] == "reconnect_ssh"


def test_connected_event_starts_session(qapp):
    page, _state, bus, ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})
    assert any(
        isinstance(c, tuple) and c[0] == "start_reader_config_session"
        for c in ctrl.calls
    )


def test_send_input_forwards_line(qapp):
    page, _state, bus, ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})
    page._input.setText("2")
    page._send_input()
    assert ("send_reader_config_input", "2\n") in ctrl.calls


def test_validate_blocks_while_session_active(qapp):
    page, _state, bus, _ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})
    valid, _msg = page.validate()
    assert valid is False

    # After the session exits, validation succeeds again.
    page._on_session_exited(0)
    valid, _msg = page.validate()
    assert valid is True


def test_skip_allows_continue(qapp):
    page, _state, bus, ctrl = _make_page()
    page.on_enter()
    page._skip()
    valid, _msg = page.validate()
    assert valid is True
    assert ctrl.calls[-1] == "stop_reader_config_session"


def test_ssh_error_reenables_connect(qapp):
    page, _state, bus, _ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.AUTH_FAILED, {"host": "x", "reason": "bad password"})
    assert page._connect_btn.isEnabled() is True
    assert "bad password" in page._status_label.text()
