"""Tests for the SSH connection manager (Paramiko mocked)."""

import threading
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

    def pop(self, hostname, default=None):
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


class _FakeKey:
    """Minimal fake paramiko key for host-key-change tests."""

    def get_name(self):
        return "ssh-ed25519"

    def asbytes(self):
        return b"fake-key-bytes"

    def get_base64(self):
        return "ZmFrZS1rZXk="


class _KeyStoreClient:
    """Fake client modelling paramiko's persistent known_hosts behaviour.

    ``disk`` is a shared dict (host -> key) standing in for the on-disk
    known_hosts file, so a retry that re-loads from disk sees the accepted key.
    """

    def __init__(self, disk, server_key):
        self._disk = disk
        self._server_key = server_key
        self._keys = {}
        self.saved_paths = []
        self.closed = False

    def set_missing_host_key_policy(self, policy):
        self._policy = policy

    def load_host_keys(self, path):
        self._keys = dict(self._disk)

    def save_host_keys(self, path):
        self.saved_paths.append(str(path))
        self._disk.clear()
        self._disk.update(self._keys)

    def get_host_keys(self):
        return self

    def pop(self, host, default=None):
        return self._keys.pop(host, default)

    def add(self, host, keytype, key):
        self._keys[host] = key

    def connect(self, *args, **kwargs):
        host = args[0] if args else kwargs.get("host")
        stored = self._keys.get(host)
        if stored is not None and stored is not self._server_key:
            raise paramiko.BadHostKeyException(host, self._server_key, stored)

    def get_transport(self):
        return None

    def close(self):
        self.closed = True


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

    def test_stream_command_streams_lines_until_stopped(self, qapp, tmp_path, monkeypatch):
        """stream_command streams lines until the stop event is set."""
        channel = _FakeChannel(lines=["hello", "world"])
        client = _FakeClient(transport=_FakeTransport(channel))
        bus, mgr, _ = self._make_manager(tmp_path, monkeypatch, client)
        mgr._client = client
        mgr._connected = True

        stop = threading.Event()
        collected = []

        def _stop_later():
            time.sleep(0.3)
            stop.set()

        threading.Thread(target=_stop_later, daemon=True).start()
        mgr.stream_command("tail -f /x", on_line=collected.append, stop_event=stop)

        assert collected == ["hello", "world"]

    def test_host_key_changed_can_be_overridden(self, qapp, tmp_path, monkeypatch):
        """A changed host key prompts; accepting replaces it and connects."""
        bad_key = _FakeKey()
        clients = [
            _FakeClient(connect_exc=paramiko.BadHostKeyException("h", bad_key, bad_key)),
            _FakeClient(),  # retry succeeds
        ]
        monkeypatch.setattr(paramiko, "SSHClient", lambda: clients.pop(0))

        bus = EventBus()
        mgr = SshConnectionManager(bus, known_hosts_path=tmp_path / "known_hosts")

        connected = []
        bus.subscribe(SshEvents.CONNECTED, connected.append)
        bus.subscribe(SshEvents.HOST_KEY_CHANGED, lambda p: mgr.confirm_host_key(True))

        mgr.connect("1.2.3.4", user="pi", password="pw")

        assert _pump_until(lambda: bool(connected))
        assert connected[0]["host"] == "1.2.3.4"
        mgr.disconnect()

    def test_host_key_changed_persists_and_connects_without_second_prompt(
        self, qapp, tmp_path, monkeypatch
    ):
        """Regression: accepting a changed host key persists it, so the retry
        connects without prompting a second time (previously: double prompt
        followed by a permanent "Connecting..." hang)."""
        host = "1.2.3.4"
        stale_key = _FakeKey()
        server_key = _FakeKey()
        disk = {host: stale_key}

        known_hosts = tmp_path / "known_hosts"
        known_hosts.write_text("")  # file exists → load_host_keys() is called

        monkeypatch.setattr(
            paramiko, "SSHClient",
            lambda: _KeyStoreClient(disk, server_key),
        )

        bus = EventBus()
        mgr = SshConnectionManager(bus, known_hosts_path=known_hosts)

        connected = []
        prompts = []
        bus.subscribe(SshEvents.CONNECTED, connected.append)
        bus.subscribe(
            SshEvents.HOST_KEY_CHANGED,
            lambda p: (prompts.append(p), mgr.confirm_host_key(True)),
        )

        mgr.connect(host, user="pi", password="pw")

        assert _pump_until(lambda: bool(connected))
        assert len(prompts) == 1
        assert connected[0]["host"] == host
        assert disk[host] is server_key
        mgr.disconnect()
