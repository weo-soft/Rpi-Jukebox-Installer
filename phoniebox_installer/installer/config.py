"""
Configuration Manager for the Phoniebox Installer.

Manages two YAML domains:
1. Installer-local config (~/.phoniebox-installer/config.yaml)
   - Window geometry, language, recent connections
2. Target installation options (mapping to install-jukebox.sh parameters)
   - Real customize_options.sh flags, git source, audio/RFID sub-tools

Uses ruamel.yaml for consistent YAML handling with the Phoniebox core.
"""

import os
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

# Default path for installer-local configuration
DEFAULT_INSTALLER_CONFIG_PATH = Path.home() / ".phoniebox-installer" / "config.yaml"


@dataclass
class InstallationOptions:
    """
    All user-selectable installation options.

    These options map to the real flags in customize_options.sh
    (see 01_default_config.sh) plus the Phoniebox source (GIT_USER/GIT_BRANCH)
    and the audio/RFID sub-tools driven via expanded M18.
    """

    # === Phoniebox source ===
    git_user: str = "MiczFlor"
    git_branch: str = "future3/main"

    # === Real customize_options.sh flags ===
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

    # === Audio HAT overlay (setup_hifiberry.sh) ===
    audio_hifiberry_board: str = ""  # e.g., "hifiberry-dacplus"

    # === WebApp (precompiled bundle) ===
    # Valid values: "release-only" (default) | "true".
    # "false" is unsupported — local WebApp builds were removed; the install fails.
    enable_webapp_prod_download: str = "release-only"

    # === Plugins (future placeholders) ===
    selected_plugins: List[str] = field(default_factory=list)


