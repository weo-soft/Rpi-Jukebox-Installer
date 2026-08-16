"""Tests for the SystemCheckPage."""

from PySide6.QtCore import QCoreApplication

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.events import CheckEvents
from phoniebox_installer.app.controller import InstallerController
from phoniebox_installer.gui.pages.system_check import SystemCheckPage
from phoniebox_installer.installer.checks import CHECKS


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return SystemCheckPage(state, bus)


def _all_pass_status():
    return {key: "pass" for key, _, _, _ in CHECKS}


def test_all_checks_populated(qapp):
    """All checks appear in the table."""
    page = _make_page()
    assert page._table.rowCount() == len(CHECKS)
    assert len(CHECKS) == 12


def test_validate_blocks_on_failed_critical(qapp):
    """A failed critical check blocks 'Next'."""
    page = _make_page()
    page._results = {
        "status": {"os_version": "fail"},
    }
    valid, _ = page.validate()
    assert valid is False


def test_validate_passes_when_critical_ok(qapp):
    """All critical checks pass → validation passes."""
    page = _make_page()
    page._results = {"status": _all_pass_status()}
    valid, _ = page.validate()
    assert valid is True


def test_disk_free_warn_only_does_not_block(qapp):
    """Disk free < 500MB (warn) does not block."""
    page = _make_page()
    status = _all_pass_status()
    status["disk_free_mb"] = "warn"
    page._results = {"status": status}
    valid, _ = page.validate()
    assert valid is True


def test_git_missing_warn_does_not_block(qapp):
    """Git missing (warn) does not block a fresh installation."""
    page = _make_page()
    status = _all_pass_status()
    status["has_git"] = "warn"
    page._results = {"status": status}
    valid, _ = page.validate()
    assert valid is True


def test_results_stored_in_state(qapp):
    """CHECK_COMPLETED is stored in the controller's state (typed values)."""
    bus = EventBus()
    controller = InstallerController(bus)
    page = SystemCheckPage(controller.get_state(), bus, controller=controller)
    page.on_enter()

    bus.publish(CheckEvents.CHECK_COMPLETED, {
        "os_version": "Debian GNU/Linux 12 (bookworm)",
        "arch": "armv7l",
        "disk_free_mb": 2048,
        "has_git": True,
        "has_internet": True,
        "status": _all_pass_status(),
    })
    QCoreApplication.processEvents()

    state = controller.get_state()
    assert state.os_version == "Debian GNU/Linux 12 (bookworm)"
    assert state.arch == "armv7l"
    assert state.disk_free_mb == 2048
    assert state.has_git is True

    page.on_leave()
