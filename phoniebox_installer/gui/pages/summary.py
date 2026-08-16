"""Summary page — read-only review of all choices."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QScrollArea, QWidget, QGroupBox,
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

        self._add_section(layout, "Mode", "mode")
        self._add_section(layout, "System", "system")
        self._add_section(layout, "Git Source", "git")
        self._add_section(layout, "Options", "options")
        self._add_section(layout, "Audio", "audio")

        layout.addStretch()

    def _add_section(self, layout, title, key):
        group = QGroupBox(title)
        v = QVBoxLayout(group)
        label = QLabel("")
        label.setWordWrap(True)
        v.addWidget(label)
        layout.addWidget(group)
        self._summary_labels[key] = label
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

        if s.existing_installation:
            action = s.existing_install_action or "backup"
            self._warning_label.setText(
                f"⚠️ Existing installation found — action: {action}"
            )
        elif s.mode == "update":
            self._warning_label.setText(
                "⚠️ Update mode — upgrading an existing installation."
            )
        else:
            self._warning_label.setText("")

    def validate(self):
        return (True, "")
