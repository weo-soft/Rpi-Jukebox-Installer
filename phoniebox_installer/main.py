"""
Entry point for the Phoniebox Installer application.

Bootstraps the QApplication, EventBus, Controller, and MainWindow.
"""

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.controller import InstallerController

logger = logging.getLogger(__name__)


# =========================================================================
# Global singletons (accessible via get_* functions)
# =========================================================================

_event_bus: EventBus = None
_controller: InstallerController = None


def get_event_bus() -> EventBus:
    """Get the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_controller() -> InstallerController:
    """Get the global InstallerController singleton."""
    global _controller
    if _controller is None:
        _controller = InstallerController(get_event_bus())
    return _controller


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to a resource file (dev + PyInstaller)."""
    import os
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(Path(__file__).parent.parent, relative_path)


# =========================================================================
# Application Bootstrap
# =========================================================================

class Application:
    """
    Bootstraps the QApplication, EventBus, Controller, and MainWindow.

    Usage:
        app = Application(sys.argv)
        sys.exit(app.run())
    """

    def __init__(self, argv):
        self._app = QApplication(argv)
        self._app.setApplicationName("Phoniebox Installer")
        self._app.setOrganizationName("Phoniebox")
        self._app.setApplicationVersion(
            __import__('phoniebox_installer').__version__
        )

        # Initialize singletons
        self.event_bus = get_event_bus()
        self.controller = get_controller()

        # Apply base stylesheet
        self._app.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
        """)

        # Create main window (placeholder — replaced by wizard in M2)
        self._window = MainWindow(self.controller)

    def run(self) -> int:
        """Start the application event loop."""
        self._window.show()
        return self._app.exec()


class MainWindow(QMainWindow):
    """Main application window (placeholder — will contain the Wizard in M2)."""

    def __init__(self, controller: InstallerController):
        super().__init__()

        self.controller = controller

        self.setWindowTitle("Phoniebox Installer")
        self.resize(800, 600)

        # Center on screen
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        label = QLabel(
            f"Phoniebox Installer v{__import__('phoniebox_installer').__version__}\n\n"
            "EventBus + Controller initialized.\n"
            "Wizard framework coming in M2..."
        )
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 16px; padding: 40px;")
        layout.addWidget(label)


def main():
    """Application entry point."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    app = Application(sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())

