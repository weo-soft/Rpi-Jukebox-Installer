"""Tests for the OptionsPage."""

from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.options import OptionsPage
from phoniebox_installer.gui.widgets import CollapsibleGroupBox, InfoIcon


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return OptionsPage(state, bus)


def test_default_values_are_set(qapp):
    """Default values match InstallerState defaults."""
    page = _make_page()
    assert page._git_fork_input.text() == "MiczFlor"
    assert page._git_branch_combo.currentText() == "future3/main"
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
    page._git_branch_combo.setCurrentText("")
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
    assert msg  # helpful message, not empty
    page._rfid_checkbox.setChecked(False)
    valid, _ = page.validate()
    assert valid is True


def test_rfid_manual_reader_allows_continue(qapp):
    """Readers without module defaults (e.g. generic_usb) pass validation.

    They are configured in an additional wizard step after installation and
    reboot, so selecting them must not block the wizard.
    """
    page = _make_page()
    idx = page._rfid_reader_combo.findData("generic_usb")
    page._rfid_reader_combo.setCurrentIndex(idx)
    valid, msg = page.validate()
    assert valid is True
    assert msg == ""

    # A reader with module defaults (pn532_i2c_py532) passes validation too
    idx = page._rfid_reader_combo.findData("pn532_i2c_py532")
    page._rfid_reader_combo.setCurrentIndex(idx)
    valid, _ = page.validate()
    assert valid is True


def test_rfid_manual_reader_hint_points_to_additional_step(qapp):
    """The hint for manual readers references the additional wizard step."""
    page = _make_page()
    idx = page._rfid_reader_combo.findData("generic_usb")
    page._rfid_reader_combo.setCurrentIndex(idx)

    text = page._rfid_manual_hint.text()
    assert "additional step" in text
    # The user is not told to configure manually anymore.
    assert "manually" not in text.lower()
    assert "run_register_rfid_reader.py" not in text


def test_rfid_manual_reader_shows_hint(qapp):
    """Selecting a manual-only reader reveals the configuration hint."""
    page = _make_page()
    assert page._rfid_manual_hint.isHidden() is True

    idx = page._rfid_reader_combo.findData("generic_usb")
    page._rfid_reader_combo.setCurrentIndex(idx)
    assert page._rfid_manual_hint.isHidden() is False

    idx = page._rfid_reader_combo.findData("pn532_i2c_py532")
    page._rfid_reader_combo.setCurrentIndex(idx)
    assert page._rfid_manual_hint.isHidden() is True

    # Disabling RFID also hides the hint
    page._rfid_reader_combo.setCurrentIndex(
        page._rfid_reader_combo.findData("generic_usb")
    )
    assert page._rfid_manual_hint.isHidden() is False
    page._rfid_checkbox.setChecked(False)
    assert page._rfid_manual_hint.isHidden() is True


def test_plugin_default_values(qapp):
    """Plugin defaults match InstallerState defaults."""
    page = _make_page()
    assert page._spotify_checkbox.isChecked() is False
    assert page._jellyfin_checkbox.isChecked() is False
    assert page._spotify_redirect_uri_input.text() == (
        "http://127.0.0.1:3000/api/v1/spotify/oauth/callback"
    )
    assert page._spotify_device_name_input.text() == "Phoniebox"


def test_plugin_fields_disabled_until_enabled(qapp):
    """Spotify/Jellyfin inputs are disabled until the plugin is checked."""
    page = _make_page()
    assert not page._spotify_client_id_input.isEnabled()
    assert not page._jellyfin_host_input.isEnabled()

    page._spotify_checkbox.setChecked(True)
    assert page._spotify_client_id_input.isEnabled()

    page._jellyfin_checkbox.setChecked(True)
    assert page._jellyfin_host_input.isEnabled()
    # Default auth mode is the API key → API key input active, user login not.
    assert page._jellyfin_api_key_input.isEnabled()
    assert not page._jellyfin_username_input.isEnabled()


