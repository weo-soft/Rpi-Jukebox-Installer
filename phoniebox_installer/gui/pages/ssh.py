"""SSH credentials page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class SshCredentialsPage(BasePage):
    page_id = "ssh"
    title = "Connect to Your Raspberry Pi"
    subtitle = "Enter your SSH credentials and test the connection."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("(Implementation in Milestone 7)"))
