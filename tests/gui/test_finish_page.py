"""Tests for the FinishPage."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.finish import FinishPage


class _FakeController:
    def __init__(self):
        self.reboot_calls = 0

    def reboot_target(self):
        self.reboot_calls += 1


def _make_page(controller=None):
    state = InstallerState()
    bus = EventBus()
    return FinishPage(state, bus, controller=controller)


def test_success_ui_shows_webapp_url(qapp):
    """Success UI shows the webapp URL."""
    page = _make_page()
    page.state.install_success = True
    page.state.webapp_url = "http://192.168.1.100"
    page.on_enter()
    assert "Installation Complete" in page._headline.text()
    assert "http://192.168.1.100" in page._webapp_link.text()
    assert not page._webapp_link.isHidden()


def test_failure_ui_shows_error(qapp):
    """Failure UI shows the error message."""
    page = _make_page()
    page.state.install_success = False
    page.state.install_message = "Connection lost during apt-get update"
    page.on_enter()
    assert "Installation Failed" in page._headline.text()
    assert "Connection lost during apt-get update" in page._error_label.text()
    assert page._webapp_link.isHidden()


def test_restart_checkbox_sends_reboot(qapp):
    """Restart checkbox triggers a reboot via the controller on commit."""
    controller = _FakeController()
    page = _make_page(controller=controller)
    page.state.install_success = True
    page.on_enter()
    page._restart_checkbox.setChecked(True)
    page.commit()
    assert controller.reboot_calls == 1


def test_webapp_link_opens_browser(qapp, monkeypatch):
    """The webapp link opens the default browser."""
    page = _make_page()
    page.state.webapp_url = "http://192.168.1.100"
    opened = []
    monkeypatch.setattr(
        "phoniebox_installer.gui.pages.finish.QDesktopServices.openUrl",
        lambda url: opened.append(url),
    )
    page._open_webapp()
    assert opened and opened[0].toString() == "http://192.168.1.100"
