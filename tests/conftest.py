"""
Pytest fixtures for the Phoniebox Installer test suite.

Provides a shared QApplication instance for all GUI tests,
avoiding the "QApplication already exists" error.
"""

import sys
import pytest

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """
    Session-scoped QApplication fixture.

    Required by pytest-qt for all GUI tests. Only one QApplication
    instance can exist per process, so we create it at session scope.

    Ensures a QApplication exists before any test that requires Qt.
    The qapp name includes "pytest" to allow test discovery to
    distinguish it from the real application.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationName("pytest-phoniebox-installer")
    yield app


@pytest.fixture(scope="session")
def resource_dir():
    """Return the path to the project's resource directory."""
    from pathlib import Path
    return Path(__file__).parent.parent / "phoniebox_installer" / "resources"
