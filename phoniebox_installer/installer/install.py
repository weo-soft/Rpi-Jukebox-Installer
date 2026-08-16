"""
Installation Manager — Remote execution of Phoniebox install scripts.

Single execution mode: CONFIG MODE.
Uploads a flat install_config.env via SFTP, then runs the install script
with the --config flag (sources the file). No terminal interaction, no PTY.
"""

import logging
import threading
import tempfile
import os
from enum import Enum
from typing import Optional, Dict

from phoniebox_installer.app.events import InstallEvents, AppEvents

logger = logging.getLogger(__name__)


class InstallMode(Enum):
    CONFIG = "config"    # flat-env-driven, non-interactive (einziger Modus)


class InstallPhase(Enum):
    """Discrete installation phases for progress tracking."""
    CONFIG_UPLOAD = ("config_upload", "Uploading configuration...", 0, 5)
    GIT_DOWNLOAD = ("git_download", "Downloading Phoniebox source (tarball)...", 5, 10)
    SYSTEM_DEPS = ("system_deps", "Installing system dependencies...", 10, 35)
    RASPI_CONFIG = ("raspi_config", "Configuring Raspberry Pi (incl. audio)...", 35, 45)
    JUKEBOX_CORE = ("jukebox_core", "Setting up Jukebox core (Python/venv)...", 45, 55)
    MPD_SETUP = ("mpd_setup", "Configuring MPD...", 55, 60)
    SAMBA_SETUP = ("samba_setup", "Setting up Samba...", 60, 65)
    WEBAPP_DOWNLOAD = ("webapp_download", "Downloading WebApp bundle (precompiled)...", 65, 75)
    KIOSK_RFID = ("kiosk_rfid", "Configuring kiosk mode + RFID reader...", 75, 85)
    BOOT_AUTOHOTSPOT = ("boot_autohotspot", "Optimizing boot time + autohotspot...", 85, 95)
    FINALIZE = ("finalize", "Finalizing installation...", 95, 100)


