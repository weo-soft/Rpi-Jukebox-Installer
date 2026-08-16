"""Finish page — installation result."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class FinishPage(BasePage):
    page_id = "finish"
    title = "Finish"
    subtitle = "Installation result."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("(Implementation in Milestone 14)"))
