"""Summary page — review of all choices (incl. existing-install action)."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QGroupBox,
    QRadioButton, QButtonGroup,
)

from phoniebox_installer.gui.pages.base import BasePage


class SummaryPage(BasePage):
    page_id = "summary"
    title = "Review Your Configuration"
    subtitle = "Review your choices before starting the installation."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._warning_label = None
        self._summary_labels = {}
        self._existing_group = None
        self._backup_radio = None
        self._remove_radio = None
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

        self._warning_label = QLabel("")
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet("color: #b58900; font-weight: bold;")
        layout.addWidget(self._warning_label)

        # Existing-installation action choice (only visible when one exists).
        # Placed full-width at the top: it is the most important decision when
        # an existing installation is found.
        self._existing_group = QGroupBox("Existing Installation")
        existing_layout = QVBoxLayout(self._existing_group)
        self._backup_radio = QRadioButton("Backup the existing installation")
        self._remove_radio = QRadioButton("Remove the existing installation")
        self._action_group = QButtonGroup(self)
        self._action_group.addButton(self._backup_radio)
        self._action_group.addButton(self._remove_radio)
        existing_layout.addWidget(self._backup_radio)
        existing_layout.addWidget(self._remove_radio)
        layout.addWidget(self._existing_group)
        self._existing_group.setVisible(False)

        # Side-by-side columns keep the page compact (no scrolling on a
        # desktop window). Left: the target machine + install source.
        # Right: the configuration choices.
        columns = QHBoxLayout()
        columns.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        # "Mode" and "System" both describe the target machine, so they share
        # one container.
        self._add_merged_section(left_col, "Target & System", ["mode", "system"])
        self._add_section(left_col, "Git Source", "git")
        columns.addLayout(left_col, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        self._add_section(right_col, "Options", "options")
        self._add_section(right_col, "Audio", "audio")
        self._add_section(right_col, "Plugins", "plugins")
        columns.addLayout(right_col, stretch=1)

        layout.addLayout(columns)
        layout.addStretch()

    def _add_section(self, layout, title, key):
        """Add a titled group box holding one wrapped detail label."""
        group = QGroupBox(title)
        v = QVBoxLayout(group)
        label = QLabel("")
        label.setWordWrap(True)
        v.addWidget(label)
        layout.addWidget(group)
        self._summary_labels[key] = label
        return group

    def _add_merged_section(self, layout, title, keys):
        """Add one titled group box holding several detail labels."""
        group = QGroupBox(title)
        v = QVBoxLayout(group)
        for key in keys:
            label = QLabel("")
            label.setWordWrap(True)
            v.addWidget(label)
            self._summary_labels[key] = label
        layout.addWidget(group)
        return group

    def on_enter(self):
        """Render the summary from the shared state."""
        s = self.state
        self._summary_labels["mode"].setText(
            f"Mode: {s.mode}\n"
            f"Target: {s.target_host} ({s.target_hostname})\n"
            f"SSH User: {s.ssh_user}"
        )

        internet = "✅" if s.has_internet else "❌"
        git = "✅" if s.has_git else "❌"
        self._summary_labels["system"].setText(
            f"{s.os_version}\n"
            f"{s.arch} — Kernel {s.kernel} — {s.memory_mb} MB RAM\n"
            f"Disk: {s.disk_free_mb} MB free / {s.disk_total_mb} MB total\n"
            f"{internet} Internet  {git} Git  Python: {s.has_python}"
        )

        self._summary_labels["git"].setText(
            f"Fork: {s.git_user} / Branch: {s.git_branch}"
        )

        self._summary_labels["options"].setText(
            f"Static IP: {s.enable_static_ip}, IPv6 disabled: {s.disable_ipv6}, "
            f"Bluetooth disabled: {s.disable_bluetooth}, MPD: {s.setup_mpd}\n"
            f"RFID Reader: {s.rfid_reader_module or 'none'}\n"
            f"WebApp: {s.enable_webapp} / Kiosk: {s.enable_kiosk_mode} / Samba: {s.enable_samba}"
        )

        self._summary_labels["audio"].setText(
            f"HiFiBerry Board: {s.audio_hifiberry_board or 'none'}"
        )

        spotify = (
            f"Spotify: on (client {s.spotify_client_id}, "
            f"device '{s.spotify_device_name}')"
            if s.setup_spotify
            else "Spotify: off"
        )
        if s.enable_jellyfin:
            jellyfin = (
                f"Jellyfin: on ({s.jellyfin_host}, API key)"
                if s.jellyfin_api_key
                else f"Jellyfin: on ({s.jellyfin_host}, user {s.jellyfin_username})"
            )
        else:
            jellyfin = "Jellyfin: off"
        self._summary_labels["plugins"].setText(
            f"{spotify}\n{jellyfin}"
        )

        if s.existing_installation:
            self._existing_group.setVisible(True)
            if s.existing_install_action == "remove":
                self._remove_radio.setChecked(True)
            else:
                self._backup_radio.setChecked(True)
            self._warning_label.setText(
                "⚠️ Existing installation found — choose how to proceed:"
            )
        else:
            self._existing_group.setVisible(False)
            if s.mode == "update":
                self._warning_label.setText(
                    "⚠️ Update mode — upgrading an existing installation."
                )
            else:
                self._warning_label.setText("")

    def validate(self):
        return (True, "")

    def on_leave(self):
        """Persist the existing-install action choice to state."""
        if self.state.existing_installation:
            self.state.existing_install_action = (
                "remove" if self._remove_radio.isChecked() else "backup"
            )
