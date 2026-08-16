"""Tests for the InstallPage."""

from PySide6.QtWidgets import QMessageBox

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.install import InstallPage


class _FakeController:
    def __init__(self):
        self.cancel_requests = 0
        self.install_starts = 0
        self.reboot_calls = 0

    def request_cancel(self):
        self.cancel_requests += 1

    def start_install(self):
        self.install_starts += 1

    def reboot_target(self):
        self.reboot_calls += 1


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


def test_details_toggle_switches_log_source(qapp):
    """The Details checkbox switches between step and detail log views."""
    page = _make_page()
    page._on_output({"line": "step-line"})
    page._on_detail({"line": "detail-line"})

    # Default: show the high-level steps.
    assert "step-line" in page._log.toPlainText()
    assert "detail-line" not in page._log.toPlainText()

    # Toggle to details: show the detailed (tailed) log.
    page._details_checkbox.setChecked(True)
    assert "detail-line" in page._log.toPlainText()
    assert "step-line" not in page._log.toPlainText()

    # Toggle back.
    page._details_checkbox.setChecked(False)
    assert "step-line" in page._log.toPlainText()
    assert "detail-line" not in page._log.toPlainText()


def test_completed_stops_progress_bar(qapp):
    """INSTALL_COMPLETED stops the indeterminate animation (full bar)."""
    page = _make_page()
    page._on_install_started({})
    assert page._progress.maximum() == 0  # indeterminate

    page._on_completed({})

    assert page._progress.maximum() == 100
    assert page._progress.value() == 100
    assert not page._cancel_btn.isEnabled()
    page._timer.stop()


def test_failed_stops_progress_bar(qapp):
    """INSTALL_FAILED stops the indeterminate animation (empty bar)."""
    page = _make_page()
    page._on_install_started({})
    page._on_failed({"error": "boom"})

    assert page._progress.maximum() == 100
    assert page._progress.value() == 0
    assert not page._cancel_btn.isEnabled()


def test_completed_starts_reboot_countdown(qapp):
    """INSTALL_COMPLETED shows the auto-reboot countdown on the install page."""
    page = _make_page()
    page._on_completed({})

    assert page._timer.isActive()
    assert "30 s" in page._countdown_label.text()
    assert not page._countdown_label.isHidden()
    assert not page._restart_now_btn.isHidden()
    page._timer.stop()


def test_restart_now_reboots_immediately(qapp):
    """'Restart Now' forces the reboot and stops the countdown."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._on_completed({})
    page._restart_now()
    assert controller.reboot_calls == 1
    assert not page._timer.isActive()


def test_countdown_reaches_zero_and_reboots(qapp):
    """When the countdown hits zero the Pi is rebooted automatically."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page._on_completed({})
    page._timer.stop()
    page._countdown_remaining = 1
    page._tick()
    assert controller.reboot_calls == 1
    assert "Restarting" in page._countdown_label.text()


def test_cancel_reboot_prevents_reboot(qapp):
    """'Cancel Restart' stops the countdown and blocks the reboot on commit."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page.state.install_success = True
    page._on_completed({})
    page._cancel_reboot()
    assert not page._timer.isActive()
    page.commit()
    assert controller.reboot_calls == 0


def test_commit_forces_reboot_when_pending(qapp):
    """Finishing the wizard while the countdown is pending still reboots."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page.state.install_success = True
    page._on_completed({})
    page.commit()
    assert controller.reboot_calls == 1


def test_failed_hides_reboot_countdown(qapp):
    """INSTALL_FAILED does not show the reboot countdown."""
    page = _make_page()
    page._on_failed({"error": "boom"})
    assert page._countdown_label.isHidden()
    assert page._restart_now_btn.isHidden()
    assert not page._timer.isActive()


def test_install_starts_only_once(qapp):
    """Re-entering the install page (e.g. back from finish) does not restart."""
    controller = _FakeController()
    page = _make_page(controller=controller)

    page.on_enter()
    assert controller.install_starts == 1

    page.on_leave()
    page.on_enter()  # back-navigation from the finish page
    assert controller.install_starts == 1
