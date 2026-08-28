"""
Entry point for the Phoniebox Installer application.

Bootstraps the QApplication, EventBus, Controller, and MainWindow.
"""

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.controller import InstallerController
from phoniebox_installer.gui.wizard import Wizard
from phoniebox_installer.ssh.connection import SshConnectionManager
from phoniebox_installer.ssh.sftp import SftpWrapper
from phoniebox_installer.installer.install import InstallManager
from phoniebox_installer.util.theme import apply_light_theme, get_app_stylesheet

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

        # Create and inject the SSH connection manager (M3)
        self.ssh_manager = SshConnectionManager(self.event_bus)
        self.controller.set_ssh_manager(self.ssh_manager)

        # Create and inject the installation manager (M12), wired to the
        # SSH manager via an SFTP wrapper for the config upload.
        self.sftp = SftpWrapper(self.ssh_manager)
        self.install_manager = InstallManager(
            self.event_bus,
            sftp_wrapper=self.sftp,
            ssh_connection=self.ssh_manager,
        )
        self.controller.set_install_manager(self.install_manager)

        # Force a light color scheme so the UI stays readable regardless of
        # the desktop theme (e.g. Breeze Dark leaves white text by default).
        apply_light_theme(self._app)
        # Global control stylesheet (button/checkbox/input contours).
        self._app.setStyleSheet(get_app_stylesheet())

        # Create main window (placeholder — replaced by wizard in M2)
        self._window = MainWindow(self.controller)

    def run(self) -> int:
        """Start the application event loop."""
        self._window.show()
        return self._app.exec()


class MainWindow(QMainWindow):
    """Main application window hosting the installation Wizard."""

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

        # Wizard Page Registry (in order)
        from phoniebox_installer.gui.pages.welcome import WelcomePage
        from phoniebox_installer.gui.pages.discover import DiscoverPage
        from phoniebox_installer.gui.pages.ssh import SshCredentialsPage
        from phoniebox_installer.gui.pages.options import OptionsPage
        from phoniebox_installer.gui.pages.summary import SummaryPage
        from phoniebox_installer.gui.pages.install import InstallPage
        from phoniebox_installer.gui.pages.reader_config import ReaderConfigPage

        page_classes = [
            WelcomePage,
            DiscoverPage,
            SshCredentialsPage,
            OptionsPage,
            SummaryPage,
            InstallPage,
            ReaderConfigPage,
        ]

        self.wizard = Wizard(
            page_classes,
            controller.get_state(),
            get_event_bus(),
            controller,
        )
        self.setCentralWidget(self.wizard)
        self.wizard.set_page(0)  # Start at welcome page

        # Connect wizard signals
        self.wizard.finished.connect(self.close)
        self.wizard.cancelled.connect(self.close)


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
