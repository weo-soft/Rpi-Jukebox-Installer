"""
Reader module constants shared between the wizard UI and the backend.

These readers have no usable module defaults and require interactive
device/pin selection on the Raspberry Pi itself. The remote/headless
installer cannot configure them, so after the installation and reboot it
runs the official configuration tool (run_register_rfid_reader.py) over an
interactive SSH session and guides the user through it.
"""

#: Reader modules that require interactive configuration on the Pi.
MANUAL_CONFIG_READERS = frozenset({"generic_usb", "generic_nfcpy", "rc522_spi"})

#: Remote wrapper for the interactive reader configuration.
#:
#: The jukebox-daemon is a systemd *user* service; the configuration tool
#: refuses to run while it is active, so we stop it first and restart it when
#: the shell exits (via a trap). XDG_RUNTIME_DIR is ensured explicitly because
#: a fresh SSH session may not always carry it.
READER_CONFIG_COMMAND = """\
set -e
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
systemctl --user stop jukebox-daemon.service 2>/dev/null || true
trap 'systemctl --user start jukebox-daemon.service 2>/dev/null || true' EXIT
cd ~/RPi-Jukebox-RFID/src/jukebox
source .venv/bin/activate
python run_register_rfid_reader.py
"""
