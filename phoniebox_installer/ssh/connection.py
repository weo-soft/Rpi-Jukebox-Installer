"""
SSH Connection Manager using Paramiko.

Provides asynchronous (threaded) SSH connection establishment with
password, key-file, and default ~/.ssh/id_rsa authentication.

All communication with the GUI goes through the EventBus.
"""

import base64
import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable

import paramiko

from phoniebox_installer.app.events import SshEvents

logger = logging.getLogger(__name__)

DEFAULT_KNOWN_HOSTS = Path.home() / ".phoniebox-installer" / "known_hosts"


class _TrustOnFirstUsePolicy(paramiko.MissingHostKeyPolicy):
    """TOFU policy: ask the user (via EventBus) and persist accepted keys."""

    def __init__(self, manager: "SshConnectionManager"):
        self._manager = manager

    def missing_host_key(self, client, hostname, key):
        self._manager._handle_missing_host_key(client, hostname, key)


class SshConnectionManager:
    """
    Manages a single SSH connection to a Raspberry Pi.

    Features:
    - Threaded connection (non-blocking GUI)
    - Password and key-file authentication
    - Keep-alive pings
    - EventBus integration (SshEvents.CONNECTED, AUTH_FAILED, ERROR)
    """

    def __init__(self, event_bus, known_hosts_path: Optional[Path] = None):
        self._event_bus = event_bus
        self._known_hosts_path = known_hosts_path or DEFAULT_KNOWN_HOSTS
        self._client: Optional[paramiko.SSHClient] = None
        self._connected: bool = False
        self._host: str = ""
        self._port: int = 22
        self._user: str = ""
        self._keep_alive_thread: Optional[threading.Thread] = None
        self._keep_alive_stop: threading.Event = threading.Event()
        self._active_channel: Optional[paramiko.Channel] = None

        # TOFU decision state (written by the GUI thread, read by the connect thread)
        self._host_key_decision: threading.Event = threading.Event()
        self._host_key_accepted: bool = False
        self._host_key_rejected: bool = False

        # Subscribe to connect requests
        self._event_bus.subscribe(SshEvents.CONNECT_REQUEST, self._on_connect_request)
        self._event_bus.subscribe(SshEvents.DISCONNECT_REQUEST, self._on_disconnect_request)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def client(self) -> Optional[paramiko.SSHClient]:
        """The underlying Paramiko SSHClient (None if not connected)."""
        return self._client

    @property
    def is_connected(self) -> bool:
        """Whether an authenticated SSH session is active."""
        return self._connected and self._client is not None

    def connect(self, host: str, port: int = 22,
                user: str = "pi", password: str = "",
                key_filename: Optional[str] = None):
        """
        Establish an SSH connection (asynchronous).

        Runs in a background thread. Results are published via EventBus:
        - SshEvents.CONNECTED on success
        - SshEvents.AUTH_FAILED on authentication failure

        :param host: IP or hostname of the Raspberry Pi
        :param port: SSH port (default: 22)
        :param user: SSH username (default: "pi")
        :param password: SSH password (optional if using key)
        :param key_filename: Path to SSH private key (optional)
        """
        self._host = host
        self._port = port
        self._user = user

        self._event_bus.publish(SshEvents.CONNECTING, {
            "host": host, "port": port, "user": user
        })

        thread = threading.Thread(
            target=self._connect_thread,
            args=(host, port, user, password, key_filename),
            daemon=True,
            name="ssh-connect"
        )
        thread.start()

    def disconnect(self):
        """Disconnect the SSH session and stop keep-alive."""
        self._stop_keep_alive()

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        self._connected = False
        self._event_bus.publish(SshEvents.DISCONNECTED, {
            "host": self._host
        })
        logger.info(f"Disconnected from {self._host}")

    def exec_command(self, command: str, timeout: float = 3600.0,
                     on_line: Optional[Callable[[str], None]] = None) -> int:
        """
        Execute a command non-interactively and stream its output line by line.

        Used by InstallManager (M12) and System-Check (M8): runs `command` via
        `paramiko.SSHClient.get_transport().open_session()`, publishes each
        output line as an InstallEvents.INSTALL_OUTPUT event, and returns the
        exit status.

        :param command: Shell command to execute on the target
        :param timeout: Hard overall deadline in seconds (0 = no limit)
        :param on_line: Optional per-line callback (defaults to EventBus publish)
        :return: Exit status code (0 = success)
        :raises RuntimeError: on transport failure or timeout (NEVER returns None —
            M12 must not confuse "no transport" with success)
        """
        from phoniebox_installer.app.events import InstallEvents

        if not self.is_connected:
            raise RuntimeError("exec_command: SSH not connected")

        transport = self._client.get_transport()
        if transport is None or not transport.is_active():
            raise RuntimeError("exec_command: SSH transport not active")

        channel = transport.open_session()
        channel.settimeout(1.0)
        self._active_channel = channel
        deadline = time.monotonic() + timeout if timeout else None

        def _emit(data: bytes):
            for line in data.decode('utf-8', errors='replace').splitlines():
                if line:
                    if on_line:
                        on_line(line)
                    else:
                        self._event_bus.publish(
                            InstallEvents.INSTALL_OUTPUT, {"line": line}
                        )

        try:
            channel.exec_command(command)
            while True:
                if channel.recv_ready():
                    _emit(channel.recv(4096))
                if channel.recv_stderr_ready():
                    _emit(channel.recv_stderr(4096))
                if channel.exit_status_ready():
                    break
                if channel.closed:
                    break
                if deadline and time.monotonic() > deadline:
                    raise RuntimeError(f"exec_command timed out after {timeout}s")
                time.sleep(0.05)
            return channel.recv_exit_status()
        finally:
            if self._active_channel is channel:
                self._active_channel = None
            channel.close()

    def cancel_current(self):
        """
        Interrupt the running exec_command() (used by M12 Cancel, Q2).

        Primary: run `pkill -f install-jukebox.sh` in a second session to
        terminate the remote install. Secondary (if a PTY channel is active):
        send Ctrl+C. NOTE: killing mid-`apt` can leave the Pi half-configured
        — the UI (M13) must warn the user.
        """
        channel = self._active_channel
        if channel is not None:
            try:
                channel.send(b"\x03")
            except Exception:
                pass
        try:
            self._client.exec_command("pkill -f install-jukebox.sh")
        except Exception as e:
            logger.warning(f"Remote kill failed: {e}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_connect_request(self, payload: dict):
        """EventBus handler for 'ssh.connect' events."""
        self.connect(
            host=payload.get("host", ""),
            port=payload.get("port", 22),
            user=payload.get("user", "pi"),
            password=payload.get("password", ""),
            key_filename=payload.get("key_file"),
        )

    def _on_disconnect_request(self, payload: dict):
        """EventBus handler for 'ssh.disconnect' events."""
        self.disconnect()

    def confirm_host_key(self, accept: bool):
        """Resolve a pending TOFU prompt (called by the controller from the GUI)."""
        self._host_key_accepted = bool(accept)
        self._host_key_rejected = not bool(accept)
        self._host_key_decision.set()

    def _handle_missing_host_key(self, client, hostname, key):
        """Block the connect thread until the user trusts (or rejects) the key."""
        fingerprint = base64.b64encode(
            hashlib.sha256(key.asbytes()).digest()
        ).rstrip(b"=").decode()

        self._host_key_decision.clear()
        self._host_key_accepted = False
        self._host_key_rejected = False

        self._event_bus.publish(SshEvents.HOST_KEY_UNKNOWN, {
            "host": hostname,
            "key_type": key.get_name(),
            "fingerprint": fingerprint,
        })

        if not self._host_key_decision.wait(timeout=120.0):
            raise paramiko.SSHException("Host key confirmation timed out.")
        if not self._host_key_accepted:
            self._host_key_rejected = True
            raise paramiko.SSHException("Host key rejected by user.")

        # Accept: register the key so connect() proceeds and save_host_keys persists it.
        client.get_host_keys().add(hostname, key.get_name(), key)

    def _connect_thread(
        self, host: str, port: int, user: str,
        password: str, key_filename: Optional[str],
    ):
        """Background thread: establish SSH connection (TOFU host keys)."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(_TrustOnFirstUsePolicy(self))

        self._host_key_rejected = False
        self._known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
        if self._known_hosts_path.is_file():
            try:
                client.load_host_keys(str(self._known_hosts_path))
            except OSError as e:
                logger.warning(f"Could not load known_hosts: {e}")

        try:
            # Determine auth method
            if key_filename:
                client.connect(
                    host, port=port, username=user,
                    key_filename=key_filename,
                    timeout=15,
                    banner_timeout=10,
                    auth_timeout=15,
                    look_for_keys=False,
                    allow_agent=False,
                )
            elif password:
                client.connect(
                    host, port=port, username=user,
                    password=password,
                    timeout=15,
                    banner_timeout=10,
                    auth_timeout=15,
                    look_for_keys=True,
                )
            else:
                # Try default SSH key
                client.connect(
                    host, port=port, username=user,
                    timeout=15,
                    banner_timeout=10,
                    auth_timeout=15,
                    look_for_keys=True,
                )

            self._client = client
            self._connected = True
            self._start_keep_alive()

            # Persist newly accepted host keys (TOFU).
            try:
                client.save_host_keys(str(self._known_hosts_path))
            except OSError as e:
                logger.warning(f"Could not save known_hosts: {e}")

            self._event_bus.publish(SshEvents.CONNECTED, {
                "host": host,
                "port": port,
                "user": user,
            })
            logger.info(f"SSH connected: {user}@{host}:{port}")

        except paramiko.BadHostKeyException as e:
            logger.error(f"SSH host key changed: {e}")
            self._event_bus.publish(SshEvents.HOST_KEY_CHANGED, {
                "host": host,
                "reason": str(e),
            })
        except paramiko.AuthenticationException as e:
            logger.warning(f"SSH auth failed: {e}")
            self._event_bus.publish(SshEvents.AUTH_FAILED, {
                "host": host,
                "reason": str(e),
            })
        except paramiko.SSHException as e:
            if self._host_key_rejected:
                logger.info("SSH host key rejected by user")
                self._event_bus.publish(SshEvents.HOST_KEY_REJECTED, {"host": host})
            else:
                logger.error(f"SSH error: {e}")
                self._event_bus.publish(SshEvents.ERROR, {
                    "host": host,
                    "error": str(e),
                })
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            self._event_bus.publish(SshEvents.ERROR, {
                "host": host,
                "error": f"Connection failed: {str(e)}",
            })

    def _start_keep_alive(self):
        """Start a background thread that sends periodic keep-alive pings."""
        self._keep_alive_stop.clear()
        self._keep_alive_thread = threading.Thread(
            target=self._keep_alive_loop,
            daemon=True,
            name="ssh-keepalive"
        )
        self._keep_alive_thread.start()

    def _stop_keep_alive(self):
        """Stop the keep-alive thread."""
        self._keep_alive_stop.set()
        if self._keep_alive_thread and self._keep_alive_thread.is_alive():
            self._keep_alive_thread.join(timeout=2.0)

    def _keep_alive_loop(self):
        """Send periodic transport-level keep-alive messages."""
        while not self._keep_alive_stop.is_set():
            self._keep_alive_stop.wait(timeout=30.0)
            if self._client and self._connected:
                try:
                    transport = self._client.get_transport()
                    if transport and transport.is_active():
                        transport.send_ignore()
                    else:
                        logger.warning("SSH transport lost")
                        self._connected = False
                        self._event_bus.publish(SshEvents.DISCONNECTED, {
                            "host": self._host,
                            "reason": "Connection lost"
                        })
                        break
                except Exception as e:
                    logger.error(f"Keep-alive failed: {e}")
                    break
