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
#:
#: Note: the virtualenv is created by the installer at ``~/RPi-Jukebox-RFID/.venv``
#: (see installation/includes/00_constants.sh), NOT inside src/jukebox.
READER_CONFIG_COMMAND = """\
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
restart_daemon() { systemctl --user start jukebox-daemon.service 2>/dev/null || true; }
trap restart_daemon EXIT

systemctl --user stop jukebox-daemon.service 2>/dev/null || true

cd ~/RPi-Jukebox-RFID || { echo 'ERROR: Jukebox directory not found (~/RPi-Jukebox-RFID)'; exit 1; }
if [ ! -f .venv/bin/activate ]; then
    echo 'ERROR: virtualenv not found (~/RPi-Jukebox-RFID/.venv)'
    exit 1
fi
. .venv/bin/activate
cd src/jukebox || { echo 'ERROR: src/jukebox not found (~/RPi-Jukebox-RFID/src/jukebox)'; exit 1; }

python run_register_rfid_reader.py
"""
