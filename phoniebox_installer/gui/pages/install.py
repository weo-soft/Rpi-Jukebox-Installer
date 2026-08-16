"""Install page — live log and progress, plus post-install reboot countdown."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar,
    QPlainTextEdit, QMessageBox, QCheckBox,
)
from PySide6.QtCore import QTimer

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import InstallEvents

#: Seconds the page waits after a successful install before auto-rebooting.
REBOOT_COUNTDOWN_SECONDS = 30


class InstallPage(BasePage):
    page_id = "install"
    title = "Installing Phoniebox"
    subtitle = "Live installation log and progress."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._step_lines = []
        self._detail_lines = []
        self._show_details = False
        self._install_triggered = False

        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._reboot_sent = False
        self._reboot_cancelled = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._phase_label = QLabel("")
        layout.addWidget(self._phase_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        layout.addWidget(self._progress)

        # Prominent auto-reboot countdown (shown after a successful install).
        self._countdown_label = QLabel("")
        self._countdown_label.setWordWrap(True)
        self._countdown_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #b04a00;"
        )
        layout.addWidget(self._countdown_label)

        reboot_row = QHBoxLayout()
        self._restart_now_btn = QPushButton("🔄 Restart Now")
        self._restart_now_btn.clicked.connect(self._restart_now)
        reboot_row.addWidget(self._restart_now_btn)
        self._cancel_reboot_btn = QPushButton("Cancel Restart")
        self._cancel_reboot_btn.clicked.connect(self._cancel_reboot)
        reboot_row.addWidget(self._cancel_reboot_btn)
        reboot_row.addStretch()
        layout.addLayout(reboot_row)

        self._countdown_label.setVisible(False)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)

        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Live Log:"))
        log_row.addStretch()
        self._details_checkbox = QCheckBox("Details")
        self._details_checkbox.toggled.connect(self._on_details_toggled)
        log_row.addWidget(self._details_checkbox)
        layout.addLayout(log_row)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(10000)
        layout.addWidget(self._log, stretch=1)

        self._cancel_btn = QPushButton("Cancel Installation")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self._cancel_btn)

    def on_enter(self):
        self.event_bus.subscribe(InstallEvents.INSTALL_STARTED, self._on_install_started)
        self.event_bus.subscribe(InstallEvents.INSTALL_OUTPUT, self._on_output)
        self.event_bus.subscribe(InstallEvents.INSTALL_PROGRESS, self._on_progress)
        self.event_bus.subscribe(InstallEvents.INSTALL_COMPLETED, self._on_completed)
        self.event_bus.subscribe(InstallEvents.INSTALL_FAILED, self._on_failed)
        self.event_bus.subscribe(InstallEvents.INSTALL_DETAIL, self._on_detail)
        # Start the installation once. Re-entering the page (e.g. navigating
        # back from the finish page) must not restart it — otherwise a
        # completed install would be re-run against a rebooting Pi and fail.
        if self.controller is not None and not self._install_triggered:
            self._install_triggered = True
            self.controller.start_install()

    def _on_install_started(self, payload):
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setValue(0)
        self._phase_label.setStyleSheet("")
        self._log.clear()
        self._step_lines = []
        self._detail_lines = []
        self._cancel_btn.setEnabled(True)
        # Reset any pending reboot countdown from a previous run.
        self._timer.stop()
        self._reboot_sent = False
        self._reboot_cancelled = False
        self._countdown_label.setVisible(False)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)

    def _on_output(self, payload):
        line = payload.get("line", "")
        self._step_lines.append(line)
        if not self._show_details:
            self._log.appendPlainText(line)

    def _on_detail(self, payload):
        line = payload.get("line", "")
        self._detail_lines.append(line)
        if self._show_details:
            self._log.appendPlainText(line)

    def _on_details_toggled(self, checked):
        self._show_details = checked
        self._log.clear()
        lines = self._detail_lines if checked else self._step_lines
        for line in lines:
            self._log.appendPlainText(line)

    def _on_progress(self, payload):
        self._phase_label.setText(payload.get("step", ""))

    def _on_completed(self, payload):
        self._phase_label.setText("✅ Installation complete.")
        self._phase_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #2a7d2a;"
        )
        # Stop the indeterminate animation and show a full bar.
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._cancel_btn.setEnabled(False)
        # Start the auto-reboot countdown right here on the install page.
        self._start_countdown()

    def _on_failed(self, payload):
        self._phase_label.setText(f"❌ {payload.get('error', 'Installation failed')}")
        self._phase_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #d33;"
        )
        # Stop the indeterminate animation and show an empty bar.
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._cancel_btn.setEnabled(False)
        self._timer.stop()
        self._countdown_label.setVisible(False)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)

    # ------------------------------------------------------------------
    # Reboot countdown (auto-reboot after a successful installation)
    # ------------------------------------------------------------------

    def _start_countdown(self):
        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._update_countdown_label()
        self._countdown_label.setVisible(True)
        self._restart_now_btn.setVisible(True)
        self._restart_now_btn.setEnabled(True)
        self._cancel_reboot_btn.setVisible(True)
        self._cancel_reboot_btn.setEnabled(True)
        self._timer.start()

    def _tick(self):
        if self._reboot_sent or self._reboot_cancelled:
            return
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._do_reboot()
        else:
            self._update_countdown_label()

    def _update_countdown_label(self):
        self._countdown_label.setText(
            "🔄 The Raspberry Pi will restart automatically in "
            f"{self._countdown_remaining} s…"
        )

    def _restart_now(self):
        self._do_reboot()

    def _cancel_reboot(self):
        if self._reboot_sent:
            return
        self._reboot_cancelled = True
        self._timer.stop()
        self._countdown_label.setText(
            "Restart cancelled. You can restart the Pi manually later."
        )
        self._restart_now_btn.setEnabled(False)
        self._cancel_reboot_btn.setEnabled(False)

    def _do_reboot(self):
        if self._reboot_sent or self._reboot_cancelled:
            return
        self._reboot_sent = True
        self._timer.stop()
        self._countdown_label.setText("🔄 Restarting the Raspberry Pi…")
        self._restart_now_btn.setEnabled(False)
        self._cancel_reboot_btn.setEnabled(False)
        if self.controller is not None:
            self.controller.reboot_target()

    def _on_cancel_clicked(self):
        reply = QMessageBox.question(
            self,
            "Cancel Installation",
            "Are you sure you want to cancel?\n"
            "The installation will be incomplete.\n\n"
            "Note: cancelling during package installation (apt) may leave "
            "the Pi half-configured.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes and self.controller is not None:
            self.controller.request_cancel()

    def validate(self):
        if self.state.install_success:
            return (True, "")
        return (False, "Installation is still in progress.")

    def commit(self):
        """On wizard finish, honour the auto-reboot intent if still pending."""
        if (self.state.install_success and not self._reboot_cancelled
                and not self._reboot_sent):
            self._do_reboot()

    def on_leave(self):
        self.event_bus.unsubscribe(InstallEvents.INSTALL_STARTED, self._on_install_started)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_OUTPUT, self._on_output)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_PROGRESS, self._on_progress)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_COMPLETED, self._on_completed)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_FAILED, self._on_failed)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_DETAIL, self._on_detail)
