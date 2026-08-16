"""Tests for the dual-log logging system."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from phoniebox_installer.util.logger import PhonieboxLogger


@pytest.fixture
def clean_logging():
    """Reset root logger state before and after each test."""
    root = logging.getLogger()
    root.handlers.clear()
    yield root
    root.handlers.clear()


def _rotating_handlers():
    root = logging.getLogger()
    return [h for h in root.handlers if isinstance(h, RotatingFileHandler)]


def test_setup_creates_log_file(tmp_path, clean_logging):
    """setup() creates a rotating debug log file in the log dir."""
    PhonieboxLogger.setup(level=logging.DEBUG, log_dir=tmp_path)

    debug_log = tmp_path / "installer.log"
    assert debug_log.exists()

    # A rotating file handler is attached to the root logger
    assert len(_rotating_handlers()) == 1


def test_rotation_configuration(tmp_path, clean_logging):
    """RotatingFileHandler is configured for 5MB with 3 backups."""
    PhonieboxLogger.setup(level=logging.DEBUG, log_dir=tmp_path)

    rotating = _rotating_handlers()[0]
    assert rotating.maxBytes == 5 * 1024 * 1024
    assert rotating.backupCount == 3


def test_install_log_created(tmp_path, clean_logging):
    """create_install_log() creates a new per-run log file and returns its handler."""
    PhonieboxLogger.setup(level=logging.DEBUG, log_dir=tmp_path)
    handler = PhonieboxLogger.create_install_log(log_dir=tmp_path)

    assert Path(handler.baseFilename).name.startswith("install-")
    assert Path(handler.baseFilename).exists()

    # Cleanup: remove the per-run handler to avoid accumulation
    logging.getLogger().removeHandler(handler)


def test_console_output(tmp_path, clean_logging, capsys):
    """Log messages appear on stdout."""
    PhonieboxLogger.setup(level=logging.DEBUG, log_dir=tmp_path)
    logging.getLogger("test.console").info("hello-from-test")

    captured = capsys.readouterr()
    assert "hello-from-test" in captured.out
