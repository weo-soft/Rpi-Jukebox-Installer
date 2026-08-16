"""Device discovery page."""

from PySide6.QtWidgets import QLabel, QVBoxLayout
from phoniebox_installer.gui.pages.base import BasePage


class DiscoverPage(BasePage):
    page_id = "discover"
    title = "Find Your Raspberry Pi"
    subtitle = "Discover your Raspberry Pi on the local network."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("(Implementation in Milestone 6)"))
