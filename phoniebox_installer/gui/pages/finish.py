"""Finish page — installation result summary."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QPushButton
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from phoniebox_installer.gui.pages.base import BasePage


class FinishPage(BasePage):
    page_id = "finish"
    title = "Finish"
    subtitle = "Installation result."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._headline = QLabel("")
        self._headline.setWordWrap(True)
        self._headline.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(self._headline)

        self._message = QLabel("")
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        self._webapp_link = QPushButton("🌐 Open Web Interface")
        self._webapp_link.clicked.connect(self._open_webapp)
        layout.addWidget(self._webapp_link)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #d33;")
        layout.addWidget(self._error_label)

        layout.addStretch()

    def on_enter(self):
        """Render success or failure UI based on state.install_success."""
        s = self.state
        if s.install_success:
            self._headline.setText("✅ Installation Complete!")
            self._headline.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #2a7d2a;"
            )
            self._message.setText(
                "Phoniebox has been successfully installed on your Raspberry Pi."
            )
            url = s.webapp_url or f"http://{s.target_host}"
            self._webapp_link.setText(f"🌐 Open Web Interface\n{url}")
            self._webapp_link.setVisible(True)
            self._error_label.setText("")
        else:
            self._headline.setText("❌ Installation Failed")
            self._headline.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #d33;"
            )
            self._message.setText("The installation could not be completed.")
            self._error_label.setText(s.install_message or "Unknown error")
            self._webapp_link.setVisible(False)

    def _open_webapp(self):
        url = self.state.webapp_url or f"http://{self.state.target_host}"
        QDesktopServices.openUrl(QUrl(url))

    def validate(self):
        return (True, "")