class ConfigManager:
    """
    Reads and writes installer configuration.

    Usage:
        cfg = ConfigManager()
        cfg.load()
        cfg.get_recent_hosts()  # → ["192.168.1.100", "phoniebox.local"]
        cfg.save_recent_host("192.168.1.101")
        cfg.set_options(options)
        cfg.save()
    """

    def __init__(self, config_path: Path = None):
        self._config_path = config_path or DEFAULT_INSTALLER_CONFIG_PATH
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._data: dict = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """Load configuration from disk. Returns empty dict if not found."""
        if self._config_path.is_file():
            try:
                with open(self._config_path, 'r') as f:
                    self._data = self._yaml.load(f) or {}
                logger.debug(f"Loaded config from {self._config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
                self._data = {}
        else:
            self._data = {}
        return self._data

    def save(self):
        """Persist current configuration to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, 'w') as f:
            self._yaml.dump(self._data, f)
        os.chmod(self._config_path, 0o644)   # Akzeptanzkriterium: chmod 644
        logger.debug(f"Saved config to {self._config_path}")

    # ------------------------------------------------------------------
    # Installer-Local Settings
    # ------------------------------------------------------------------

    @property
    def recent_hosts(self) -> List[str]:
        """Recently connected Raspberry Pi addresses."""
        return self._data.get("recent_hosts", [])

    def add_recent_host(self, host: str):
        """Add a host to recent connections (max 10, most recent first)."""
        hosts = self.recent_hosts
        if host in hosts:
            hosts.remove(host)
        hosts.insert(0, host)
        self._data["recent_hosts"] = hosts[:10]

    @property
    def language(self) -> str:
        """UI language code (e.g., 'en', 'de')."""
        return self._data.get("language", "en")

    @language.setter
    def language(self, value: str):
        self._data["language"] = value

    # ------------------------------------------------------------------
    # Target Installation Options
    # ------------------------------------------------------------------

    def get_options(self) -> InstallationOptions:
        """Deserialize stored options into InstallationOptions dataclass."""
        raw = self._data.get("options", {})
        return InstallationOptions(**{
            k: v for k, v in raw.items()
            if k in InstallationOptions.__dataclass_fields__
        })

    def set_options(self, options: InstallationOptions):
        """Serialize options for storage."""
        self._data["options"] = asdict(options)

    # ------------------------------------------------------------------
    # Phoniebox-Specific Config Generation
    # ------------------------------------------------------------------

    def generate_install_config_yaml(self, state) -> dict:
        """
        Generate the human-readable/versioned install_config.yaml.

        This is the INTERNAL representation. For the actual upload, the GUI
        flattens it to a flat KEY=VALUE file via generate_install_config_env()
        (which install-jukebox.sh sources — no YAML parser on the Pi, see M18).

        :param state: Fully populated InstallerState
        :return: Dict ready for ruamel.yaml dump
        """
        return {
            "mode": state.mode,
            "existing_install_action": state.existing_install_action,
            "phoniebox": {
                "git_user": state.git_user,
                "git_branch": state.git_branch,
            },
            "options": {
                "enable_static_ip": state.enable_static_ip,
                "disable_ipv6": state.disable_ipv6,
                "enable_autohotspot": state.enable_autohotspot,
                "disable_bluetooth": state.disable_bluetooth,
                "disable_onboard_audio": state.disable_onboard_audio,
                "setup_mpd": state.setup_mpd,
                "enable_mpd_overwrite_install": state.enable_mpd_overwrite_install,
                "enable_rfid_reader": state.enable_rfid_reader,
                "rfid_reader_module": state.rfid_reader_module,
                "enable_samba": state.enable_samba,
                "enable_webapp": state.enable_webapp,
                "enable_kiosk_mode": state.enable_kiosk_mode,
                "update_raspi_os": state.update_raspi_os,
            },
            "webapp": {
                "prod_download": state.enable_webapp_prod_download,
            },
            "audio": {
                "hifiberry_board": state.audio_hifiberry_board,
            },
        }

    def generate_install_config_env(self, state) -> str:
        """
        Generate a flat, shell-sourceable KEY=VALUE file for the target Pi.

        This is the PRIMARY upload artifact: install-jukebox.sh sources it
        (no YAML parser needed on the Pi — see M18). generate_install_config_yaml()
        remains the human-readable/versioned representation of the same options.

        :param state: Fully populated InstallerState
        :return: Multi-line "UPPERCASE=value" string
        """
        def sh_quote(value: str) -> str:
            """Quote a value for safe use in a shell-sourced KEY=VALUE file."""
            return "'" + value.replace("'", "'\\''") + "'"

        entries = [
            ("MODE", state.mode),
            ("GIT_USER", state.git_user),
            ("GIT_BRANCH", state.git_branch),
            ("ENABLE_STATIC_IP", state.enable_static_ip),
            ("DISABLE_IPv6", state.disable_ipv6),
            ("ENABLE_AUTOHOTSPOT", state.enable_autohotspot),
            ("DISABLE_BLUETOOTH", state.disable_bluetooth),
            ("DISABLE_ONBOARD_AUDIO", state.disable_onboard_audio),
            ("SETUP_MPD", state.setup_mpd),
            ("ENABLE_MPD_OVERWRITE_INSTALL", state.enable_mpd_overwrite_install),
            ("ENABLE_RFID_READER", state.enable_rfid_reader),
            ("RFID_READER_MODULE", state.rfid_reader_module),
            ("ENABLE_SAMBA", state.enable_samba),
            ("ENABLE_WEBAPP", state.enable_webapp),
            ("ENABLE_KIOSK_MODE", state.enable_kiosk_mode),
            ("UPDATE_RASPI_OS", state.update_raspi_os),
            ("ENABLE_WEBAPP_PROD_DOWNLOAD", state.enable_webapp_prod_download),
            ("HIFIBERRY_BOARD", state.audio_hifiberry_board),
            ("EXISTING_INSTALL_ACTION", state.existing_install_action),
        ]  # NOTE: MODE ist rein informativ — kein Skript konsumiert ihn derzeit

        lines = []
        for key, value in entries:
            if isinstance(value, bool):
                lines.append(f"{key}={'true' if value else 'false'}")
            elif value not in (None, ""):
                lines.append(f"{key}={sh_quote(str(value))}")
        return "\n".join(lines) + "\n"

    def generate_jukebox_yaml_overrides(self) -> dict:
        """
        NOTE: In v1 the installer does NOT generate jukebox.yaml overrides.

        The target jukebox.yaml is configured by the install scripts
        (install-jukebox.sh) and, for audio, by run_configure_audio.py
        (PulseAudio primary/secondary sinks). There is no
        jukebox.audio_interface / installation_path / music_folder key.
        """
        return {}

