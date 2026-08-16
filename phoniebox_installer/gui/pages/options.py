"""Installation options page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class OptionsPage(BasePage):
    page_id = "options"
    title = "Configure Your Installation"
    subtitle = "Customize how Phoniebox is installed."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("(Implementation in Milestone 10)"))
