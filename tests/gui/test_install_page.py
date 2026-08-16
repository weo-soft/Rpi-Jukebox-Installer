"""Tests for the InstallPage."""

from PySide6.QtWidgets import QMessageBox

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.install import InstallPage


class _FakeController:
    def __init__(self):
        self.cancel_requests = 0
        self.install_starts = 0

    def request_cancel(self):
        self.cancel_requests += 1

    def start_install(self):
        self.install_starts += 1


def _make_page(controller=None):
    state = InstallerState()
    bus = EventBus()
    return InstallPage(state, bus, controller=controller)


def test_log_appends_output_lines(qapp):
    """INSTALL_OUTPUT lines appear in the log."""
    page = _make_page()
    page._on_output({"line": "Cloning repository..."})
    assert "Cloning repository..." in page._log.toPlainText()


def test_progress_bar_updates(qapp):
    """INSTALL_PROGRESS updates the phase label."""
    page = _make_page()
    page._on_progress({"step": "Configuring MPD..."})
    assert page._phase_label.text() == "Configuring MPD..."


def test_cancel_button_shows_dialog(qapp, monkeypatch):
    """Cancel button requests cancellation after confirmation."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

    page._on_cancel_clicked()

    assert controller.cancel_requests == 1


def test_next_disabled_during_install(qapp):
    """validate() blocks while installation is in progress."""
    page = _make_page()
    page.state.install_success = False
    valid, _ = page.validate()
    assert valid is False


def test_next_enabled_after_completion(qapp):
    """validate() passes after installation completes."""
    page = _make_page()
    page.state.install_success = True
    valid, _ = page.validate()
    assert valid is True
