"""Summary page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class SummaryPage(BasePage):
    page_id = "summary"
    title = "Review Your Configuration"
    subtitle = "Review your choices before starting the installation."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("(Implementation in Milestone 11)"))
