"""Installation options page."""

import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QLineEdit,
    QComboBox, QFrame, QGroupBox, QScrollArea, QWidget, QCompleter,
    QRadioButton, QButtonGroup,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.gui.widgets import (
    CollapsibleGroupBox, CustomCheckBox, InfoIcon,
)
from phoniebox_installer.util.validation import parse_github_branch_url
from phoniebox_installer.util.network import fetch_github_branches

#: (module name, display name) — the display names are the same labels the
#: interactive install shows (components/rfid/hardware/<reader>/description.py).
RFID_READERS = [
    ("pn532_i2c_py532", "PN532 reader via I2C using py532 library"),
    ("rc522_spi", "MFRC522 via SPI"),
    ("rdm6300_serial", "RDM6300 via serial UART"),
    ("mfrc522_i2c", "MFRC522 Reader using I2C via the mfrc522_i2c library"),
    ("generic_nfcpy", "Generic NFCPY NFC Reader Module"),
    ("generic_usb", "Generic USB Reader"),
]

#: Readers that have no usable module defaults and require interactive
#: device/pin selection on the Raspberry Pi itself (run_register_rfid_reader.py).
#: They cannot be configured by this remote/headless installer, so selecting
#: them is blocked in validate() with a hint on how to proceed.
RFID_MANUAL_READERS = frozenset({"generic_usb", "generic_nfcpy", "rc522_spi"})

HIFIBERRY_BOARDS = [
    "hifiberry-dacplus",
    "hifiberry-digi",
    "hifiberry-dac",
    "hifiberry-amp",
]

#: (data value, display name) — the display names describe the bundle in
#: user-facing terms; the data is the ENABLE_WEBAPP_PROD_DOWNLOAD value the
#: install script consumes.
WEBAPP_BUNDLE_MODES = [
    ("release-only", "Upstream / default (release bundle)"),
    ("true", "Fork / branch (development bundle)"),
]

#: Default Spotify OAuth callback URI, matching
#: SPOTIFY_DEFAULT_REDIRECT_URI in installation/includes/01_default_config.sh.
SPOTIFY_DEFAULT_REDIRECT_URI = "http://127.0.0.1:3000/api/v1/spotify/oauth/callback"


