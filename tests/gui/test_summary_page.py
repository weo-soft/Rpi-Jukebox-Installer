"""Tests for the SummaryPage."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.wizard import Wizard
from phoniebox_installer.gui.pages.summary import SummaryPage
from phoniebox_installer.gui.pages.install import InstallPage


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return SummaryPage(state, bus)


def _all_text(page):
    return " ".join(label.text() for label in page._summary_labels.values())


def test_all_state_fields_displayed(qapp):
    """All state categories are rendered into the summary labels."""
    page = _make_page()
    page.state.target_host = "192.168.1.100"
    page.state.os_version = "Debian GNU/Linux 12 (bookworm)"
    page.state.arch = "armv7l"
    page.state.git_user = "MiczFlor"
    page.state.rfid_reader_module = "pn532_i2c_py532"
    page.on_enter()

    text = _all_text(page)
    assert "192.168.1.100" in text
    assert "Debian GNU/Linux 12 (bookworm)" in text
    assert "armv7l" in text
    assert "MiczFlor" in text
    assert "pn532_i2c_py532" in text


def test_update_mode_warning_shown(qapp):
    """A warning is shown in update mode."""
    page = _make_page()
    page.state.mode = "update"
    page.on_enter()
    assert "Update" in page._warning_label.text()


def test_validate_always_passes(qapp):
    """Summary never blocks 'Next'."""
    page = _make_page()
    assert page.validate() == (True, "")


def test_existing_installation_shows_choice(qapp):
    """An existing installation shows the remove/backup choice (default backup)."""
    page = _make_page()
    page.state.existing_installation = True
    page.on_enter()
    assert not page._existing_group.isHidden()
    assert page._backup_radio.isChecked()
    assert not page._remove_radio.isChecked()


def test_group_hidden_without_existing_installation(qapp):
    """The action choice is hidden when no existing installation was found."""
    page = _make_page()
    page.state.existing_installation = False
    page.on_enter()
    assert page._existing_group.isHidden()


def test_backup_choice_saved_on_leave(qapp):
    """The default backup choice is persisted to state on leave."""
    page = _make_page()
    page.state.existing_installation = True
    page.on_enter()
    page.on_leave()
    assert page.state.existing_install_action == "backup"


def test_remove_choice_saved_on_leave(qapp):
    """Selecting 'Remove' is persisted to state on leave."""
    page = _make_page()
    page.state.existing_installation = True
    page.on_enter()
    page._remove_radio.setChecked(True)
    page.on_leave()
    assert page.state.existing_install_action == "remove"


def test_remove_choice_restored_on_enter(qapp):
    """A previously chosen 'remove' action is restored on re-entry."""
    page = _make_page()
    page.state.existing_installation = True
    page.state.existing_install_action = "remove"
    page.on_enter()
    assert page._remove_radio.isChecked()


def test_next_button_advances_to_install(qapp):
    """'Next' on the summary page advances to the install page."""
    state = InstallerState()
    bus = EventBus()
    wizard = Wizard([SummaryPage, InstallPage], state, bus)
    wizard.set_page(0)
    assert wizard.current_page().page_id == "summary"
    wizard._on_next()
    assert wizard.current_page().page_id == "install"
