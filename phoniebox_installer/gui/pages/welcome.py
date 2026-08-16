"""Welcome page — select installation mode."""

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.util.resources import get_resource_path


class WelcomePage(BasePage):
    page_id = "welcome"
    title = "Welcome"
    subtitle = "Set up your Phoniebox RFID Jukebox"

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._selected_mode = None
        self._new_btn = None
        self._update_btn = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setSpacing(16)

        # Spacer top
        main_layout.addStretch()

        # Logo
        logo_label = QLabel()
        logo_path = get_resource_path("resources/icons/phoniebox_logo.png")
        logo_pixmap = QPixmap(logo_path)
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(
                128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        logo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(logo_label)

        # Title
        title_label = QLabel("Phoniebox Installer")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "This wizard will guide you through installing\n"
            "RPi-Jukebox-RFID (future3) on your Raspberry Pi."
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #555; font-size: 14px;")
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        main_layout.addSpacing(16)

        # Question
        question_label = QLabel("What would you like to do?")
        question_label.setAlignment(Qt.AlignCenter)
        question_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        main_layout.addWidget(question_label)

        # Option cards container
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        cards_layout.setAlignment(Qt.AlignCenter)

        # New Installation card
        self._new_btn = self._create_option_card(
            "🆕",
            "New Installation",
            "Set up a fresh Phoniebox\non a new Raspberry Pi",
        )
        self._new_btn.clicked.connect(lambda: self._select_mode("new"))
        cards_layout.addWidget(self._new_btn)

        # Update card (disabled in v1 — future goal)
        self._update_btn = self._create_option_card(
            "🔄",
            "Update Existing (coming soon)",
            "Upgrade an already installed\nPhoniebox to the latest version",
        )
        self._update_btn.setEnabled(False)
        cards_layout.addWidget(self._update_btn)

        main_layout.addLayout(cards_layout)

        # Spacer bottom
        main_layout.addStretch()

        # Version info
        version_label = QLabel("v0.1.0 — future3")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #999; font-size: 12px;")
        main_layout.addWidget(version_label)

    def _create_option_card(self, emoji: str, title: str,
                            description: str) -> QPushButton:
        """Create a stylized option card button (multiline QPushButton)."""
        btn = QPushButton(f"{emoji}\n\n{title}\n{description}")
        btn.setMinimumSize(240, 160)
        btn.setMaximumWidth(300)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setCheckable(True)
        btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #ddd;
                border-radius: 12px;
                padding: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                border-color: #2196F3;
                background-color: #E3F2FD;
            }
            QPushButton:checked {
                border-color: #1976D2;
                background-color: #BBDEFB;
            }
        """)
        return btn

    def _select_mode(self, mode: str):
        """Handle mode selection."""
        self._selected_mode = mode
        # Visual feedback
        self._new_btn.setChecked(mode == "new")
        self._update_btn.setChecked(mode == "update")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        """Restore the previous selection (v1: only 'new' is selectable)."""
        if self.state.mode == "new":
            self._select_mode("new")

    def validate(self):
        """Ensure a mode has been selected."""
        if self._selected_mode is None:
            return (False, "Please select an installation mode.")
        return (True, "")

    def on_leave(self):
        """Save selected mode to state."""
        if self._selected_mode:
            self.state.mode = self._selected_mode
