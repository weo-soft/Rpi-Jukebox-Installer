"""
Global installer state (dataclass-based).

The InstallerController holds a single InstallerState instance
that is passed between wizard pages. Pages read from this state
to populate their fields and write to it on validation/save.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InstallerState:
    """
    Global, mutable state shared across all wizard pages.

    Pages read values to pre-fill their UI and write values
    back when the user confirms (on page commit). The controller
    provides the state to each page via the wizard framework.
    """

    # =========================================================================
    # Mode
    # =========================================================================

    # "new" = fresh installation (v1); "update" = future goal
    mode: str = "new"

    # =========================================================================
    # Target Device
    # =========================================================================

    target_host: str = ""           # IP address or hostname
    target_hostname: str = ""       # mDNS hostname (e.g., "phoniebox.local")
    ssh_user: str = "pi"
    ssh_password: str = ""
    ssh_key_file: Optional[str] = None
    ssh_port: int = 22
    ssh_authenticated: bool = False

    # =========================================================================
    # System Check Results (populated by SystemCheckPage, M8)
    # =========================================================================

    os_version: str = ""
    kernel: str = ""
    arch: str = ""                  # "armv6l" | "armv7l" | "aarch64"
    disk_free_mb: int = 0
    disk_total_mb: int = 0
    memory_mb: int = 0
    has_internet: bool = False
    has_git: bool = False
    has_python: bool = False
    has_pip: bool = False
    existing_installation: bool = False
    existing_version: str = ""
    existing_install_action: str = ""  # "" | "remove" | "backup" — gewählt bei bestehender Installation (M8)

    # =========================================================================
    # Installation Options (populated by OptionsPage, M10)
    # Real customize_options.sh flags (see 01_default_config.sh)
    # =========================================================================

    enable_static_ip: bool = True
    disable_ipv6: bool = True
    enable_autohotspot: bool = False
    disable_bluetooth: bool = True
    disable_onboard_audio: bool = False
    setup_mpd: bool = True
    enable_mpd_overwrite_install: bool = True
    enable_rfid_reader: bool = True
    rfid_reader_module: str = ""    # real reader module name (e.g., "pn532_i2c_py532")
    enable_samba: bool = False
    enable_webapp: bool = True
    enable_kiosk_mode: bool = False
    update_raspi_os: bool = False

    # Audio (driven via expanded M18: setup_hifiberry.sh / run_configure_audio.py)
    audio_hifiberry_board: str = ""  # e.g., "hifiberry-dacplus"

    # WebApp (precompiled bundle)
    enable_webapp_prod_download: str = "release-only"

    # Plugins (future placeholders)
    selected_plugins: List[str] = field(default_factory=list)

    # =========================================================================
    # Phoniebox Source (populated by OptionsPage, M10)
    # =========================================================================

    git_user: str = "MiczFlor"
    git_branch: str = "future3/main"

    # =========================================================================
    # Installation Result (populated by InstallPage, M13)
    # =========================================================================

    install_success: bool = False
    install_message: str = ""
    webapp_url: str = ""
