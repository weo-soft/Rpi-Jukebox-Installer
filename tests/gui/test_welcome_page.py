"""Tests for the WelcomePage."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.welcome import WelcomePage


def _make_page(mode="new"):
    state = InstallerState(mode=mode)
    bus = EventBus()
    return WelcomePage(state, bus)


def test_initial_state_no_selection(qapp):
    """No mode is pre-selected before entering the page."""
    page = _make_page()
    assert page._selected_mode is None


def test_select_new_sets_mode(qapp):
    """Selecting 'new' stores the mode and checks the button."""
    page = _make_page()
    page._select_mode("new")
    assert page._selected_mode == "new"
    assert page._new_btn.isChecked()


def test_update_option_disabled(qapp):
    """The 'Update Existing' card is disabled in v1."""
    page = _make_page()
    assert not page._update_btn.isEnabled()


def test_validate_fails_without_selection(qapp):
    """validate() fails when no mode has been selected."""
    page = _make_page()
    valid, msg = page.validate()
    assert valid is False
    assert msg


def test_validate_passes_with_selection(qapp):
    """validate() passes once a mode is selected."""
    page = _make_page()
    page._select_mode("new")
    valid, _ = page.validate()
    assert valid is True


def test_on_leave_writes_to_state(qapp):
    """on_leave() persists the selected mode to state."""
    page = _make_page()
    page._select_mode("new")
    page.on_leave()
    assert page.state.mode == "new"


def test_on_enter_restores_previous_selection(qapp):
    """on_enter() restores the previously stored mode."""
    page = _make_page(mode="new")
    page.on_enter()
    assert page._selected_mode == "new"
    assert page._new_btn.isChecked()
