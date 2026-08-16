"""
Basic tests for the application entry point.

Verifies that the application can be imported and that the main window
can be created without errors.
"""

from PySide6.QtWidgets import QApplication


def test_app_import():
    """Verify the package can be imported."""
    import phoniebox_installer
    assert phoniebox_installer.__version__ == "0.1.0"


def test_main_window_creation(qapp):
    """Verify the main window can be created without errors."""
    from phoniebox_installer.main import MainWindow, get_controller
    window = MainWindow(get_controller())
    assert window.windowTitle() == "Phoniebox Installer"
    assert window.width() == 800
    assert window.height() == 600
    window.close()


def test_qapp_exists(qapp):
    """Verify QApplication instance exists during tests."""
    app = QApplication.instance()
    assert app is not None
    assert app.applicationName() == "pytest-phoniebox-installer"
