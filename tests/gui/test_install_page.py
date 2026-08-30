"""Tests for the InstallPage."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.install import InstallPage


class _FakeController:
    def __init__(self):
        self.install_starts = 0
        self.reboot_calls = 0

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
    page._timer.stop()


def test_failed_stops_progress_bar(qapp):
    """INSTALL_FAILED stops the indeterminate animation (empty bar)."""
    page = _make_page()
    page._on_install_started({})
    page._on_failed({"error": "boom"})

    assert page._progress.maximum() == 100
    assert page._progress.value() == 0


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
    """Re-entering the install page (e.g. via Back/Next) does not restart."""
    controller = _FakeController()
    page = _make_page(controller=controller)

    page.on_enter()
    assert controller.install_starts == 1

    page.on_leave()
    page.on_enter()  # re-entry after navigating away
    assert controller.install_starts == 1


class _FakeSocket:
    """Fake socket that reports ``connect_ex == 0`` for open addresses."""

    def __init__(self, open_addrs):
        self._open_addrs = open_addrs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def settimeout(self, timeout):
        pass

    def connect_ex(self, address):
        return 0 if address in self._open_addrs else 1


def test_completed_shows_webapp_button(qapp):
    """INSTALL_COMPLETED reveals an enabled 'Open Web Interface' button."""
    page = _make_page()
    assert page._webapp_btn.isHidden()

    page._on_completed({})

    assert not page._webapp_btn.isHidden()
    assert page._webapp_btn.isEnabled()
    page._timer.stop()


def test_reboot_hides_buttons_shows_spinner_and_disables_webapp(qapp):
    """A reboot hides the action buttons, shows a spinner and disables webapp."""
    page = _make_page()
    page._on_completed({})

    page._restart_now()

    assert page._restart_now_btn.isHidden()
    assert page._cancel_reboot_btn.isHidden()
    assert not page._reboot_spinner.isHidden()
    assert not page._webapp_btn.isEnabled()
    assert page._poll_timer.isActive()
    page._poll_timer.stop()


def test_reachable_reenables_webapp_button_after_going_down(qapp):
    """The webapp button re-enables only after the Pi went down and came back."""
    page = _make_page()
    page._on_completed({})
    page._restart_now()

    # Still reachable (reboot hasn't taken effect yet): keep polling.
    page._on_reachable(True)
    assert not page._webapp_btn.isEnabled()
    assert page._poll_timer.isActive()

    # Pi went offline.
    page._on_reachable(False)

    # Pi is back: re-enable, hide spinner, show completion message.
    page._on_reachable(True)
    assert page._webapp_btn.isEnabled()
    assert not page._poll_timer.isActive()
    assert page._reboot_spinner.isHidden()
    assert "Restart complete" in page._countdown_label.text()
    assert "close the installer" in page._countdown_label.text()


def test_cancel_reboot_hides_buttons_and_keeps_webapp_enabled(qapp):
    """Cancelling the reboot hides the action buttons and keeps webapp enabled."""
    page = _make_page()
    page._on_completed({})

    page._cancel_reboot()

    assert page._restart_now_btn.isHidden()
    assert page._cancel_reboot_btn.isHidden()
    assert page._reboot_spinner.isHidden()
    assert page._webapp_btn.isEnabled()
    assert not page._poll_timer.isActive()


def test_check_reachable_true_for_open_port(qapp, monkeypatch):
    """_check_reachable returns True when the web port accepts a connection."""
    page = _make_page()
    page.state.target_host = "192.168.1.60"
    page.state.webapp_url = "http://192.168.1.60"
    monkeypatch.setattr(
        "phoniebox_installer.gui.pages.install.socket.socket",
        lambda family, type: _FakeSocket({("192.168.1.60", 80)}),
    )
    assert page._check_reachable() is True


def test_check_reachable_false_for_closed_port(qapp, monkeypatch):
    """_check_reachable returns False when the web port is closed."""
    page = _make_page()
    page.state.target_host = "192.168.1.60"
    page.state.webapp_url = "http://192.168.1.60"
    monkeypatch.setattr(
        "phoniebox_installer.gui.pages.install.socket.socket",
        lambda family, type: _FakeSocket(set()),
    )
    assert page._check_reachable() is False


def test_on_enter_starts_install_once(qapp):
    """Re-entering without a failure must not restart the install."""
    controller = _FakeController()
    page = _make_page(controller=controller)

    page.on_enter()
    page.on_leave()
    page.on_enter()

    assert controller.install_starts == 1


def test_on_enter_restarts_after_failure(qapp):
    """A failed install is restarted when the page is entered again.

    This is the retry path: the user goes back, changes e.g. the fork/branch,
    and returns — the install must run again with the updated state instead of
    staying stuck in the failed state.
    """
    controller = _FakeController()
    page = _make_page(controller=controller)

    page.on_enter()
    page._on_failed({"error": "install-jukebox.sh does not support --config"})
    page.on_leave()
    page.on_enter()

    assert controller.install_starts == 2


def test_on_enter_does_not_restart_after_success(qapp):
    """A completed install must not be re-run when the page is re-entered."""
    controller = _FakeController()
    page = _make_page(controller=controller)

    page.on_enter()
    page._on_completed({})
    page.on_leave()
    page.on_enter()

    assert controller.install_starts == 1


def test_reachable_after_reboot_shows_completion(qapp):
    """After the reboot the page shows the completion message.

    The RFID reader is configured during the installation, so there is no
    additional post-install step to advance to anymore.
    """
    page = _make_page()

    page._on_completed({})
    page._restart_now()
    page._on_reachable(False)  # Pi went offline during the reboot
    page._on_reachable(True)   # Pi is back online

    assert "close the installer" in page._countdown_label.text()
