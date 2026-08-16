"""Tests for the InstallManager and RepoSyncer."""

import pytest
from PySide6.QtCore import QCoreApplication

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.events import InstallEvents
from phoniebox_installer.installer.install import InstallManager, InstallPhase
from phoniebox_installer.installer.repo import RepoSyncer


class _FakeSsh:
    def __init__(self, exit_status=0, lines=None):
        self._exit_status = exit_status
        self._lines = list(lines or [])
        self.commands = []
        self.cancel_called = False

    def exec_command(self, cmd, timeout=3600.0, on_line=None):
        self.commands.append(cmd)
        if on_line:
            for line in self._lines:
                on_line(line)
        return self._exit_status

    def cancel_current(self):
        self.cancel_called = True


class _FakeSftp:
    def __init__(self):
        self.put_calls = []

    def put(self, local, remote):
        self.put_calls.append((local, remote))
        return True


def test_install_manager_emits_phases(qapp):
    """_set_phase publishes INSTALL_PROGRESS."""
    bus = EventBus()
    mgr = InstallManager(bus)
    received = []
    bus.subscribe(InstallEvents.INSTALL_PROGRESS, received.append)

    mgr._set_phase(InstallPhase.CONFIG_UPLOAD)

    assert received[0]["step"] == "Uploading configuration..."
    assert received[0]["percentage"] == 0.0


def test_config_mode_uploads_env_before_install(qapp):
    """Config-Mode uploads install_config.env via SFTP before running the script."""
    bus = EventBus()
    ssh = _FakeSsh(exit_status=0)
    sftp = _FakeSftp()
    mgr = InstallManager(bus, sftp_wrapper=sftp, ssh_connection=ssh)

    mgr._install_config_mode(InstallerState())

    assert len(sftp.put_calls) == 1
    assert sftp.put_calls[0][1] == "/tmp/install_config.env"
    assert len(ssh.commands) == 1
    assert "--config /tmp/install_config.env" in ssh.commands[0]


def test_cancel_calls_ssh_cancel_current(qapp):
    """cancel() delegates to SshConnectionManager.cancel_current()."""
    bus = EventBus()
    ssh = _FakeSsh()
    mgr = InstallManager(bus, ssh_connection=ssh)

    mgr.cancel()

    assert ssh.cancel_called is True


def test_source_check_existing_command_format(qapp):
    """RepoSyncer builds the correct existence-check command."""
    ssh = _FakeSsh()
    syncer = RepoSyncer(ssh)

    result = syncer.check_existing("~/RPi-Jukebox-RFID")

    assert "test -d ~/RPi-Jukebox-RFID" in ssh.commands[0]
    assert result == "NOT_FOUND"


def test_install_failed_on_exception(qapp):
    """An exception during install publishes INSTALL_FAILED."""
    bus = EventBus()
    # "MISSING" makes _config_support_check raise RuntimeError.
    ssh = _FakeSsh(exit_status=0, lines=["MISSING"])
    mgr = InstallManager(bus, ssh_connection=ssh)
    received = []
    bus.subscribe(InstallEvents.INSTALL_FAILED, received.append)

    mgr._install_thread(InstallerState())
    QCoreApplication.processEvents()

    assert len(received) == 1
    assert received[0]["error"]


def test_config_support_check_raises_without_flag(qapp):
    """Script without --config → RuntimeError (no PTY fallback)."""
    bus = EventBus()
    ssh = _FakeSsh(exit_status=0, lines=["MISSING"])
    mgr = InstallManager(bus, ssh_connection=ssh)

    with pytest.raises(RuntimeError):
        mgr._config_support_check(InstallerState())
