"""Install page — live log and progress, plus post-install reboot countdown."""

import socket
import threading
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar,
    QPlainTextEdit,
)
from PySide6.QtCore import QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.gui.widgets import CustomCheckBox
from phoniebox_installer.app.events import InstallEvents, WizardEvents

#: Seconds the page waits after a successful install before auto-rebooting.
REBOOT_COUNTDOWN_SECONDS = 30


class InstallPage(BasePage):
    page_id = "install"
    title = "Installing Phoniebox"
    subtitle = "Live installation log and progress."

    #: Emitted from the availability-poll thread; handled on the GUI thread.
    _reachable = Signal(bool)

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._step_lines = []
        self._detail_lines = []
        self._show_details = False
        self._install_triggered = False
        self._install_failed = False

        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._reboot_sent = False
        self._reboot_cancelled = False
        self._seen_down = False  # True once the Pi went offline during reboot
        self._advanced_to_reader = False  # True once auto-advanced to reader config

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._poll_availability)
        self._reachable.connect(self._on_reachable)

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

        # Busy spinner shown while the Pi reboots (until it is reachable again).
        self._reboot_spinner = QProgressBar()
        self._reboot_spinner.setRange(0, 0)  # indeterminate
        self._reboot_spinner.setTextVisible(False)
        self._reboot_spinner.setFixedHeight(16)
        self._reboot_spinner.setVisible(False)
        layout.addWidget(self._reboot_spinner)

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

        # Web interface button (shown after a successful install). Disabled
        # while the Pi is rebooting and re-enabled once it is reachable again.
        self._webapp_btn = QPushButton("🌐 Open Web Interface")
        self._webapp_btn.clicked.connect(self._open_webapp)
        layout.addWidget(self._webapp_btn)
        self._webapp_btn.setVisible(False)

        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Live Log:"))
        log_row.addStretch()
        self._details_checkbox = CustomCheckBox("Details")
        self._details_checkbox.toggled.connect(self._on_details_toggled)
        log_row.addWidget(self._details_checkbox)
        layout.addLayout(log_row)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(10000)
        layout.addWidget(self._log, stretch=1)

    def on_enter(self):
        self.event_bus.subscribe(InstallEvents.INSTALL_STARTED, self._on_install_started)
        self.event_bus.subscribe(InstallEvents.INSTALL_OUTPUT, self._on_output)
        self.event_bus.subscribe(InstallEvents.INSTALL_PROGRESS, self._on_progress)
        self.event_bus.subscribe(InstallEvents.INSTALL_COMPLETED, self._on_completed)
        self.event_bus.subscribe(InstallEvents.INSTALL_FAILED, self._on_failed)
        self.event_bus.subscribe(InstallEvents.INSTALL_DETAIL, self._on_detail)
        # Start the installation. Re-entering the page must not restart a
        # completed or still-running install (a completed install would
        # otherwise be re-run against a rebooting Pi), but a FAILED attempt
        # (e.g. the install script does not support --config) SHOULD be
        # restarted: the user can go back, change e.g. fork/branch, and come
        # back here to try again with the updated state.
        if self.controller is not None and (
            not self._install_triggered or self._install_failed
        ):
            self._install_triggered = True
            self._install_failed = False
            self.controller.start_install()

    def _on_install_started(self, payload):
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setValue(0)
        self._phase_label.setStyleSheet("")
        self._log.clear()
        self._step_lines = []
        self._detail_lines = []
        # Reset any pending reboot countdown from a previous run.
        self._timer.stop()
        self._poll_timer.stop()
        self._reboot_sent = False
        self._reboot_cancelled = False
        self._seen_down = False
        self._advanced_to_reader = False
        self._countdown_label.setVisible(False)
        self._reboot_spinner.setVisible(False)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)
        self._webapp_btn.setVisible(False)

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
        # Offer the web interface right here, next to the reboot countdown.
        self._webapp_btn.setVisible(True)
        self._webapp_btn.setEnabled(True)
        self._webapp_btn.setText("🌐 Open Web Interface")
        # Start the auto-reboot countdown right here on the install page.
        self._start_countdown()

    def _on_failed(self, payload):
        # Remember the failure so re-entering the page restarts the install
        # (e.g. after the user changed the fork/branch to retry).
        self._install_failed = True
        self._phase_label.setText(f"❌ {payload.get('error', 'Installation failed')}")
        self._phase_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #d33;"
        )
        # Stop the indeterminate animation and show an empty bar.
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._timer.stop()
        self._poll_timer.stop()
        self._countdown_label.setVisible(False)
        self._reboot_spinner.setVisible(False)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)
        self._webapp_btn.setVisible(False)

    # ------------------------------------------------------------------
    # Reboot countdown (auto-reboot after a successful installation)
    # ------------------------------------------------------------------

    def _start_countdown(self):
        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._countdown_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #b04a00;"
        )
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
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)

    def _do_reboot(self):
        if self._reboot_sent or self._reboot_cancelled:
            return
        self._reboot_sent = True
        self._timer.stop()
        self._countdown_label.setText("🔄 Restarting the Raspberry Pi…")
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)
        # The web interface is unreachable while the Pi reboots: disable the
        # button, show a spinner, and poll until it comes back online.
        self._disable_webapp_for_reboot()
        if self.controller is not None:
            self.controller.reboot_target()

    # ------------------------------------------------------------------
    # Web interface availability polling
    # ------------------------------------------------------------------

    def _disable_webapp_for_reboot(self):
        self._webapp_btn.setEnabled(False)
        self._webapp_btn.setText("⏳ Waiting for the Pi to come back online…")
        self._seen_down = False
        self._reboot_spinner.setVisible(True)
        self._start_availability_poll()

    def _start_availability_poll(self):
        self._poll_timer.start()
        self._poll_availability()

    def _poll_availability(self):
        if not self.state.target_host:
            return
        threading.Thread(target=self._emit_reachability, daemon=True).start()

    def _emit_reachability(self):
        self._reachable.emit(self._check_reachable())

    def _check_reachable(self) -> bool:
        """Return True if the web interface host/port accepts a connection."""
        url = self.state.webapp_url or f"http://{self.state.target_host}"
        parsed = urlparse(url)
        host = parsed.hostname or self.state.target_host
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                return s.connect_ex((host, port)) == 0
        except OSError:
            return False

    def _on_reachable(self, reachable):
        if reachable:
            if self._seen_down:
                # The Pi went offline and is back — restart complete.
                self._poll_timer.stop()
                self._reboot_spinner.setVisible(False)
                self._countdown_label.setStyleSheet(
                    "font-size: 20px; font-weight: bold; color: #2a7d2a;"
                )
                if (self.controller is not None
                        and getattr(self.controller, "needs_reader_config", lambda: False)()):
                    self._countdown_label.setText(
                        "✅ Restart complete — the Raspberry Pi is back online. "
                        "Opening the RFID reader configuration…"
                    )
                    self._webapp_btn.setEnabled(True)
                    self._webapp_btn.setText("🌐 Open Web Interface")
                    self._advance_to_reader_config()
                else:
                    self._countdown_label.setText(
                        "✅ Restart complete — the Raspberry Pi is back online. "
                        "You can now close the installer."
                    )
                    self._webapp_btn.setEnabled(True)
                    self._webapp_btn.setText("🌐 Open Web Interface")
            # else: still up from before the reboot took effect — keep polling.
        else:
            self._seen_down = True

    def _advance_to_reader_config(self):
        """Auto-advance to the next page once the Pi is back online.

        The wizard listens for ``WizardEvents.ADVANCE`` and jumps to the next
        *relevant* page (the reader configuration when a manually configured
        reader was selected). The page_id guard makes sure this request only
        applies while the install page is active. Published only once: the
        availability poll may still have an in-flight request queued after the
        timer was stopped, which would otherwise trigger a duplicate
        navigation.
        """
        if self._advanced_to_reader:
            return
        self._advanced_to_reader = True
        self.event_bus.publish(WizardEvents.ADVANCE, {"page_id": self.page_id})

    def _open_webapp(self):
        url = self.state.webapp_url or f"http://{self.state.target_host}"
        QDesktopServices.openUrl(QUrl(url))

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
