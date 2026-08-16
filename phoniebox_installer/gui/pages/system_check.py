"""System check page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class SystemCheckPage(BasePage):
    page_id = "system_check"
    title = "System Check"
    subtitle = "Checking your Raspberry Pi before installation."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("(Implementation in Milestone 8)"))