def test_spotify_validation_requires_client_id(qapp):
    """Spotify enabled without a client ID → validation fails."""
    page = _make_page()
    page._rfid_checkbox.setChecked(False)  # satisfy the RFID requirement
    page._spotify_checkbox.setChecked(True)
    page._spotify_client_id_input.setText("")
    valid, _ = page.validate()
    assert valid is False

    page._spotify_client_id_input.setText("abc123")
    valid, _ = page.validate()
    assert valid is True


def test_jellyfin_validation(qapp):
    """Jellyfin enabled requires host and exactly one auth method."""
    page = _make_page()
    page._rfid_checkbox.setChecked(False)  # satisfy the RFID requirement
    page._jellyfin_checkbox.setChecked(True)
    valid, _ = page.validate()
    assert valid is False  # host missing

    page._jellyfin_host_input.setText("http://jellyfin.local:8096")
    # API key mode: key required
    page._jellyfin_api_key_radio.setChecked(True)
    valid, _ = page.validate()
    assert valid is False

    page._jellyfin_api_key_input.setText("jf-key")
    valid, _ = page.validate()
    assert valid is True

    # User login mode: username and password required
    page._jellyfin_user_radio.setChecked(True)
    page._jellyfin_api_key_input.setText("")
    valid, _ = page.validate()
    assert valid is False

    page._jellyfin_username_input.setText("jelly")
    page._jellyfin_password_input.setText("pw")
    valid, _ = page.validate()
    assert valid is True


def test_plugin_state_saved_on_leave(qapp):
    """Plugin fields write their values to state on leave."""
    page = _make_page()
    page._spotify_checkbox.setChecked(True)
    page._spotify_client_id_input.setText("abc123")
    page._spotify_redirect_uri_input.setText("http://127.0.0.1:3000/cb")
    page._spotify_device_name_input.setText("Kitchen")

    page._jellyfin_checkbox.setChecked(True)
    page._jellyfin_host_input.setText("http://jellyfin.local:8096")
    page._jellyfin_user_radio.setChecked(True)
    page._jellyfin_username_input.setText("jelly")
    page._jellyfin_password_input.setText("pw")

    page.on_leave()
    assert page.state.setup_spotify is True
    assert page.state.spotify_client_id == "abc123"
    assert page.state.spotify_redirect_uri == "http://127.0.0.1:3000/cb"
    assert page.state.spotify_device_name == "Kitchen"
    assert page.state.enable_jellyfin is True
    assert page.state.jellyfin_host == "http://jellyfin.local:8096"
    assert page.state.jellyfin_api_key == ""
    assert page.state.jellyfin_username == "jelly"
    assert page.state.jellyfin_password == "pw"


def test_branch_url_fills_fork_and_branch(qapp):
    """Entering a branch URL auto-fills the fork and branch fields."""
    page = _make_page()
    page._git_url_input.setText(
        "https://github.com/weo-soft/RPi-Jukebox-RFID/"
        "tree/future3/feature/installer-noninteractive-config"
    )
    assert page._git_fork_input.text() == "weo-soft"
    assert page._git_branch_combo.currentText() == "future3/feature/installer-noninteractive-config"
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


def test_webapp_bundle_combo_in_source_group(qapp):
    """The WebApp bundle selection lives in the 'Phoniebox Source' group."""
    page = _make_page()
    source_group = next(
        g for g in page.findChildren(QGroupBox) if g.title() == "Phoniebox Source"
    )
    combos = source_group.findChildren(QComboBox)
    assert page._webapp_bundle_combo in combos
    assert page._git_branch_combo in combos  # branch dropdown lives there too


def test_upstream_release_keeps_release_only(qapp):
    """The upstream release branch keeps the 'release-only' default."""
    page = _make_page()
    assert page._webapp_bundle_combo.currentData() == "release-only"

    page._git_fork_input.setText("MiczFlor")
    page._git_branch_combo.setCurrentText("future3/main")
    assert page._webapp_bundle_combo.currentData() == "release-only"


def test_non_upstream_fork_auto_selects_true(qapp):
    """A fork automatically switches the WebApp bundle mode to 'true'."""
    page = _make_page()
    page._git_fork_input.setText("weo-soft")
    page._git_branch_combo.setCurrentText("future3/feature/installer-noninteractive-config")
    assert page._webapp_bundle_combo.currentData() == "true"


