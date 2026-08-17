"""Tests for the InstallManager and RepoSyncer."""

import pytest
from PySide6.QtCore import QCoreApplication

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.events import InstallEvents
from phoniebox_installer.installer import install as install_module
from phoniebox_installer.installer.install import InstallManager, InstallPhase
from phoniebox_installer.installer.repo import RepoSyncer


class _FakeSsh:
    def __init__(self, exit_status=0, lines=None):
        self._exit_status = exit_status
        self._lines = list(lines or [])
        self.commands = []
        self.stream_calls = []
        self.cancel_called = False

    def exec_command(self, cmd, timeout=3600.0, on_line=None):
        self.commands.append(cmd)
        if on_line:
            for line in self._lines:
                on_line(line)
        return self._exit_status

    def stream_command(self, command, on_line=None, stop_event=None):
        self.stream_calls.append(command)

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


def test_install_failed_on_exception(qapp, monkeypatch):
    """An exception during install publishes INSTALL_FAILED."""
    def _no_config(*args, **kwargs):
        # A script that does NOT declare --config -> _config_support_check raises.
        return "#!/usr/bin/env bash\n# pre-config-era script\n"

    monkeypatch.setattr(install_module, "fetch_github_file_text", _no_config)

    bus = EventBus()
    ssh = _FakeSsh(exit_status=0)
    mgr = InstallManager(bus, ssh_connection=ssh)
    received = []
    bus.subscribe(InstallEvents.INSTALL_FAILED, received.append)

    mgr._install_thread(InstallerState())
    QCoreApplication.processEvents()

    assert len(received) == 1
    assert received[0]["error"]


def test_config_support_check_raises_without_flag(qapp, monkeypatch):
    """Script without --config → RuntimeError (no PTY fallback)."""
    def _no_config(*args, **kwargs):
        return "#!/usr/bin/env bash\n# pre-config-era script\n"

    monkeypatch.setattr(install_module, "fetch_github_file_text", _no_config)

    bus = EventBus()
    mgr = InstallManager(bus)

    with pytest.raises(RuntimeError):
        mgr._config_support_check(InstallerState())


def test_config_support_check_raises_when_source_unreachable(qapp, monkeypatch):
    """A source that cannot be verified fails with the exact URL in the error."""
    monkeypatch.setattr(install_module, "fetch_github_file_text",
                        lambda *args, **kwargs: None)

    state = InstallerState()
    state.git_user = "weo-soft"
    state.git_branch = "future3/feature/installer-noninteractive-config"

    mgr = InstallManager(EventBus())
    with pytest.raises(RuntimeError) as excinfo:
        mgr._config_support_check(state)

    assert "https://github.com/weo-soft/RPi-Jukebox-RFID/tree/" \
           "future3/feature/installer-noninteractive-config" in str(excinfo.value)


def test_config_support_check_passes_with_flag(qapp, monkeypatch):
    """A script containing --config passes; the exact source is queried."""
    calls = {}

    def _with_config(owner, repo, path, ref, **kwargs):
        calls["owner"] = owner
        calls["path"] = path
        calls["ref"] = ref
        return "#!/usr/bin/env bash\n  --config) NON_INTERACTIVE=true ;;\n"

    monkeypatch.setattr(install_module, "fetch_github_file_text", _with_config)

    state = InstallerState()
    state.git_user = "weo-soft"
    state.git_branch = "future3/feature/installer-noninteractive-config"

    mgr = InstallManager(EventBus())
    mgr._config_support_check(state)  # must not raise

    assert calls == {
        "owner": "weo-soft",
        "path": "installation/install-jukebox.sh",
        "ref": "future3/feature/installer-noninteractive-config",
    }


def test_install_line_publishes_output_and_detects_logfile(qapp):
    """Console lines → INSTALL_OUTPUT; the logfile line starts the detail tail."""
    bus = EventBus()
    ssh = _FakeSsh()
    mgr = InstallManager(bus, ssh_connection=ssh)

    received = []
    bus.subscribe(InstallEvents.INSTALL_OUTPUT, received.append)

    mgr._on_install_line("hello")
    assert received == [{"line": "hello"}]

    mgr._on_install_line("INSTALLATION_LOGFILE=/home/pi/INSTALL-123.log")
    assert mgr._detail_log_path == "/home/pi/INSTALL-123.log"

    # The detail tail thread starts and tails the remote log file.
    import time as _time
    for _ in range(100):
        if ssh.stream_calls:
            break
        _time.sleep(0.02)
    assert ssh.stream_calls == ["tail -n +1 -f '/home/pi/INSTALL-123.log'"]

    mgr._stop_detail_tail()
