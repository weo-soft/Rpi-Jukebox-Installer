"""
Entry point for the Phoniebox Installer application.

Creates a QApplication instance, sets up the main window, and starts
the Qt event loop.

Usage:
    python -m phoniebox_installer.main
    phoniebox-installer  # if installed via pip
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource file.

    Works both in development (filesystem) and in PyInstaller bundles (temp dir).

    :param relative_path: Path relative to the package root (e.g., 'resources/icons/app.svg')
    :return: Absolute filesystem path
    """
    import os
    # PyInstaller stores extracted resources in sys._MEIPASS
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = Path(__file__).parent.parent
    return os.path.join(base_path, relative_path)


class MainWindow(QMainWindow):
    """Main application window (temporary Hello World)."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Phoniebox Installer")
        self.resize(800, 600)

        # Center the window
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

        # Hello World content (will be replaced by Wizard in M2)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        label = QLabel("Phoniebox Installer v0.1.0\n\nComing soon...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; padding: 40px;")
        layout.addWidget(label)


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Phoniebox Installer")
    app.setApplicationVersion(__import__('phoniebox_installer').__version__)
    app.setOrganizationName("Phoniebox")

    # Apply base stylesheet (will be expanded in M2)
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
