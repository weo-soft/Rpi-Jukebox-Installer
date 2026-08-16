"""
InstallerController — Central orchestrator for the installation wizard.

The controller:
- Holds the global InstallerState
- Provides methods that wizard pages call (e.g., start_discovery, connect_ssh)
- Subscribes to EventBus events to coordinate async operations
- Delegates to SshManager, InstallManager, ConfigManager (future milestones)

Pages should never call SSH/network code directly — they call controller
methods, which delegate to the appropriate manager.
"""

import logging
from typing import Optional

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import AppEvents
from phoniebox_installer.app.state import InstallerState

logger = logging.getLogger(__name__)


class InstallerController:
    """
    Central orchestrator for the Phoniebox installation wizard.

    Holds the global InstallerState and coordinates between
    GUI pages (via EventBus) and backend services (SSH, installer).

    Usage:
        event_bus = EventBus()
        state = InstallerState()
        controller = InstallerController(event_bus, state)
        # Controller subscribes to relevant events automatically
    """

    def __init__(self, event_bus: EventBus, state: InstallerState = None):
        self.event_bus = event_bus
        self.state = state or InstallerState()

        # Backend managers (set by later milestones)
        self._ssh_manager = None       # M3
        self._config_manager = None    # M9
        self._install_manager = None   # M12

        # Discovery workers (created on demand by start_discovery)
        self._mdns = None
        self._scanner = None

        # Register default event handlers
        self._register_handlers()

    # ------------------------------------------------------------------
    # Backend Injection (called by Application bootstrap)
    # ------------------------------------------------------------------

    def set_ssh_manager(self, ssh_manager):
        """Inject the SSH manager instance (from M3)."""
        self._ssh_manager = ssh_manager

    def set_config_manager(self, config_manager):
        """Inject the config manager instance (from M9)."""
        self._config_manager = config_manager

    def set_install_manager(self, install_manager):
        """Inject the install manager instance (from M12)."""
        self._install_manager = install_manager

    # ------------------------------------------------------------------
    # Public API — called by Wizard Pages
    # ------------------------------------------------------------------

    def get_state(self) -> InstallerState:
        """Return the current global state (read-only for display purposes)."""
        return self.state

    def set_mode(self, mode: str):
        """Set installation mode ('new' or 'update')."""
        if mode not in ("new", "update"):
            raise ValueError(f"Invalid mode: {mode}")
        self.state.mode = mode
        logger.info(f"Mode set to: {mode}")

    def set_target(self, host: str, port: int = 22):
        """Set the target Raspberry Pi address."""
        self.state.target_host = host
        self.state.ssh_port = port
        logger.info(f"Target set to: {host}:{port}")

    def set_credentials(self, user: str, password: str = "",
                        key_file: Optional[str] = None):
        """Set SSH credentials."""
        self.state.ssh_user = user
        self.state.ssh_password = password
        self.state.ssh_key_file = key_file
        logger.info(f"Credentials set for user: {user}")

    def request_cancel(self):
        """Request cancellation of the current operation."""
        self.event_bus.publish(AppEvents.CANCEL, {})

    def start_install(self):
        """Start the installation via the injected InstallManager (M12).

        Called by the InstallPage (M13) on_enter(). No-op if the
        InstallManager has not been injected yet.
        """
        if self._install_manager is None:
            logger.error("InstallManager not injected — cannot start install")
            return
        self._install_manager.start(self.state)

    def test_connection(self):
        """Trigger an SSH connection test using the current state credentials.

        Called by the SshCredentialsPage (M7) "Test Connection" button.
        """
        if self._ssh_manager is None:
            logger.error("SSH manager not injected — cannot test connection")
            return
        self._ssh_manager.connect(
            host=self.state.target_host,
            port=self.state.ssh_port,
            user=self.state.ssh_user,
            password=self.state.ssh_password,
            key_filename=self.state.ssh_key_file,
        )

    def confirm_host_key(self, accept: bool):
        """Resolve a pending TOFU host-key prompt (called by M7)."""
        if self._ssh_manager is None:
            logger.error("SSH manager not injected — cannot confirm host key")
            return
        self._ssh_manager.confirm_host_key(accept)

    def start_discovery(self):
        """Start device discovery (called by M6)."""
        from phoniebox_installer.util.network import MdnsDiscovery, PortScanner
        self._mdns = MdnsDiscovery(self.event_bus)
        self._scanner = PortScanner(self.event_bus)
        self._mdns.scan()
        self._scanner.scan_subnet()

    def stop_discovery(self):
        """Stop any running device discovery (called by M6 on_leave)."""
        mdns = getattr(self, "_mdns", None)
        if mdns is not None:
            mdns.stop()
        self._mdns = None
        self._scanner = None

    def run_system_check(self):
        """Trigger the pre-flight system check (called by M8)."""
        from phoniebox_installer.installer.checks import SystemCheckRunner
        if self._ssh_manager is None:
            logger.error("SSH manager not injected — cannot run system check")
            return
        SystemCheckRunner(self._ssh_manager, self.event_bus).run()

    # ------------------------------------------------------------------
    # Internal Event Handlers
    # ------------------------------------------------------------------

    def _register_handlers(self):
        """Subscribe to relevant EventBus events."""
        from phoniebox_installer.app.events import (
            SshEvents, CheckEvents, InstallEvents
        )
        self.event_bus.subscribe(SshEvents.CONNECTED, self._on_ssh_connected)
        self.event_bus.subscribe(SshEvents.DISCONNECTED, self._on_ssh_disconnected)
        self.event_bus.subscribe(SshEvents.AUTH_FAILED, self._on_ssh_auth_failed)
        self.event_bus.subscribe(CheckEvents.CHECK_COMPLETED, self._on_check_completed)
        self.event_bus.subscribe(InstallEvents.INSTALL_COMPLETED, self._on_install_completed)
        self.event_bus.subscribe(InstallEvents.INSTALL_FAILED, self._on_install_failed)

    def _on_ssh_connected(self, payload: dict):
        """Handle successful SSH connection."""
        self.state.ssh_authenticated = True
        logger.info(f"SSH connected to {payload.get('host', 'unknown')}")

    def _on_ssh_auth_failed(self, payload: dict):
        """Handle SSH authentication failure."""
        self.state.ssh_authenticated = False
        logger.warning(f"SSH auth failed: {payload.get('reason', 'unknown')}")

    def _on_ssh_disconnected(self, payload: dict):
        """Handle SSH disconnection (explicit or connection loss)."""
        self.state.ssh_authenticated = False
        logger.warning(f"SSH disconnected: {payload.get('reason', 'unknown')}")

    def _on_check_completed(self, payload: dict):
        """Handle system check completion.

        Payload enthält bereits TYPISIERTE Werte (bools für has_*, int für
        *_mb, str für Versionsinfos) — der SystemCheckRunner (M8) konvertiert
        die Rohstrings vor der Publikation. Zusätzlich liegt die Auswertung
        unter `payload["status"]` (pass|warn|fail).
        """
        self.state.os_version = payload.get('os_version', '')
        self.state.kernel = payload.get('kernel', '')
        self.state.arch = payload.get('arch', '')
        self.state.disk_free_mb = payload.get('disk_free_mb', 0)
        self.state.disk_total_mb = payload.get('disk_total_mb', 0)
        self.state.memory_mb = payload.get('memory_mb', 0)
        self.state.has_internet = payload.get('has_internet', False)
        self.state.has_git = payload.get('has_git', False)
        self.state.has_python = payload.get('has_python', False)
        self.state.has_pip = payload.get('has_pip', False)
        self.state.existing_installation = payload.get('existing_installation', False)
        self.state.existing_version = payload.get('existing_version', '')
        self.state.existing_install_action = payload.get('existing_install_action', '')
        logger.info("System check results stored in state")

    def _on_install_completed(self, payload: dict):
        """Handle successful installation."""
        self.state.install_success = True
        self.state.install_message = payload.get('message', 'Installation complete')
        self.state.webapp_url = payload.get('webapp_url', '')
        logger.info("Installation completed successfully")

    def _on_install_failed(self, payload: dict):
        """Handle installation failure."""
        self.state.install_success = False
        self.state.install_message = payload.get('error', 'Installation failed')
        logger.error(f"Installation failed: {self.state.install_message}")

