"""Welcome page — select installation mode."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class WelcomePage(BasePage):
    page_id = "welcome"
    title = "Welcome"
    subtitle = "Set up your Phoniebox RFID Jukebox"

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Choose whether to perform a fresh installation "
            "or update an existing Phoniebox.\n\n"
            "(Implementation in Milestone 5)"
        ))
