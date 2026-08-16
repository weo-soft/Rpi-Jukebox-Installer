# Phoniebox Installer

A cross-platform graphical installer (Windows & Linux) for
[RPi-Jukebox-RFID (Phoniebox future3)](https://github.com/MiczFlor/RPi-Jukebox-RFID).

Built with Python, PySide6 (Qt), and Paramiko. The installer connects to a
Raspberry Pi over SSH, runs pre-flight system checks, lets the user configure
the installation, and executes the Phoniebox install scripts non-interactively
(flat `KEY=VALUE` config + `install-jukebox.sh --config`).

## Development

```bash
# Create a virtualenv and install dependencies
uv venv .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt

# Run the application
.venv/bin/python -m phoniebox_installer.main

# Run tests
.venv/bin/pytest

# Lint
.venv/bin/flake8 phoniebox_installer/ tests/
```

## Documentation

The detailed implementation plan lives in the main Phoniebox repository under
`Docs/Phoniebox-Installer/` (18 milestone design docs).

## License

MIT — see [LICENSE](LICENSE).
