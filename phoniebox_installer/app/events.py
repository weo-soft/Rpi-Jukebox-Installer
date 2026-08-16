"""
Event type definitions for the EventBus.

All events are typed string constants. Handlers register for specific
event types and receive typed payloads.
"""

from dataclasses import dataclass, field
from typing import List


# =========================================================================
# Event Types (String Constants)
# =========================================================================

class AppEvents:
    """Application lifecycle events."""
    STARTUP = "app.startup"
    SHUTDOWN = "app.shutdown"
    ERROR = "app.error"
    CANCEL = "app.cancel"


class SshEvents:
    """SSH connection and authentication events."""
    CONNECTING = "ssh.connecting"
    CONNECTED = "ssh.connected"
    DISCONNECTED = "ssh.disconnected"
    AUTH_FAILED = "ssh.auth_failed"
    AUTH_BANNER = "ssh.auth_banner"
    ERROR = "ssh.error"
    CONNECT_REQUEST = "ssh.connect"        # request to open a connection
    DISCONNECT_REQUEST = "ssh.disconnect"  # request to close the connection
    HOST_KEY_UNKNOWN = "ssh.host_key_unknown"   # first connect: needs user confirmation
    HOST_KEY_CHANGED = "ssh.host_key_changed"   # key mismatch vs known_hosts
    HOST_KEY_REJECTED = "ssh.host_key_rejected"  # user declined the unknown key


class DiscoveryEvents:
    """Device discovery events."""
    SCAN_STARTED = "discovery.scan_started"
    DEVICE_FOUND = "discovery.device_found"
    SCAN_COMPLETED = "discovery.scan_completed"
    SCAN_ERROR = "discovery.scan_error"


class CheckEvents:
    """System check events."""
    CHECK_STARTED = "check.started"
    CHECK_PROGRESS = "check.progress"
    CHECK_COMPLETED = "check.completed"
    CHECK_FAILED = "check.failed"


class InstallEvents:
    """Installation execution events."""
    INSTALL_STARTED = "install.started"
    INSTALL_OUTPUT = "install.output"
    INSTALL_PROGRESS = "install.progress"
    INSTALL_COMPLETED = "install.completed"
    INSTALL_FAILED = "install.failed"
    INSTALL_DETAIL = "install.detail"   # detailed remote log (tailed INSTALL-*.log)


class WizardEvents:
    """Wizard navigation events."""
    PAGE_CHANGED = "wizard.page_changed"
    CAN_VALIDATE = "wizard.can_validate"
    WIZARD_FINISHED = "wizard.finished"


# =========================================================================
# Event Payload Dataclasses
# =========================================================================

@dataclass
class DeviceInfo:
    """Information about a discovered Raspberry Pi."""
    ip_address: str
    hostname: str = ""
    mac_address: str = ""
    port: int = 22
    discovery_method: str = ""  # "mdns" | "scan" | "manual"


@dataclass
class SystemCheckResult:
    """Results of the pre-flight system check."""
    success: bool
    os_version: str = ""
    kernel: str = ""
    arch: str = ""
    disk_free_mb: int = 0
    disk_total_mb: int = 0
    memory_mb: int = 0
    has_internet: bool = False
    has_git: bool = False
    has_python: bool = False
    has_pip: bool = False
    existing_installation: bool = False
    existing_version: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class InstallProgress:
    """Progress update during installation."""
    step: str = ""              # Current step description
    percentage: float = 0.0     # 0.0 to 100.0
    output_line: str = ""       # Latest output line