class InstallManager:
    """
    Orchestrates the remote installation on the Raspberry Pi.

    Config-Mode only: flat env upload + non-interactive script (--config).

    Usage:
        mgr = InstallManager(event_bus, sftp_wrapper=sftp, ssh_connection=ssh)
        mgr.start(state)
        # Events: INSTALL_STARTED → INSTALL_PROGRESS → INSTALL_COMPLETED/FAILED
    """

    def __init__(self, event_bus, sftp_wrapper=None, ssh_connection=None):
        self._event_bus = event_bus
        self._sftp = sftp_wrapper
        self._ssh = ssh_connection  # M3 SshConnectionManager (exec_command)
        self._current_phase: Optional[InstallPhase] = None
        self._cancelled: bool = False
        self._mode: InstallMode = InstallMode.CONFIG

        # Detail log streaming (tail of the remote INSTALL-*.log file)
        self._detail_log_path: Optional[str] = None
        self._detail_thread: Optional[threading.Thread] = None
        self._detail_stop = threading.Event()

        # Subscribe to cancel
        self._event_bus.subscribe(AppEvents.CANCEL, self._on_cancel)

    def start(self, state):
        """
        Start the installation process (Config-Mode).

        :param state: Populated InstallerState
        """
        self._cancelled = False

        # Run in background thread
        thread = threading.Thread(
            target=self._install_thread, args=(state,), daemon=True
        )
        thread.start()

    def cancel(self):
        """Cancel the running installation (Q2: kill the remote process)."""
        self._cancelled = True
        # Config-Mode: interrupt the remote install via M3.
        if self._ssh is not None:
            self._ssh.cancel_current()
        # NOTE: killing mid-`apt` may leave the Pi half-configured.

    # ------------------------------------------------------------------
    # Script Compatibility Check
    # ------------------------------------------------------------------

    def _config_support_check(self, state) -> None:
        """
        Verify the target install-jukebox.sh supports `--config` (M18 Phase 1).

        Downloads the entry script once and greps it for the `--config` flag
        via exec_command. Raises a clear RuntimeError if the flag is absent
        (older script versions) — the installer does NOT fall back to any
        PTY/prompt-simulation mode.
        """
        if self._ssh is None:
            raise RuntimeError("SSH connection not available")

        captured: Dict[str, str] = {}

        def _on_line(line: str):
            captured["last"] = line.strip()

        cmd = (
            f"wget -qO /tmp/install-jukebox.sh "
            f"https://raw.githubusercontent.com/{state.git_user}/"
            f"RPi-Jukebox-RFID/{state.git_branch}/installation/install-jukebox.sh && "
            f"(grep -q -- '--config' /tmp/install-jukebox.sh && echo CONFIG || echo MISSING)"
        )
        self._ssh.exec_command(cmd, on_line=_on_line)
        if captured.get("last") != "CONFIG":
            raise RuntimeError(
                "install-jukebox.sh on this branch does not support --config. "
                "Please update the Phoniebox installation scripts."
            )

    # ------------------------------------------------------------------
    # Installation Thread
    # ------------------------------------------------------------------

    def _install_thread(self, state):
        try:
            self._config_support_check(state)

            self._event_bus.publish(InstallEvents.INSTALL_STARTED, {
                "mode": self._mode.value,
            })

            self._install_config_mode(state)

            if self._cancelled:
                return

            self._event_bus.publish(InstallEvents.INSTALL_COMPLETED, {
                "message": "Installation completed successfully!",
                "webapp_url": f"http://{state.target_host}",  # WebApp läuft via nginx auf Port 80
            })

        except Exception as e:
            logger.error(f"Installation failed: {e}", exc_info=True)
            self._event_bus.publish(InstallEvents.INSTALL_FAILED, {
                "error": str(e),
            })
        finally:
            self._stop_detail_tail()

    def _install_config_mode(self, state):
        """
        Config-driven installation (preferred).

        1. Generate flat install_config.env from state
        2. Upload via SFTP to /tmp/install_config.env
        3. Run install script with --config flag (sources the file)
        4. Stream output via exec_command (no PTY needed!)
        """
        from phoniebox_installer.installer.config import ConfigManager

        # Phase: Generate + Upload Config
        self._set_phase(InstallPhase.CONFIG_UPLOAD)

        cfg = ConfigManager()
        config_env = cfg.generate_install_config_env(state)

        # Write the flat KEY=VALUE file locally
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False
        ) as f:
            f.write(config_env)
            local_path = f.name

        try:
            # Upload to Pi
            if self._sftp:
                self._sftp.put(local_path, "/tmp/install_config.env")

            # Download + run install-jukebox.sh with --config (non-interactive).
            # Output is streamed via SshConnectionManager.exec_command (no PTY).
            self._set_phase(InstallPhase.GIT_DOWNLOAD)
            cmd = (
                f"wget -qO /tmp/install-jukebox.sh "
                f"https://raw.githubusercontent.com/{state.git_user}/"
                f"RPi-Jukebox-RFID/{state.git_branch}/installation/install-jukebox.sh && "
                f"bash /tmp/install-jukebox.sh --config /tmp/install_config.env"
            )
            exit_status = self._ssh.exec_command(cmd, on_line=self._on_install_line)
            if exit_status != 0:
                raise RuntimeError(
                    f"install-jukebox.sh exited with status {exit_status}"
                )

        finally:
            os.unlink(local_path)

    # ------------------------------------------------------------------
    # Detail log streaming
    # ------------------------------------------------------------------

    def _on_install_line(self, line: str):
        """Handle a console line from the install script.

        Publishes it as INSTALL_OUTPUT and detects the remote log file path,
        starting a tail of that file for the detailed live log.
        """
        self._event_bus.publish(InstallEvents.INSTALL_OUTPUT, {"line": line})
        if line.startswith("INSTALLATION_LOGFILE="):
            path = line.split("=", 1)[1].strip()
            if path and path != self._detail_log_path:
                self._detail_log_path = path
                self._start_detail_tail()

    def _start_detail_tail(self):
        """Tail the remote install log file (detailed view)."""
        if self._detail_log_path is None or self._ssh is None:
            return
        self._detail_stop.clear()

        def _run():
            def _line(line):
                self._event_bus.publish(InstallEvents.INSTALL_DETAIL, {"line": line})

            try:
                self._ssh.stream_command(
                    f"tail -n +1 -f '{self._detail_log_path}'",
                    on_line=_line,
                    stop_event=self._detail_stop,
                )
            except Exception as e:
                logger.debug(f"Detail log tail stopped: {e}")

        self._detail_thread = threading.Thread(
            target=_run, daemon=True, name="install-detail-tail"
        )
        self._detail_thread.start()

    def _stop_detail_tail(self):
        """Stop the detail log tail thread."""
        self._detail_stop.set()
        if self._detail_thread is not None and self._detail_thread.is_alive():
            self._detail_thread.join(timeout=2.0)
        self._detail_thread = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_phase(self, phase: InstallPhase):
        """Update current phase and broadcast progress."""
        self._current_phase = phase
        self._event_bus.publish(InstallEvents.INSTALL_PROGRESS, {
            "step": phase.value[1],
            "percentage": float(phase.value[2]),
        })

    def _on_cancel(self, payload: dict):
        """Handle cancellation request."""
        self.cancel()