def test_non_upstream_branch_auto_selects_true(qapp):
    """A development branch on the upstream user also selects 'true'."""
    page = _make_page()
    page._git_fork_input.setText("MiczFlor")
    page._git_branch_combo.setCurrentText("future3/develop")
    assert page._webapp_bundle_combo.currentData() == "true"


def test_branch_url_auto_selects_true_for_fork(qapp):
    """Pasting a fork URL auto-fills the source and selects 'true'."""
    page = _make_page()
    page._git_url_input.setText(
        "https://github.com/weo-soft/RPi-Jukebox-RFID/"
        "tree/future3/feature/installer-noninteractive-config"
    )
    assert page._git_fork_input.text() == "weo-soft"
    assert page._webapp_bundle_combo.currentData() == "true"


def test_on_enter_non_upstream_state_selects_true(qapp):
    """Restoring a non-upstream source from state selects 'true' too."""
    state = InstallerState(
        git_user="weo-soft",
        git_branch="future3/develop",
        enable_webapp_prod_download="release-only",
    )
    page = OptionsPage(state, EventBus())
    page.on_enter()
    assert page._webapp_bundle_combo.currentData() == "true"


def test_on_leave_persists_auto_selected_bundle(qapp):
    """The auto-selected 'true' mode is written to state on leave."""
    page = _make_page()
    page._git_fork_input.setText("weo-soft")
    page._git_branch_combo.setCurrentText("future3/develop")
    page.on_leave()
    assert page.state.enable_webapp_prod_download == "true"


def test_webapp_bundle_combo_shows_interpretable_names(qapp):
    """The bundle dropdown shows user-facing names, keeping the data values."""
    page = _make_page()
    texts = [page._webapp_bundle_combo.itemText(i)
             for i in range(page._webapp_bundle_combo.count())]
    assert "Upstream / default (release bundle)" in texts
    assert "Fork / branch (development bundle)" in texts
    # The data values are the ENABLE_WEBAPP_PROD_DOWNLOAD contract.
    assert page._webapp_bundle_combo.findData("release-only") >= 0
    assert page._webapp_bundle_combo.findData("true") >= 0
    assert page._webapp_bundle_combo.currentData() == "release-only"


def _completer_names(page):
    model = page._branch_completer.model()
    return [
        model.data(model.index(i, 0))
        for i in range(model.rowCount())
    ]


def test_branch_completer_populated_from_cache(qapp):
    """A cached branch list is applied to the completer immediately."""
    page = _make_page()
    page._branch_cache["MiczFlor"] = ["future3/main", "future3/develop"]
    page._load_branches()
    assert _completer_names(page) == ["future3/main", "future3/develop"]


def test_branch_completer_populated_after_fetch(qapp, monkeypatch):
    """A successful GitHub fetch populates the completer (via signal)."""
    monkeypatch.setattr(
        "phoniebox_installer.gui.pages.options.fetch_github_branches",
        lambda owner: ["future3/main", "future3/develop"],
    )
    page = _make_page()
    page._fetch_branches_sync("MiczFlor")
    assert page._branch_cache["MiczFlor"] == ["future3/main", "future3/develop"]
    assert _completer_names(page) == ["future3/main", "future3/develop"]


def test_branch_completer_empty_on_fetch_failure(qapp, monkeypatch):
    """A failed fetch leaves the completer empty (manual entry fallback)."""
    monkeypatch.setattr(
        "phoniebox_installer.gui.pages.options.fetch_github_branches",
        lambda owner: (_ for _ in ()).throw(OSError("offline")),
    )
    page = _make_page()
    page._fetch_branches_sync("MiczFlor")
    assert _completer_names(page) == []
    assert page._branch_fetch_pending == set()