#: Explanations behind the info icons, taken from the Phoniebox install
#: scripts (installation/routines/customize_options.sh, setup_mpd.sh,
#: components/setup_hifiberry.sh, includes/01_default_config.sh).
OPTION_INFO = {
    "git_url": (
        "Branch URL",
        "Paste a GitHub branch URL to auto-fill fork and branch, e.g.\n"
        "https://github.com/<owner>/RPi-Jukebox-RFID/tree/<branch>",
    ),
    "git_fork": (
        "Git Project/Fork",
        "The GitHub user. The source is downloaded from "
        "https://github.com/<fork>/RPi-Jukebox-RFID. Installing from a fork is "
        "mainly for developers.",
    ),
    "git_branch": (
        "Git Branch",
        "The branch of the repository to install. Defaults to the upstream "
        "release branch (future3/main). A specific branch or repository is "
        "mainly for developers.",
    ),
    "webapp_bundle": (
        "WebApp Bundle",
        "Which precompiled WebApp bundle to download:\n"
        "• Upstream / default — the exact-commit release bundle (default)\n"
        "• Fork / branch — the exact-commit development bundle\n\n"
        "Forks and development branches require the development bundle; "
        "the release bundle only works with the upstream release branch.",
    ),
    "static_ip": (
        "Static IP",
        "Setting a static IP will save a lot of startup time.\n"
        "The installer uses the currently dynamically assigned IP address, "
        "including its gateway and interface.",
    ),
    "ipv6": (
        "Disable IPv6",
        "IPv6 is only needed if you intend to use it.\n"
        "Otherwise it can be disabled.",
    ),
    "autohotspot": (
        "Autohotspot",
        "When enabled, this service spins up a WiFi hotspot when the Phoniebox "
        "is unable to connect to a known WiFi. This way you can still access "
        "it.\n\n"
        "Note: Static IP configuration cannot be enabled together with the "
        "WiFi hotspot.",
    ),
    "bluetooth": (
        "Disable Bluetooth",
        "Turning off Bluetooth will save energy and startup time, "
        "if you do not plan to use it.",
    ),
    "onboard_audio": (
        "Disable on-chip audio",
        "If you are using an external sound card (e.g. USB, HiFiBerry, "
        "PirateAudio, etc.), we recommend disabling the on-chip audio. It "
        "makes the ALSA sound configuration easier.\n"
        "If you are planning to only use Bluetooth speakers, leave the on-chip "
        "audio enabled!\n\n"
        "This touches your boot configuration file; a backup copy is written.",
    ),
    "mpd": (
        "Setup MPD",
        "Installs the Music Player Daemon (MPD) as a user service. It is "
        "important that MPD runs as a user process rather than a system-wide "
        "process.",
    ),
    "mpd_overwrite": (
        "Overwrite MPD config",
        "If MPD is already installed, overwrite its existing configuration. "
        "Note: it is important that MPD runs as a user service.",
    ),
    "update_os": (
        "Update OS",
        "Updates the operating system (apt full-upgrade). This should be done "
        "eventually, but increases the installation time a lot.",
    ),
    "rfid": (
        "RFID Reader",
        "Phoniebox can be controlled with RFID cards/tags if you have an RFID "
        "reader connected. Select this to set up a reader.\n\n"
        "Available readers:\n"
        "• PN532 reader via I2C using py532 library\n"
        "• MFRC522 via SPI\n"
        "• RDM6300 via serial UART\n"
        "• MFRC522 Reader using I2C via the mfrc522_i2c library\n"
        "• Generic NFCPY NFC Reader Module\n"
        "• Generic USB Reader",
    ),
    "samba": (
        "Samba",
        "The Web App can upload and manage files in the audio library. Samba "
        "additionally provides direct network access to the complete shared "
        "directory, including configuration files.",
    ),
    "webapp": (
        "WebApp",
        "This is only required if you want to use a graphical interface to "
        "manage your Phoniebox.",
    ),
    "kiosk": (
        "Kiosk Mode",
        "If you have a screen attached to your RPi, this launches the Web App "
        "right after boot. It only installs the necessary X server "
        "dependencies, not the entire RPi desktop environment.\n\n"
        "Due to limited resources, kiosk mode is not supported on Raspberry Pi "
        "1 or Zero 1 (ARMv6 models).",
    ),
    "hifiberry": (
        "HiFiBerry Board",
        "Enables the device-tree overlay for a HiFiBerry audio HAT, e.g.\n"
        "• hifiberry-dacplus — HiFiBerry DAC+ Standard/Pro/Amp2\n"
        "• hifiberry-digi — HiFiBerry Digi+\n"
        "• hifiberry-dac — HiFiBerry MiniAmp / I2S PCM5102A DAC\n"
        "• hifiberry-amp — HiFiBerry Amp+ (not Amp2)\n\n"
        "The on-chip audio is disabled automatically when a board is selected.",
    ),
    "spotify": (
        "Spotify",
        "Installs librespot as a user service and configures the Spotify\n"
        "player backend in the Web App.\n\n"
        "Spotify playback requires a Premium account and a Spotify developer\n"
        "app:\n"
        "1. Go to https://developer.spotify.com/dashboard and create an app.\n"
        "2. Enter the exact Redirect URI below (the default targets the Web App\n"
        "   via an SSH tunnel).\n"
        "3. Copy the Client ID into the Client ID field.\n\n"
        "After the installation, connect the account in the Web App under\n"
        "Settings > Spotify > Connect.",
    ),
    "jellyfin": (
        "Jellyfin",
        "Configures the Jellyfin player backend in jukebox.yaml. The Jellyfin\n"
        "media server is not installed — you only connect to an existing one\n"
        "on your network (e.g. http://jellyfin.local:8096).\n\n"
        "Authentication: either an API key (Jellyfin Dashboard → API Keys) or\n"
        "a Jellyfin username + password. The user login honors the library\n"
        "permissions of that account.",
    ),
}


