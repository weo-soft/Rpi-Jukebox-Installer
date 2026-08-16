"""
Dual-log system: user-visible installation log + technical debug log.

The user log streams to the GUI via EventBus (as INSTALL_OUTPUT events).
The technical log writes to rotating log files with full details.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path.home() / ".phoniebox-installer" / "logs"
DEFAULT_FORMAT = (
    "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
DETAILED_FORMAT = (
    "%(asctime)s [%(name)s:%(lineno)d] %(levelname)s: %(message)s"
)


class PhonieboxLogger:
    """
    Configures the Python logging system for the installer.

    Sets up:
    - Console handler (stdout) for development
    - Rotating file handler for persistent debug logs
    - Per-installation log file for each run

    Usage:
        PhonieboxLogger.setup(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.info("Installer started")
    """

    @staticmethod
    def setup(level: int = logging.DEBUG,
              log_dir: Path = None):
        """
        Initialize the logging system.

        :param level: Log level (DEBUG, INFO, WARNING, ERROR)
        :param log_dir: Directory for log files
        """
        log_dir = log_dir or LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # 1. Console handler (stdout)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        root_logger.addHandler(console)

        # 2. Rotating file handler (debug log, persistent)
        debug_log = log_dir / "installer.log"
        file_handler = RotatingFileHandler(
            str(debug_log),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        root_logger.addHandler(file_handler)

        # 3. Suppress noisy third-party loggers
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        logging.getLogger("zeroconf").setLevel(logging.WARNING)

        logging.info(f"Logging initialized. Debug log: {debug_log}")

    @staticmethod
    def create_install_log(log_dir: Path = None) -> logging.FileHandler:
        """
        Create a dedicated log file for this installation run.

        The returned FileHandler is added to the root logger and MUST be
        removed again after the run (logging.getLogger().removeHandler(handler))
        to avoid accumulating handlers across multiple runs.

        :param log_dir: Directory for log files
        :return: The FileHandler for the new log file
                 (the file path is available via ``handler.baseFilename``)
        """
        log_dir = log_dir or LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = log_dir / f"install-{timestamp}.log"

        handler = logging.FileHandler(str(log_file))
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        logging.getLogger().addHandler(handler)

        logging.info(f"Installation log: {log_file}")
        return handler