def test_fork_change_triggers_branch_load(qapp, monkeypatch):
    """Editing the fork field schedules a branch-list reload (debounced)."""
    fetched = []
    monkeypatch.setattr(
        "phoniebox_installer.gui.pages.options.fetch_github_branches",
        lambda owner: fetched.append(owner) or ["future3/develop"],
    )
    page = _make_page()
    page._git_fork_input.setText("weo-soft")
    assert fetched == []  # debounce: not loaded synchronously

    from PySide6.QtTest import QTest
    QTest.qWait(800)
    assert "weo-soft" in fetched
    assert _completer_names(page) == ["future3/develop"]


def _groups_by_title(page):
    return {
        g.title(): g
        for g in page.findChildren(CollapsibleGroupBox)
    }


def _columns_layout(page):
    """Return the top-level QHBoxLayout holding the two option columns."""
    content = page.layout().itemAt(0).widget().widget()
    main = content.layout()
    for i in range(main.count()):
        item = main.itemAt(i)
        if item.layout() is not None and isinstance(item.layout(), QHBoxLayout):
            return item.layout()
    return None


def test_services_audio_left_system_right(qapp):
    """Services+Audio sit left, System Options right (swapped order)."""
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
    assert "Services" in left_titles
    assert "Audio" in left_titles

    right_widget = columns.itemAt(1).widget()
    assert right_widget.title() == "System Options"


def test_rfid_highlight_until_selection(qapp):
    """The RFID combo is flagged (and the hint shown) until a choice is made."""
    page = _make_page()
    assert page._rfid_reader_combo.property("needsSelection") is True
    assert page._rfid_hint.isHidden() is False

    idx = page._rfid_reader_combo.findData("rc522_spi")
    page._rfid_reader_combo.setCurrentIndex(idx)
    assert page._rfid_reader_combo.property("needsSelection") is False
    assert page._rfid_hint.isHidden() is True


def test_rfid_highlight_cleared_when_disabled(qapp):
    """Disabling the RFID reader clears the required-highlight."""
    page = _make_page()
    page._rfid_checkbox.setChecked(False)
    assert page._rfid_reader_combo.property("needsSelection") is False
    assert page._rfid_hint.isHidden() is True


def test_source_group_collapsed_by_default(qapp):
    """The developer-focused Phoniebox Source group starts collapsed."""
    page = _make_page()
    assert _groups_by_title(page)["Phoniebox Source"].is_collapsed()


def test_only_source_group_is_collapsible(qapp):
    """Only the developer-focused Phoniebox Source group is collapsible."""
    page = _make_page()
    groups = _groups_by_title(page)
    assert set(groups) == {"Phoniebox Source"}  # no other collapsible group
    assert groups["Phoniebox Source"].is_collapsed()


def test_collapsible_groups_toggle(qapp):
    """Clicking a group title toggles its content."""
    page = _make_page()
    source = _groups_by_title(page)["Phoniebox Source"]

    source._toggle.click()          # expand
    assert not source.is_collapsed()

    source._toggle.click()          # collapse again
    assert source.is_collapsed()


def test_every_option_entry_has_info_icon(qapp):
    """Each option entry has an info icon with a description tooltip."""
    page = _make_page()
    icons = page.findChildren(InfoIcon)
    # System (8) + Services (Samba, WebApp, Kiosk) + RFID row + Audio +
    # Plugins (Spotify, Jellyfin) + Source (URL, fork, branch, bundle).
    assert len(icons) == 19
    for icon in icons:
        assert icon._description, "info icon without a description"
        assert len(icon._description) > 20, "description too short to be useful"


def test_rfid_combo_shows_reader_names(qapp):
    """The reader dropdown shows display names, the module stays as data."""
    page = _make_page()
    texts = [page._rfid_reader_combo.itemText(i)
             for i in range(page._rfid_reader_combo.count())]
    assert "PN532 reader via I2C using py532 library" in texts
    assert "MFRC522 via SPI" in texts
    assert "pn532_i2c_py532" not in texts  # no python package names

    idx = page._rfid_reader_combo.findData("pn532_i2c_py532")
    assert idx >= 0
    page._rfid_reader_combo.setCurrentIndex(idx)
    page.on_leave()
    assert page.state.rfid_reader_module == "pn532_i2c_py532"