class OptionsPage(BasePage):
    page_id = "options"
    title = "Configure Your Installation"
    subtitle = "Customize how Phoniebox is installed."

    #: Branch names fetched from GitHub (emitted from a worker thread).
    _branches_loaded = Signal(list)

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._branch_cache = {}          # owner -> [branch names]
        self._branch_fetch_pending = set()
        self._branches_loaded.connect(self._on_branches_loaded)

        # Debounce branch-list reloads while the user edits the fork field.
        self._branch_debounce = QTimer(self)
        self._branch_debounce.setSingleShot(True)
        self._branch_debounce.setInterval(400)
        self._branch_debounce.timeout.connect(self._load_branches)

        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # ---- Phoniebox Source (developer-focused, collapsed by default) ----
        source_group = CollapsibleGroupBox("Phoniebox Source", collapsed=True)
        source_layout = source_group.content_layout()
        source_layout.addWidget(QLabel("Branch URL (paste to auto-fill fork + branch):"))
        self._git_url_input = QLineEdit()
        self._git_url_input.setPlaceholderText(
            "https://github.com/<owner>/RPi-Jukebox-RFID/tree/<branch>"
        )
        self._git_url_input.textChanged.connect(self._on_url_text_changed)
        url_row = QHBoxLayout()
        url_row.addWidget(self._git_url_input, stretch=1)
        url_row.addWidget(self._make_info_icon("git_url"))
        source_layout.addLayout(url_row)
        self._url_hint_label = QLabel("")
        self._url_hint_label.setWordWrap(True)
        self._url_hint_label.setStyleSheet("color: #b04a00;")
        self._url_hint_label.setVisible(False)
        source_layout.addWidget(self._url_hint_label)
        # Git Project/Fork and Git Branch side by side.
        fork_branch_row = QHBoxLayout()
        fork_branch_row.setSpacing(12)

        fork_col = QVBoxLayout()
        fork_col.addWidget(QLabel("Git Project/Fork:"))
        self._git_fork_input = QLineEdit("MiczFlor")
        fork_input_row = QHBoxLayout()
        fork_input_row.addWidget(self._git_fork_input, stretch=1)
        fork_input_row.addWidget(self._make_info_icon("git_fork"))
        fork_col.addLayout(fork_input_row)
        fork_branch_row.addLayout(fork_col, stretch=1)

        branch_col = QVBoxLayout()
        branch_col.addWidget(QLabel("Git Branch:"))
        self._git_branch_combo = QComboBox()
        self._git_branch_combo.setEditable(True)
        self._git_branch_combo.setInsertPolicy(QComboBox.NoInsert)
        self._git_branch_combo.setCurrentText("future3/main")
        branch_input_row = QHBoxLayout()
        branch_input_row.addWidget(self._git_branch_combo, stretch=1)
        branch_input_row.addWidget(self._make_info_icon("git_branch"))
        branch_col.addLayout(branch_input_row)
        fork_branch_row.addLayout(branch_col, stretch=1)

        source_layout.addLayout(fork_branch_row)

        # Branch autocomplete from the GitHub branches API (see _load_branches).
        # An editable combo gives a proper dropdown that closes on outside
        # click and autocompletes while typing — a QLineEdit+QCompleter popup
        # shown on focus can grab the mouse and block input globally.
        self._branch_completer = QCompleter(self._git_branch_combo.model(), self)
        self._branch_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._branch_completer.setFilterMode(Qt.MatchContains)
        self._branch_completer.setCompletionMode(QCompleter.PopupCompletion)
        self._git_branch_combo.setCompleter(self._branch_completer)
        # The bundle mode is tied to the source: only the upstream release
        # branch ships release-only bundles, forks/development branches need
        # the commit-addressed development bundles (see _sync_webapp_bundle_to_source).
        source_layout.addWidget(QLabel("WebApp bundle:"))
        self._webapp_bundle_combo = QComboBox()
        for data, name in WEBAPP_BUNDLE_MODES:
            self._webapp_bundle_combo.addItem(name, data)
        bundle_row = QHBoxLayout()
        bundle_row.addWidget(self._webapp_bundle_combo, stretch=1)
        bundle_row.addWidget(self._make_info_icon("webapp_bundle"))
        source_layout.addLayout(bundle_row)

        # ---- Services + Audio (left) | System Options (right) ----
        columns = QHBoxLayout()
        columns.setSpacing(12)

        # Left column: Services on top, Audio below it. The block is
        # bottom-anchored so both columns end flush at the bottom (System
        # Options on the right is the taller one).
        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        left_col.addStretch()

        services_group = QGroupBox("Services")
        services_layout = QVBoxLayout(services_group)

        # RFID is the only option the user MUST decide on (enabled by default,
        # but no reader type is pre-selected), so the row is highlighted.
        rfid_frame = QFrame()
        rfid_frame.setObjectName("rfidRequired")
        rfid_frame.setStyleSheet("""
            #rfidRequired {
                background-color: #eef4fb;
                border: 1px solid #1976d2;
                border-radius: 6px;
            }
            /* No background-color on the combo: a stylesheet background on a
               QComboBox also paints the popup's selected row and overlays the
               selection highlight with a white box. */
            #rfidRequired QComboBox[needsSelection="true"] {
                border: 2px solid #b04a00;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        rfid_frame_layout = QVBoxLayout(rfid_frame)
        rfid_frame_layout.setContentsMargins(8, 6, 8, 6)
        rfid_frame_layout.setSpacing(4)

        rfid_row = QHBoxLayout()
        self._rfid_checkbox = CustomCheckBox("RFID Reader")
        self._rfid_checkbox.setChecked(True)
        rfid_row.addWidget(self._rfid_checkbox)
        self._rfid_reader_combo = QComboBox()
        self._rfid_reader_combo.addItem("Select reader…", "")
        for module, name in RFID_READERS:
            self._rfid_reader_combo.addItem(name, module)
        rfid_row.addWidget(self._rfid_reader_combo, stretch=1)
        rfid_row.addWidget(self._make_info_icon("rfid"))
        rfid_frame_layout.addLayout(rfid_row)
        self._rfid_hint = QLabel("⚠️  Required — choose your RFID reader type.")
        self._rfid_hint.setStyleSheet("color: #b04a00; font-size: 11px;")
        rfid_frame_layout.addWidget(self._rfid_hint)
        self._rfid_manual_hint = QLabel(
            "ℹ️  This reader cannot be configured by the remote installer: it has no "
            "automatic defaults and requires interactive device/pin selection on the "
            "Raspberry Pi. Disable the RFID reader for now, install, and afterwards run "
            "'run_register_rfid_reader.py' in ~/RPi-Jukebox-RFID/src/jukebox on the Pi."
        )
        self._rfid_manual_hint.setWordWrap(True)
        self._rfid_manual_hint.setStyleSheet("color: #8a6d00; font-size: 11px;")
        self._rfid_manual_hint.setVisible(False)
        rfid_frame_layout.addWidget(self._rfid_manual_hint)
        services_layout.addWidget(rfid_frame)

        self._samba_checkbox = self._add_checkbox(
            services_layout, "Samba", False, info_key="samba"
        )
        self._webapp_checkbox = self._add_checkbox(
            services_layout, "WebApp", True, info_key="webapp"
        )
        self._kiosk_checkbox = self._add_checkbox(
            services_layout, "Kiosk Mode (full-screen WebUI)", False,
            info_key="kiosk",
        )
        left_col.addWidget(services_group)

        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout(audio_group)
        audio_layout.addWidget(QLabel("HiFiBerry Board:"))
        self._hifiberry_combo = QComboBox()
        self._hifiberry_combo.addItem("None", "")
        for board in HIFIBERRY_BOARDS:
            self._hifiberry_combo.addItem(board, board)
        audio_row = QHBoxLayout()
        audio_row.addWidget(self._hifiberry_combo, stretch=1)
        audio_row.addWidget(self._make_info_icon("hifiberry"))
        audio_layout.addLayout(audio_row)
        audio_layout.addWidget(QLabel("ℹ️  Select the audio HAT overlay (optional)"))
        left_col.addWidget(audio_group)

        columns.addLayout(left_col, stretch=1)

        # Right column: System Options.
        sys_group = QGroupBox("System Options")
        sys_layout = QVBoxLayout(sys_group)
        self._static_ip_checkbox = self._add_checkbox(
            sys_layout, "Static IP", True, info_key="static_ip"
        )
        self._ipv6_checkbox = self._add_checkbox(
            sys_layout, "Disable IPv6", True, info_key="ipv6"
        )
        self._autohotspot_checkbox = self._add_checkbox(
            sys_layout, "Autohotspot", False, info_key="autohotspot"
        )
        self._bluetooth_checkbox = self._add_checkbox(
            sys_layout, "Disable Bluetooth", True, info_key="bluetooth"
        )
        self._onboard_audio_checkbox = self._add_checkbox(
            sys_layout, "Disable on-chip audio", False, info_key="onboard_audio"
        )
        self._mpd_checkbox = self._add_checkbox(
            sys_layout, "Setup MPD", True, info_key="mpd"
        )
        self._mpd_overwrite_checkbox = self._add_checkbox(
            sys_layout, "Overwrite MPD config", True, info_key="mpd_overwrite"
        )
        self._update_os_checkbox = self._add_checkbox(
            sys_layout, "Update OS", False, info_key="update_os"
        )
        columns.addWidget(sys_group, stretch=1)

        layout.addLayout(columns)

        # ---- Plugins: Spotify + Jellyfin ----
        plugins_group = QGroupBox("Plugins")
        plugins_layout = QVBoxLayout(plugins_group)
        plugins_layout.setSpacing(8)

        # --- Spotify ---
        spotify_frame = QFrame()
        spotify_layout = QVBoxLayout(spotify_frame)
        spotify_layout.setContentsMargins(8, 6, 8, 6)
        spotify_layout.setSpacing(6)

        spotify_row = QHBoxLayout()
        self._spotify_checkbox = CustomCheckBox("Install Spotify support")
        self._spotify_checkbox.setChecked(False)
        spotify_row.addWidget(self._spotify_checkbox)
        spotify_row.addWidget(self._make_info_icon("spotify"))
        spotify_row.addStretch()
        spotify_layout.addLayout(spotify_row)

        self._spotify_client_id_input = QLineEdit()
        self._spotify_client_id_input.setPlaceholderText("Spotify developer app client ID")
        spotify_layout.addWidget(self._spotify_client_id_input)

        self._spotify_redirect_uri_input = QLineEdit(SPOTIFY_DEFAULT_REDIRECT_URI)
        spotify_layout.addWidget(self._spotify_redirect_uri_input)

        self._spotify_device_name_input = QLineEdit("Phoniebox")
        self._spotify_device_name_input.setPlaceholderText("Spotify Connect device name")
        spotify_layout.addWidget(self._spotify_device_name_input)
        spotify_layout.addWidget(QLabel(
            "Spotify requires a Premium account and a developer app. "
            "Client ID, Redirect URI and device name map to SPOTIFY_*."
        ))
        plugins_layout.addWidget(spotify_frame)

        # --- Jellyfin ---
        jellyfin_frame = QFrame()
        jellyfin_layout = QVBoxLayout(jellyfin_frame)
        jellyfin_layout.setContentsMargins(8, 6, 8, 6)
        jellyfin_layout.setSpacing(6)

        jellyfin_row = QHBoxLayout()
        self._jellyfin_checkbox = CustomCheckBox("Enable Jellyfin player backend")
        self._jellyfin_checkbox.setChecked(False)
        jellyfin_row.addWidget(self._jellyfin_checkbox)
        jellyfin_row.addWidget(self._make_info_icon("jellyfin"))
        jellyfin_row.addStretch()
        jellyfin_layout.addLayout(jellyfin_row)

        self._jellyfin_host_input = QLineEdit()
        self._jellyfin_host_input.setPlaceholderText(
            "Jellyfin server URL, e.g. http://jellyfin.local:8096"
        )
        jellyfin_layout.addWidget(self._jellyfin_host_input)

        auth_row = QHBoxLayout()
        self._jellyfin_api_key_radio = QRadioButton("API key")
        self._jellyfin_api_key_radio.setChecked(True)
        self._jellyfin_user_radio = QRadioButton("Jellyfin user login")
        self._auth_group = QButtonGroup(self)
        self._auth_group.addButton(self._jellyfin_api_key_radio)
        self._auth_group.addButton(self._jellyfin_user_radio)
        auth_row.addWidget(self._jellyfin_api_key_radio)
        auth_row.addWidget(self._jellyfin_user_radio)
        auth_row.addStretch()
        jellyfin_layout.addLayout(auth_row)

        self._jellyfin_api_key_input = QLineEdit()
        self._jellyfin_api_key_input.setPlaceholderText("API key (Jellyfin Dashboard → API Keys)")
        jellyfin_layout.addWidget(self._jellyfin_api_key_input)

        self._jellyfin_username_input = QLineEdit()
        self._jellyfin_username_input.setPlaceholderText("Jellyfin username")
        jellyfin_layout.addWidget(self._jellyfin_username_input)

        self._jellyfin_password_input = QLineEdit()
        self._jellyfin_password_input.setPlaceholderText("Jellyfin password")
        self._jellyfin_password_input.setEchoMode(QLineEdit.Password)
        jellyfin_layout.addWidget(self._jellyfin_password_input)
        plugins_layout.addWidget(jellyfin_frame)

        layout.addWidget(plugins_group)

        # Phoniebox Source — developer-focused, so it is placed below the main
        # option blocks instead of being the most prominent section.
        layout.addWidget(source_group)

        layout.addStretch()

        self._wire_dependencies()
        self._update_rfid_highlight()
        # Apply the initial enabled/disabled state of the plugin fields
        # (the toggled signals do not fire for the constructor defaults).
        self._on_spotify_toggled(self._spotify_checkbox.isChecked())
        self._on_jellyfin_toggled(self._jellyfin_checkbox.isChecked())

    def _update_rfid_highlight(self, *_args):
        """Mark the reader combo (orange border) while a choice is required.

        RFID is enabled by default but has no pre-selected module, so the user
        must actively choose a reader type (or disable the reader).
        """
        needed = self._rfid_checkbox.isChecked() and not self._rfid_reader_combo.currentData()
        self._rfid_reader_combo.setProperty("needsSelection", needed)
        self._rfid_reader_combo.style().unpolish(self._rfid_reader_combo)
        self._rfid_reader_combo.style().polish(self._rfid_reader_combo)
        self._rfid_hint.setVisible(needed)
        self._update_rfid_manual_hint()

    def _update_rfid_manual_hint(self, *_args):
        """Show a hint when a reader requiring on-Pi configuration is selected."""
        needs_manual = (
            self._rfid_checkbox.isChecked()
            and self._rfid_reader_combo.currentData() in RFID_MANUAL_READERS
        )
        self._rfid_manual_hint.setVisible(needs_manual)

    def _make_info_icon(self, key):
        """Return an InfoIcon for the given OPTION_INFO key."""
        title, text = OPTION_INFO[key]
        return InfoIcon(title, text)

    def _add_checkbox(self, layout, label, default, info_key=None):
        """Add a checkbox row; optionally append an info icon at the end."""
        cb = CustomCheckBox(label)
        cb.setChecked(default)
        if info_key:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(cb)
            row.addWidget(self._make_info_icon(info_key))
            row.addStretch()
            layout.addLayout(row)
        else:
            layout.addWidget(cb)
        return cb

    def _wire_dependencies(self):
        self._rfid_checkbox.toggled.connect(
            lambda checked: self._rfid_reader_combo.setEnabled(checked)
        )
        self._rfid_checkbox.toggled.connect(self._update_rfid_highlight)
        self._rfid_reader_combo.currentIndexChanged.connect(self._update_rfid_highlight)
        self._rfid_reader_combo.currentIndexChanged.connect(self._update_rfid_manual_hint)
        self._webapp_checkbox.toggled.connect(self._on_webapp_toggled)
        self._autohotspot_checkbox.toggled.connect(self._on_autohotspot_toggled)
        # A non-upstream source requires the development WebApp bundle.
        self._git_fork_input.textChanged.connect(self._sync_webapp_bundle_to_source)
        self._git_branch_combo.currentTextChanged.connect(
            self._sync_webapp_bundle_to_source
        )
        # Reload the branch list (debounced) when the fork changes.
        self._git_fork_input.textChanged.connect(self._on_fork_changed)

        # Spotify / Jellyfin plugin fields follow their enable checkbox.
        self._spotify_checkbox.toggled.connect(self._on_spotify_toggled)
        self._jellyfin_checkbox.toggled.connect(self._on_jellyfin_toggled)
        self._jellyfin_api_key_radio.toggled.connect(self._on_jellyfin_auth_toggled)

    def _on_spotify_toggled(self, checked):
        self._spotify_client_id_input.setEnabled(checked)
        self._spotify_redirect_uri_input.setEnabled(checked)
        self._spotify_device_name_input.setEnabled(checked)

    def _on_jellyfin_toggled(self, checked):
        self._jellyfin_host_input.setEnabled(checked)
        self._jellyfin_api_key_radio.setEnabled(checked)
        self._jellyfin_user_radio.setEnabled(checked)
        self._on_jellyfin_auth_toggled(self._jellyfin_api_key_radio.isChecked())

    def _on_jellyfin_auth_toggled(self, _api_key_selected):
        api_key_mode = self._jellyfin_api_key_radio.isChecked()
        enabled = self._jellyfin_checkbox.isChecked()
        self._jellyfin_api_key_input.setEnabled(enabled and api_key_mode)
        self._jellyfin_username_input.setEnabled(enabled and not api_key_mode)
        self._jellyfin_password_input.setEnabled(enabled and not api_key_mode)

    def _on_webapp_toggled(self, checked):
        self._kiosk_checkbox.setEnabled(checked)
        if not checked:
            self._kiosk_checkbox.setChecked(False)

    def _on_autohotspot_toggled(self, checked):
        # Static IP and Autohotspot are mutually exclusive.
        if checked:
            self._static_ip_checkbox.setChecked(False)

    # ------------------------------------------------------------------
    # Branch autocomplete (GitHub branches API)
    # ------------------------------------------------------------------

    def _on_fork_changed(self, *_args):
        """Debounce branch-list reloads while the fork field is edited."""
        self._branch_debounce.start()

    def _load_branches(self):
        """(Re)load the branch list for the current fork.

        Uses a per-fork cache; only uncached forks trigger a GitHub API call
        (in a background thread so the UI stays responsive).
        """
        owner = self._git_fork_input.text().strip()
        if not owner:
            return
        if owner in self._branch_cache:
            self._on_branches_loaded(self._branch_cache[owner])
            return
        if owner in self._branch_fetch_pending:
            return
        self._branch_fetch_pending.add(owner)
        threading.Thread(
            target=self._fetch_branches_sync, args=(owner,), daemon=True
        ).start()

    def _fetch_branches_sync(self, owner):
        """Fetch branch names in a worker thread and publish them."""
        try:
            names = fetch_github_branches(owner)
        except Exception:
            names = []
        self._branch_cache[owner] = names
        self._branch_fetch_pending.discard(owner)
        self._branches_loaded.emit(names)

    def _on_branches_loaded(self, names):
        """Apply fetched branch names to the dropdown (GUI thread)."""
        current = self._git_branch_combo.currentText()
        self._git_branch_combo.clear()
        self._git_branch_combo.addItems(names)
        self._git_branch_combo.setCurrentText(current)

    def _sync_webapp_bundle_to_source(self, *_args):
        """Non-upstream sources need the development WebApp bundle.

        'release-only' only makes sense for the upstream release branch
        (MiczFlor / future3/main). Any other fork/branch requires
        commit-addressed development bundles, so 'true' is selected
        automatically. Switching back to the upstream release branch does not
        force the mode back — the user can still choose it manually.
        """
        fork = self._git_fork_input.text().strip()
        branch = self._git_branch_combo.currentText().strip()
        if fork != "MiczFlor" or branch != "future3/main":
            idx = self._webapp_bundle_combo.findData("true")
            if idx >= 0:
                self._webapp_bundle_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        """Pre-fill fields from state (restore on back-navigation)."""
        self._git_fork_input.setText(self.state.git_user)
        self._git_branch_combo.setCurrentText(self.state.git_branch)
        self._static_ip_checkbox.setChecked(self.state.enable_static_ip)
        self._ipv6_checkbox.setChecked(self.state.disable_ipv6)
        self._autohotspot_checkbox.setChecked(self.state.enable_autohotspot)
        self._bluetooth_checkbox.setChecked(self.state.disable_bluetooth)
        self._onboard_audio_checkbox.setChecked(self.state.disable_onboard_audio)
        self._mpd_checkbox.setChecked(self.state.setup_mpd)
        self._mpd_overwrite_checkbox.setChecked(self.state.enable_mpd_overwrite_install)
        self._update_os_checkbox.setChecked(self.state.update_raspi_os)
        self._rfid_checkbox.setChecked(self.state.enable_rfid_reader)
        self._samba_checkbox.setChecked(self.state.enable_samba)
        self._webapp_checkbox.setChecked(self.state.enable_webapp)
        self._kiosk_checkbox.setChecked(self.state.enable_kiosk_mode)
        self._set_combo_data(self._rfid_reader_combo, self.state.rfid_reader_module)
        self._update_rfid_manual_hint()
        self._set_combo_data(self._hifiberry_combo, self.state.audio_hifiberry_board)
        self._set_combo_data(self._webapp_bundle_combo, self.state.enable_webapp_prod_download)
        # The source rule wins over the stored value: a non-upstream source
        # always requires the development WebApp bundle.
        self._sync_webapp_bundle_to_source()
        # Preload the branch list for the current fork (cached per fork).
        self._load_branches()

    def _set_combo_data(self, combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_url_text_changed(self, text):
        """Auto-fill fork + branch as soon as a valid branch URL is entered."""
        url = text.strip()
        if not url:
            self._clear_url_hint()
            return

        parsed = parse_github_branch_url(url)
        if parsed is None:
            self._show_url_hint(
                "⚠️ Invalid URL — expected "
                "https://github.com/<owner>/RPi-Jukebox-RFID/tree/<branch>"
            )
            return

        owner, repo, branch = parsed
        if repo != "RPi-Jukebox-RFID":
            self._show_url_hint(
                f"⚠️ URL points to repository '{repo}', but the installer "
                "installs RPi-Jukebox-RFID."
            )
            return

        self._git_fork_input.setText(owner)
        if branch:
            self._git_branch_combo.setCurrentText(branch)
        self._clear_url_hint()

    def _show_url_hint(self, message):
        self._url_hint_label.setText(message)
        self._url_hint_label.setVisible(True)

    def _clear_url_hint(self):
        self._url_hint_label.setText("")
        self._url_hint_label.setVisible(False)

    def validate(self):
        if not self._git_fork_input.text().strip():
            return (False, "Git fork must not be empty.")
        if not self._git_branch_combo.currentText().strip():
            return (False, "Git branch must not be empty.")
        url = self._git_url_input.text().strip()
        if url:
            parsed = parse_github_branch_url(url)
            if parsed is None:
                return (False, "Could not parse the branch URL. Use a GitHub URL like "
                               "https://github.com/<owner>/RPi-Jukebox-RFID/tree/<branch>.")
            _, repo, _ = parsed
            if repo != "RPi-Jukebox-RFID":
                return (False, f"The URL points to repository '{repo}', but the "
                               "installer installs RPi-Jukebox-RFID. Please use a "
                               "URL for RPi-Jukebox-RFID.")
        if self._rfid_checkbox.isChecked() and not self._rfid_reader_combo.currentData():
            return (False, "RFID reader is enabled — please select a reader type "
                           "or disable the RFID reader.")
        if (self._rfid_checkbox.isChecked()
                and self._rfid_reader_combo.currentData() in RFID_MANUAL_READERS):
            return (False, "The selected reader requires interactive configuration on "
                           "the Raspberry Pi and cannot be set up by the remote installer. "
                           "Choose a reader with automatic defaults, disable the RFID "
                           "reader for now, or configure it manually on the Pi afterwards "
                           "with 'run_register_rfid_reader.py' (from ~/RPi-Jukebox-RFID/"
                           "src/jukebox).")
        if self._spotify_checkbox.isChecked() and not self._spotify_client_id_input.text().strip():
            return (False, "Spotify is enabled — please enter the Spotify developer app "
                           "client ID.")
        if (self._spotify_checkbox.isChecked()
                and not self._spotify_redirect_uri_input.text().strip()):
            return (False, "Spotify is enabled — please enter the OAuth redirect URI.")
        if self._jellyfin_checkbox.isChecked():
            if not self._jellyfin_host_input.text().strip():
                return (False, "Jellyfin is enabled — please enter the Jellyfin server URL.")
            if self._jellyfin_api_key_radio.isChecked():
                if not self._jellyfin_api_key_input.text().strip():
                    return (False, "Jellyfin is enabled — please enter an API key or "
                                   "switch to the Jellyfin user login.")
            elif (not self._jellyfin_username_input.text().strip()
                  or not self._jellyfin_password_input.text()):
                return (False, "Jellyfin is enabled — please enter username and password.")
        return (True, "")

    def on_leave(self):
        """Save all field values back to state."""
        self.state.git_user = self._git_fork_input.text().strip()
        self.state.git_branch = self._git_branch_combo.currentText().strip()
        self.state.enable_static_ip = self._static_ip_checkbox.isChecked()
        self.state.disable_ipv6 = self._ipv6_checkbox.isChecked()
        self.state.enable_autohotspot = self._autohotspot_checkbox.isChecked()
        self.state.disable_bluetooth = self._bluetooth_checkbox.isChecked()
        self.state.disable_onboard_audio = self._onboard_audio_checkbox.isChecked()
        self.state.setup_mpd = self._mpd_checkbox.isChecked()
        self.state.enable_mpd_overwrite_install = self._mpd_overwrite_checkbox.isChecked()
        self.state.update_raspi_os = self._update_os_checkbox.isChecked()
        self.state.enable_rfid_reader = self._rfid_checkbox.isChecked()
        self.state.rfid_reader_module = self._rfid_reader_combo.currentData() or ""
        self.state.enable_samba = self._samba_checkbox.isChecked()
        self.state.enable_webapp = self._webapp_checkbox.isChecked()
        self.state.enable_kiosk_mode = self._kiosk_checkbox.isChecked()
        self.state.audio_hifiberry_board = self._hifiberry_combo.currentData() or ""
        self.state.enable_webapp_prod_download = (
            self._webapp_bundle_combo.currentData() or "release-only"
        )
        self.state.setup_spotify = self._spotify_checkbox.isChecked()
        self.state.spotify_client_id = self._spotify_client_id_input.text().strip()
        self.state.spotify_redirect_uri = self._spotify_redirect_uri_input.text().strip()
        self.state.spotify_device_name = (
            self._spotify_device_name_input.text().strip() or "Phoniebox"
        )
        self.state.enable_jellyfin = self._jellyfin_checkbox.isChecked()
        self.state.jellyfin_host = self._jellyfin_host_input.text().strip()
        self.state.jellyfin_api_key = self._jellyfin_api_key_input.text().strip()
        self.state.jellyfin_username = self._jellyfin_username_input.text().strip()
        self.state.jellyfin_password = self._jellyfin_password_input.text()
