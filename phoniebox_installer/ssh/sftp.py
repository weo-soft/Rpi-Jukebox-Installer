"""
SFTP wrapper for file transfer operations.

Used to upload configuration files to the Raspberry Pi
before running the installation scripts.
"""

import logging
import os

import paramiko

logger = logging.getLogger(__name__)


class SftpWrapper:
    """
    Simple wrapper around paramiko.SFTPClient.

    Usage:
        sftp = SftpWrapper(ssh_manager)
        sftp.put(local_path, remote_path)
    """

    def __init__(self, ssh_manager):
        """
        :param ssh_manager: SshConnectionManager instance
        """
        self._ssh_manager = ssh_manager

    def _get_sftp(self) -> paramiko.SFTPClient:
        """Get or open an SFTP session."""
        if self._ssh_manager.client is None:
            raise RuntimeError("SSH not connected")
        transport = self._ssh_manager.client.get_transport()
        if transport is None or not transport.is_active():
            raise RuntimeError("SSH transport not active")
        return transport.open_sftp_client()

    def put(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a local file to the remote Raspberry Pi.

        :param local_path: Path on the local machine
        :param remote_path: Destination path on the Raspberry Pi
        :return: True if successful
        """
        if not os.path.isfile(local_path):
            logger.error(f"Local file not found: {local_path}")
            return False

        try:
            sftp = self._get_sftp()
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            try:
                sftp.stat(remote_dir)
            except OSError:
                self._mkdir_p(sftp, remote_dir)

            sftp.put(local_path, remote_path)
            sftp.close()
            logger.info(f"Uploaded: {local_path} → {remote_path}")
            return True
        except Exception as e:
            logger.error(f"SFTP upload failed: {e}")
            return False

    def _mkdir_p(self, sftp, remote_dir: str):
        """Create remote directory recursively (like mkdir -p)."""
        if remote_dir in ("/", "", "."):
            return
        try:
            sftp.stat(remote_dir)
        except OSError:
            self._mkdir_p(sftp, os.path.dirname(remote_dir))
            sftp.mkdir(remote_dir)
