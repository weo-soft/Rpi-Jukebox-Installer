"""Install page — live log and progress."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar,
    QPlainTextEdit, QMessageBox, QCheckBox,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import InstallEvents


class InstallPage(BasePage):
    page_id = "install"
    title = "Installing Phoniebox"
    subtitle = "Live installation log and progress."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._step_lines = []
        self._detail_lines = []
        self._show_details = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._phase_label = QLabel("")
        layout.addWidget(self._phase_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        layout.addWidget(self._progress)

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
        # Start the installation
        if self.controller is not None:
            self.controller.start_install()

    def _on_install_started(self, payload):
        self._progress.setRange(0, 0)
        self._log.clear()
        self._step_lines = []
        self._detail_lines = []
        self._cancel_btn.setEnabled(True)

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
        self._cancel_btn.setEnabled(False)

    def _on_failed(self, payload):
        self._phase_label.setText(f"❌ {payload.get('error', 'Installation failed')}")
        self._cancel_btn.setEnabled(False)

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

    def on_leave(self):
        self.event_bus.unsubscribe(InstallEvents.INSTALL_STARTED, self._on_install_started)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_OUTPUT, self._on_output)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_PROGRESS, self._on_progress)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_COMPLETED, self._on_completed)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_FAILED, self._on_failed)
        self.event_bus.unsubscribe(InstallEvents.INSTALL_DETAIL, self._on_detail)
