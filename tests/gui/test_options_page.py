"""Tests for the OptionsPage."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.options import OptionsPage


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return OptionsPage(state, bus)


def test_default_values_are_set(qapp):
    """Default values match InstallerState defaults."""
    page = _make_page()
    assert page._git_fork_input.text() == "MiczFlor"
    assert page._git_branch_input.text() == "future3/main"
    assert page._static_ip_checkbox.isChecked() is True
    assert page._samba_checkbox.isChecked() is False
    assert page._webapp_checkbox.isChecked() is True


def test_git_fork_branch_required(qapp):
    """Empty git fork or branch → validation fails."""
    page = _make_page()
    page._git_fork_input.setText("")
    valid, _ = page.validate()
    assert valid is False

    page._git_fork_input.setText("MiczFlor")
    page._git_branch_input.setText("")
    valid, _ = page.validate()
    assert valid is False


def test_option_checkboxes_toggle_state(qapp):
    """Checkboxes write their values to state on leave."""
    page = _make_page()
    page._samba_checkbox.setChecked(True)
    page.on_leave()
    assert page.state.enable_samba is True


def test_rfid_reader_type_dropdown(qapp):
    """Selecting an RFID reader updates state.rfid_reader_module."""
    page = _make_page()
    idx = page._rfid_reader_combo.findData("pn532_i2c_py532")
    page._rfid_reader_combo.setCurrentIndex(idx)
    page.on_leave()
    assert page.state.rfid_reader_module == "pn532_i2c_py532"


def test_hifiberry_board_dropdown(qapp):
    """Selecting a HiFiBerry board updates state.audio_hifiberry_board."""
    page = _make_page()
    idx = page._hifiberry_combo.findData("hifiberry-dacplus")
    page._hifiberry_combo.setCurrentIndex(idx)
    page.on_leave()
    assert page.state.audio_hifiberry_board == "hifiberry-dacplus"


def test_kiosk_disabled_without_webapp(qapp):
    """Kiosk mode is disabled (and unchecked) when WebApp is off."""
    page = _make_page()
    page._webapp_checkbox.setChecked(False)
    assert not page._kiosk_checkbox.isEnabled()
    assert not page._kiosk_checkbox.isChecked()


def test_rfid_module_required_when_enabled(qapp):
    """RFID enabled without a reader module → validation fails."""
    page = _make_page()
    page._rfid_checkbox.setChecked(True)
    page._rfid_reader_combo.setCurrentIndex(0)  # placeholder, empty data
    valid, msg = page.validate()
    assert valid is False
    assert msg

    page._rfid_checkbox.setChecked(False)
    valid, _ = page.validate()
    assert valid is True


def test_branch_url_fills_fork_and_branch(qapp):
    """Entering a branch URL auto-fills the fork and branch fields."""
    page = _make_page()
    page._git_url_input.setText(
        "https://github.com/weo-soft/RPi-Jukebox-RFID/"
        "tree/future3/feature/installer-noninteractive-config"
    )
    assert page._git_fork_input.text() == "weo-soft"
    assert page._git_branch_input.text() == "future3/feature/installer-noninteractive-config"
    assert page._url_hint_label.isHidden()


def test_invalid_url_shows_hint(qapp):
    """A non-URL input shows a warning hint at the field."""
    page = _make_page()
    page._git_url_input.setText("not-a-url")
    assert not page._url_hint_label.isHidden()
    assert "Invalid URL" in page._url_hint_label.text()


def test_wrong_repo_url_shows_hint(qapp):
    """A URL for a different repository shows a warning hint."""
    page = _make_page()
    page._git_url_input.setText("https://github.com/weo-soft/SomeOtherRepo/tree/main")
    assert not page._url_hint_label.isHidden()
    assert "SomeOtherRepo" in page._url_hint_label.text()


def test_clearing_url_hides_hint(qapp):
    """Clearing the URL field hides the warning hint again."""
    page = _make_page()
    page._git_url_input.setText("not-a-url")
    assert not page._url_hint_label.isHidden()
    page._git_url_input.setText("")
    assert page._url_hint_label.isHidden()


def test_validate_rejects_invalid_url(qapp):
    """An unparseable branch URL blocks 'Next'."""
    page = _make_page()
    page._git_url_input.setText("not-a-url")
    valid, msg = page.validate()
    assert valid is False
    assert "Could not parse" in msg


def test_validate_rejects_wrong_repo(qapp):
    """A URL for a different repository blocks 'Next'."""
    page = _make_page()
    page._git_url_input.setText("https://github.com/weo-soft/SomeOtherRepo/tree/main")
    valid, msg = page.validate()
    assert valid is False
    assert "RPi-Jukebox-RFID" in msg
