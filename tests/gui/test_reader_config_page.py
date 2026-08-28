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


def test_start_session_failure_is_visible(qapp):
    """A failing session start must be shown instead of hanging silently."""

    class _FailingController(_FakeController):
        def start_reader_config_session(self, on_output=None, on_exit=None):
            raise RuntimeError("a session is already active")

    page, _state, bus, _ctrl = _make_page(controller=_FailingController())
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})

    assert "a session is already active" in page._status_label.text()
    assert page._connect_btn.isEnabled() is True
    assert page._session_active is False


def test_output_received_updates_terminal(qapp):
    """Signals from the SSH thread are shown in the terminal widget."""
    page, _state, bus, ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})

    page._output_received.emit("[reader-config] Stopping jukebox-daemon...")
    assert "[reader-config] Stopping jukebox-daemon..." in page._terminal.toPlainText()


def test_no_output_warning_shows_message(qapp):
    """The no-output watchdog reports a possibly stuck session."""
    page, _state, bus, _ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})

    page._on_no_output()
    assert "No output received" in page._status_label.text()
    assert "may be stuck" in page._terminal.toPlainText()


def test_no_output_timer_stops_after_session_exit(qapp):
    """The watchdog is stopped once the session ends."""
    page, _state, bus, _ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})
    assert page._no_output_timer.isActive() is True

    page._on_session_exited(0)
    assert page._no_output_timer.isActive() is False


def test_output_from_ssh_thread_reaches_terminal(qapp):
    """Output emitted from a non-GUI thread is displayed (queued signal)."""
    import threading
    import time
    from PySide6.QtCore import QCoreApplication

    page, _state, bus, _ctrl = _make_page()
    page.on_enter()
    bus.publish(SshEvents.CONNECTED, {"host": "phoniebox.local"})

    def _emit():
        time.sleep(0.05)
        page._output_received.emit("[reader-config] Starting tool...\n")

    threading.Thread(target=_emit, daemon=True).start()

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if "[reader-config] Starting tool..." in page._terminal.toPlainText():
            break
        time.sleep(0.02)

    assert "[reader-config] Starting tool..." in page._terminal.toPlainText()
