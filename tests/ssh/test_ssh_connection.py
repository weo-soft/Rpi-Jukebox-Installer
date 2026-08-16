"""Tests for the SSH connection manager (Paramiko mocked)."""

import time

import paramiko

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import SshEvents
from phoniebox_installer.ssh.connection import SshConnectionManager


def _pump_until(predicate, timeout=3.0):
    """Pump the Qt event loop until ``predicate()`` is true (or timeout)."""
    from PySide6.QtCore import QCoreApplication
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    QCoreApplication.processEvents()
    return bool(predicate())


class _FakeChannel:
    """Minimal fake paramiko.Channel for exec_command()."""

    def __init__(self, exit_status=0, lines=None):
        self._exit_status = exit_status
        self._lines = list(lines or [])
        self._sent = []
        self.closed = False

    def settimeout(self, t):
        pass

    def exec_command(self, cmd):
        pass

    def recv_ready(self):
        return bool(self._lines)

    def recv(self, n):
        if self._lines:
            return (self._lines.pop(0) + "\n").encode()
        return b""

    def recv_stderr_ready(self):
        return False

    def recv_stderr(self, n):
        return b""

    def exit_status_ready(self):
        return not self._lines

    def recv_exit_status(self):
        return self._exit_status

    def send(self, data):
        self._sent.append(data)

    def close(self):
        self.closed = True


class _FakeClient:
    """Minimal fake paramiko.SSHClient."""

    def __init__(self, connect_exc=None, transport=None):
        self._connect_exc = connect_exc
        self._transport = transport
        self.closed = False
        self.exec_calls = []

    def set_missing_host_key_policy(self, policy):
        pass

    def load_host_keys(self, path):
        pass

    def save_host_keys(self, path):
        pass

    def get_host_keys(self):
        return self

    def add(self, hostname, keytype, key):
        pass

    def connect(self, *args, **kwargs):
        if self._connect_exc is not None:
            raise self._connect_exc

    def close(self):
        self.closed = True

    def get_transport(self):
        return self._transport

    def exec_command(self, cmd):
        self.exec_calls.append(cmd)


class _FakeTransport:
    """Minimal fake paramiko.Transport."""

    def __init__(self, channel):
        self._channel = channel

    def open_session(self):
        return self._channel

    def is_active(self):
        return True

    def send_ignore(self):
        pass


class TestSshConnection:
    """Test suite for SshConnectionManager (Paramiko mocked)."""

    def _make_manager(self, tmp_path, monkeypatch, client=None):
        client = client or _FakeClient()
        monkeypatch.setattr(paramiko, "SSHClient", lambda: client)
        bus = EventBus()
        mgr = SshConnectionManager(bus, known_hosts_path=tmp_path / "known_hosts")
        return bus, mgr, client

    def test_connect_success_publishes_connected_event(self, qapp, tmp_path, monkeypatch):
        """Successful connect → SshEvents.CONNECTED."""
        client = _FakeClient()
        bus, mgr, _ = self._make_manager(tmp_path, monkeypatch, client)
        received = []
        bus.subscribe(SshEvents.CONNECTED, received.append)

        mgr.connect("192.168.1.100", user="pi", password="pw")

        assert _pump_until(lambda: bool(received))
        assert received[0]["host"] == "192.168.1.100"
        assert received[0]["user"] == "pi"
        assert mgr.is_connected is True
        mgr.disconnect()

    def test_auth_failure_publishes_auth_failed_event(self, qapp, tmp_path, monkeypatch):
        """AuthenticationException → SshEvents.AUTH_FAILED."""
        client = _FakeClient(connect_exc=paramiko.AuthenticationException("bad"))
        bus, mgr, _ = self._make_manager(tmp_path, monkeypatch, client)
        received = []
        bus.subscribe(SshEvents.AUTH_FAILED, received.append)

        mgr.connect("1.2.3.4", user="pi", password="wrong")

        assert _pump_until(lambda: bool(received))
        assert received[0]["host"] == "1.2.3.4"
        assert mgr.is_connected is False

    def test_disconnect_publishes_disconnected_event(self, qapp, tmp_path, monkeypatch):
        """disconnect() → SshEvents.DISCONNECTED."""
        bus, mgr, client = self._make_manager(tmp_path, monkeypatch)
        received = []
        bus.subscribe(SshEvents.DISCONNECTED, received.append)

        mgr._client = client
        mgr._connected = True
        mgr._host = "1.2.3.4"

        mgr.disconnect()

        assert _pump_until(lambda: bool(received))
        assert received[0]["host"] == "1.2.3.4"
        assert mgr.is_connected is False

    def test_connect_resolves_on_eventbus_request(self, qapp, tmp_path, monkeypatch):
        """SshEvents.CONNECT_REQUEST triggers connect()."""
        bus, mgr, _ = self._make_manager(tmp_path, monkeypatch)
        calls = []

        def fake_connect(host="", port=22, user="pi", password="", key_filename=None):
            calls.append((host, port, user, password, key_filename))

        monkeypatch.setattr(mgr, "connect", fake_connect)

        bus.publish(SshEvents.CONNECT_REQUEST, {
            "host": "1.2.3.4",
            "port": 2222,
            "user": "admin",
            "password": "s",
            "key_file": "/k",
        })

        assert _pump_until(lambda: bool(calls))
        assert calls == [("1.2.3.4", 2222, "admin", "s", "/k")]

    def test_keep_alive_stops_on_disconnect(self, qapp, tmp_path, monkeypatch):
        """disconnect() stops the keep-alive thread."""
        bus, mgr, client = self._make_manager(tmp_path, monkeypatch)
        mgr._client = client
        mgr._connected = True

        mgr._start_keep_alive()
        assert mgr._keep_alive_thread is not None

        mgr.disconnect()

        assert mgr._keep_alive_stop.is_set()
        assert not mgr._keep_alive_thread.is_alive()

    def test_exec_command_returns_exit_status(self, qapp, tmp_path, monkeypatch):
        """exec_command streams lines and returns the exit status."""
        channel = _FakeChannel(exit_status=0, lines=["line1", "line2"])
        client = _FakeClient(transport=_FakeTransport(channel))
        bus, mgr, _ = self._make_manager(tmp_path, monkeypatch, client)
        mgr._client = client
        mgr._connected = True

        collected = []
        status = mgr.exec_command("echo hi", on_line=collected.append)

        assert status == 0
        assert collected == ["line1", "line2"]

    def test_cancel_current_kills_remote(self, qapp, tmp_path, monkeypatch):
        """cancel_current() sends Ctrl+C and pkill."""
        client = _FakeClient()
        channel = _FakeChannel()
        bus, mgr, _ = self._make_manager(tmp_path, monkeypatch, client)
        mgr._client = client
        mgr._connected = True
        mgr._active_channel = channel

        mgr.cancel_current()

        assert b"\x03" in channel._sent
        assert any("pkill -f install-jukebox.sh" in c for c in client.exec_calls)

