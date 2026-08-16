"""Resource path helpers (dev + PyInstaller)."""

import os
import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource file.

    Works both in development (filesystem) and in PyInstaller bundles (temp dir).

    :param relative_path: Path relative to the package root
                          (e.g., 'resources/icons/phoniebox_logo.png')
    :return: Absolute filesystem path
    """
    if getattr(sys, 'frozen', False):
        base_path = os.path.join(sys._MEIPASS, 'phoniebox_installer')
    else:
        base_path = Path(__file__).parent.parent
    return os.path.join(base_path, relative_path)
