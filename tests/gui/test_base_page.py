"""Tests for the BasePage lifecycle defaults."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.base import BasePage


class _ConcretePage(BasePage):
    page_id = "test"
    title = "Test Page"


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return _ConcretePage(state, bus)


def test_default_validate_returns_true(qapp):
    """Default validate() returns (True, '')."""
    page = _make_page()
    assert page.validate() == (True, "")


def test_on_enter_on_leave_commit_noop(qapp):
    """Default lifecycle hooks are no-ops that don't raise."""
    page = _make_page()
    page.on_enter()
    page.on_leave()
    page.commit()


def test_properties_expose_shared_objects(qapp):
    """state/event_bus/controller properties expose the injected objects."""
    state = InstallerState()
    bus = EventBus()
    controller = object()
    page = _ConcretePage(state, bus, controller=controller)
    assert page.state is state
    assert page.event_bus is bus
    assert page.controller is controller
