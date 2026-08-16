"""Pre-flight system check definitions and runner (non-GUI)."""

import re
from typing import Dict

from phoniebox_installer.app.events import CheckEvents

# (key, label, shell snippet, severity) — severity: info|warn|critical
CHECKS = [
    ("model", "Raspberry Pi Model", "cat /proc/device-tree/model", "info"),
    ("os_version", "OS Version", "cat /etc/os-release | grep PRETTY_NAME", "critical"),
    ("arch", "Architecture", "uname -m", "info"),
    ("kernel", "Kernel", "uname -r", "info"),
    ("disk_free_mb", "Free disk (MB)", "df -m / | tail -1 | awk '{print $4}'", "warn"),
    ("disk_total_mb", "Total disk (MB)", "df -m / | tail -1 | awk '{print $2}'", "info"),
    ("memory_mb", "RAM (MB)", "free -m | grep Mem | awk '{print $2}'", "info"),
    ("has_internet", "Internet", "ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && echo yes || echo no", "critical"),
    ("has_git", "Git", "which git >/dev/null 2>&1 && echo yes || echo no", "warn"),
    ("has_python", "Python 3", "python3 --version 2>&1", "critical"),
    ("existing_installation", "Existing installation", "test -d ~/RPi-Jukebox-RFID && echo yes || echo no", "warn"),
    ("existing_version", "Installed version", "python ~/RPi-Jukebox-RFID/src/jukebox/jukebox/version.py 2>/dev/null", "info"),
]


def evaluate(key: str, value: str) -> str:
    """Return pass|warn|fail for a check based on its raw string value."""
    if key == "os_version":
        # The install scripts only support Raspbian/Debian (is_debian_based), not Ubuntu.
        return "pass" if ("debian" in value.lower() or "raspbian" in value.lower()) else "fail"
    if key == "disk_free_mb":
        try:
            free = int(value)
        except (ValueError, TypeError):
            free = 0
        return "pass" if free >= 500 else "warn"  # warn-only: Musik kann auf USB liegen
    if key == "has_internet":
        return "pass" if value.strip() == "yes" else "fail"
    if key == "has_git":
        # Git is installed by the install script (prepare_dependencies) — warn only.
        return "pass" if value.strip() == "yes" else "warn"
    if key == "has_python":
        m = re.search(r"Python (\d+)\.(\d+)", value)
        return "pass" if m and (int(m.group(1)), int(m.group(2))) >= (3, 9) else "fail"
    return "pass"


def build_batch_script() -> str:
    """Build a single exec_command() batch that echoes CHECK_<key>=<value> lines."""
    return "; ".join(f'echo CHECK_{key}=$({cmd})' for key, _, cmd, _ in CHECKS)


class SystemCheckRunner:
    """Runs the pre-flight checks over SSH and publishes typed results.

    Publishes CheckEvents.CHECK_COMPLETED with the typed values for each key plus
    a 'status' map {key: pass|warn|fail} (matching what SystemCheckPage expects).
    """

    def __init__(self, ssh_manager, event_bus):
        self._ssh = ssh_manager
        self._event_bus = event_bus

    def run(self) -> None:
        raw: Dict[str, str] = {}

        def _on_line(line: str) -> None:
            if not line.startswith("CHECK_"):
                return
            key, sep, value = line.partition("=")
            if sep:
                raw[key[len("CHECK_"):]] = value

        self._event_bus.publish(CheckEvents.CHECK_STARTED, {"script": build_batch_script()})
        self._ssh.exec_command(build_batch_script(), on_line=_on_line)

        status = {key: evaluate(key, raw.get(key, "")) for key, _, _, _ in CHECKS}

        def _int(k: str) -> int:
            try:
                return int(str(raw.get(k, "0")).strip())
            except ValueError:
                return 0

        payload: Dict = {
            "model": raw.get("model", ""),
            "os_version": raw.get("os_version", ""),
            "kernel": raw.get("kernel", ""),
            "arch": raw.get("arch", ""),
            "disk_free_mb": _int("disk_free_mb"),
            "disk_total_mb": _int("disk_total_mb"),
            "memory_mb": _int("memory_mb"),
            "has_internet": raw.get("has_internet", "").strip() == "yes",
            "has_git": raw.get("has_git", "").strip() == "yes",
            "has_python": status.get("has_python") == "pass",
            "existing_installation": raw.get("existing_installation", "").strip() == "yes",
            "existing_version": raw.get("existing_version", ""),
            "status": status,
        }
        self._event_bus.publish(CheckEvents.CHECK_COMPLETED, payload)
