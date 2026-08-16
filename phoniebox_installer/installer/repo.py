"""
Repository / existing-installation check utility.

The Phoniebox source is downloaded by install-jukebox.sh itself as a
tarball (wget .../tarball/${GIT_BRANCH} | tar xz) and turned into a git
repository via init_git_repo_from_tardir. The InstallManager therefore
does NOT clone the repository separately.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class RepoSyncer:
    """Checks the target for an existing installation.

    The Phoniebox source is downloaded by install-jukebox.sh itself as a
    tarball (wget .../tarball/${GIT_BRANCH} | tar xz) and turned into a git
    repository via init_git_repo_from_tardir. The InstallManager therefore
    does NOT clone the repository separately.
    """

    def __init__(self, ssh_connection):
        self._ssh = ssh_connection

    def check_existing(self, install_path: str) -> str:
        """Check if an installation already exists at the given path.

        Returns 'EXISTS' or 'NOT_FOUND' (via exec_command output).
        """
        cmd = f"test -d {install_path} && echo EXISTS || echo NOT_FOUND"
        result: Dict[str, str] = {}

        def _on_line(line: str):
            result["last"] = line.strip()

        self._ssh.exec_command(cmd, on_line=_on_line)
        return result.get("last", "NOT_FOUND")
