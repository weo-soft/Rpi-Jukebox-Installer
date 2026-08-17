"""Tests for the SummaryPage."""

from PySide6.QtWidgets import QHBoxLayout

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


def _columns_layout(page):
    """Return the top-level QHBoxLayout holding the two summary columns."""
    content = page.layout().itemAt(0).widget().widget()
    main = content.layout()
    for i in range(main.count()):
        item = main.itemAt(i)
        if item.layout() is not None and isinstance(item.layout(), QHBoxLayout):
            return item.layout()
    return None


def test_summary_laid_out_in_two_columns(qapp):
    """Summary groups are split into two side-by-side columns.

    Left: the target machine (merged mode/system) and the git source.
    Right: the configuration choices. The existing-install action is a
    separate full-width container at the top (not part of a column).
    """
    page = _make_page()
    columns = _columns_layout(page)
    assert columns is not None
    assert columns.count() == 2

    left = columns.itemAt(0).layout()
    left_titles = [
        left.itemAt(i).widget().title()
        for i in range(left.count())
        if left.itemAt(i).widget()
    ]
    assert "Target & System" in left_titles
    assert "Git Source" in left_titles

    right = columns.itemAt(1).layout()
    right_titles = [
        right.itemAt(i).widget().title()
        for i in range(right.count())
        if right.itemAt(i).widget()
    ]
    assert "Options" in right_titles
    assert "Audio" in right_titles
    # The existing-install action is not tucked inside a column.
    assert "Existing Installation" not in right_titles
    assert "Existing Installation" not in left_titles

    # The merged container still keeps mode and system as separate labels.
    assert "mode" in page._summary_labels
    assert "system" in page._summary_labels
    assert page._summary_labels["mode"] is not page._summary_labels["system"]


def test_existing_installation_full_width_above_columns(qapp):
    """The existing-install action spans the full width above the columns."""
    page = _make_page()
    content = page.layout().itemAt(0).widget().widget()
    main = content.layout()

    # Order in the main vertical layout: warning, existing group, columns.
    children = [
        main.itemAt(i).widget()
        for i in range(main.count())
        if main.itemAt(i).widget()
    ]
    assert children[0] is page._warning_label
    assert children[1] is page._existing_group
    # The columns layout follows the existing group.
    assert _columns_layout(page) is not None

    # When shown, it spans the full width (not a column half).
    page.state.existing_installation = True
    page.on_enter()
    page.show()
    qapp.processEvents()
    assert page._existing_group.isVisible()

    # Measure against the scroll content, not the page: depending on the
    # platform and Qt version the content may be wider than the viewport
    # (font metrics, scrollbars), but the group always stretches to the
    # full content width.
    margins = main.contentsMargins()
    usable = content.width() - margins.left() - margins.right()
    ratio = page._existing_group.width() / usable
    assert ratio >= 0.9, f"existing group spans only {ratio:.0%} of the content width"

    # The group is centered in the content (equal left/right margins).
    left_gap = page._existing_group.x() - margins.left()
    right_gap = (content.width() - page._existing_group.x()
                 - page._existing_group.width()) - margins.right()
    assert abs(left_gap) <= 2.0 and abs(right_gap) <= 2.0, \
        f"existing group off-center in content (left gap {left_gap}, right gap {right_gap})"


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
