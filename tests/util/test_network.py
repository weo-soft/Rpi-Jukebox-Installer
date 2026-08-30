"""Tests for network utilities (PortScanner, GitHub branches)."""

import base64
import json
import socket
import subprocess
import time

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import DiscoveryEvents
from phoniebox_installer.util.network import (
    PortScanner, fetch_github_branches, fetch_github_file_text,
)


def _pump_until(predicate, timeout=3.0):
    """Pump the Qt event loop until ``predicate()`` is true (or timeout)."""
    from PySide6.QtCore import QCoreApplication
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QCoreApplication.processEvents()
    return bool(predicate())


class _FakeSocket:
    """Fake socket that reports ``connect_ex == 0`` only for open hosts."""

    def __init__(self, open_hosts):
        self._open_hosts = open_hosts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def settimeout(self, timeout):
        pass

    def connect_ex(self, address):
        return 0 if address[0] in self._open_hosts else 1


class TestPortScanner:
    def test_scan_finds_open_ssh_host(self, qapp, monkeypatch):
        """A host with SSH open is reported and the scan signals completion."""
        monkeypatch.setattr(
            socket, "socket",
            lambda family, type: _FakeSocket({"192.168.1.60"}),
        )
        monkeypatch.setattr(
            socket, "gethostbyaddr",
            lambda ip: ("raspberrypi", [], [ip]),
        )

        bus = EventBus()
        scanner = PortScanner(bus)

        found = []
        completed = []
        bus.subscribe(DiscoveryEvents.DEVICE_FOUND, found.append)
        bus.subscribe(DiscoveryEvents.SCAN_COMPLETED, completed.append)

        scanner._scan_subnet_sync("192.168.1")

        assert _pump_until(lambda: bool(found))
        assert [d["device"].ip_address for d in found] == ["192.168.1.60"]
        assert found[0]["device"].hostname == "raspberrypi"
        # SCAN_COMPLETED is published from the calling thread (direct connection).
        assert _pump_until(lambda: bool(completed))
        assert completed == [{"method": "scan"}]


class _FakeResponse:
    """Context-manager fake for ``urllib.request.urlopen``."""

    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _TextResponse:
    """Context-manager fake returning a plain-text body (raw.githubusercontent)."""

    def __init__(self, text):
        self._text = text.encode("utf-8")

    def read(self):
        return self._text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _no_git(*args, **kwargs):
    """Simulate a machine without git installed (fallback also unavailable)."""
    raise FileNotFoundError("git not installed")


class TestFetchGithubBranches:
    def test_returns_branch_names(self, monkeypatch):
        """Branch names are extracted from the GitHub API payload."""
        payload = [{"name": "future3/main"}, {"name": "future3/develop"}]
        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen",
            lambda request, timeout=None: _FakeResponse(payload),
        )
        assert fetch_github_branches("MiczFlor") == [
            "future3/main", "future3/develop"
        ]

    def test_follows_pagination(self, monkeypatch):
        """A full first page triggers the next page request."""
        def _opener(request, timeout=None):
            if "page=2" in request.full_url:
                payload = [{"name": "future3/develop"}]
            else:
                payload = [{"name": f"branch-{i}"} for i in range(100)]
            return _FakeResponse(payload)

        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen", _opener
        )
        names = fetch_github_branches("MiczFlor")
        assert len(names) == 101
        assert names[-1] == "future3/develop"

    def test_api_rate_limit_falls_back_to_git(self, monkeypatch):
        """A rate-limited/offline API falls back to git ls-remote --heads."""
        def _boom(request, timeout=None):
            raise OSError("HTTP Error 403: rate limit exceeded")

        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen", _boom
        )
        completed = subprocess.CompletedProcess(
            ["git", "ls-remote", "--heads", "https://github.com/MiczFlor/RPi-Jukebox-RFID.git"],
            0,
            stdout=(
                "1111111111\trefs/heads/future3/main\n"
                "2222222222\trefs/heads/future3/develop\n"
            ),
            stderr="",
        )
        monkeypatch.setattr(
            "phoniebox_installer.util.network.subprocess.run",
            lambda *args, **kwargs: completed,
        )
        assert fetch_github_branches("MiczFlor") == [
            "future3/main", "future3/develop"
        ]

    def test_network_error_and_no_git_returns_empty_list(self, monkeypatch):
        """API down and no git available -> empty list (manual entry)."""

        def _boom(request, timeout=None):
            raise OSError("offline")

        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen", _boom
        )
        monkeypatch.setattr(
            "phoniebox_installer.util.network.subprocess.run", _no_git
        )
        assert fetch_github_branches("MiczFlor") == []

    def test_non_list_payload_and_no_git_returns_empty_list(self, monkeypatch):
        """A non-list payload (e.g. 404 message) and no git -> empty list."""
        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen",
            lambda request, timeout=None: _FakeResponse({"message": "Not Found"}),
        )
        monkeypatch.setattr(
            "phoniebox_installer.util.network.subprocess.run", _no_git
        )
        assert fetch_github_branches("does-not-exist") == []

    def test_git_failure_returns_empty_list(self, monkeypatch):
        """API down and git ls-remote failing -> empty list."""
        def _boom(request, timeout=None):
            raise OSError("offline")

        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen", _boom
        )
        monkeypatch.setattr(
            "phoniebox_installer.util.network.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args[0], 128, stdout="", stderr="repository not found"
            ),
        )
        assert fetch_github_branches("does-not-exist") == []


class TestFetchGithubFileText:
    def test_api_success_decodes_base64(self, monkeypatch):
        """Content from the contents API is base64-decoded."""
        payload = {
            "content": base64.b64encode(
                b"#!/usr/bin/env bash\n--config\n"
            ).decode("ascii"),
        }
        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen",
            lambda request, timeout=None: _FakeResponse(payload),
        )
        text = fetch_github_file_text(
            "weo-soft", "RPi-Jukebox-RFID",
            "installation/install-jukebox.sh",
            "future3/feature/installer-noninteractive-plugins",
        )
        assert text is not None
        assert "--config" in text

    def test_api_rate_limit_falls_back_to_raw(self, monkeypatch):
        """A rate-limited API falls back to raw.githubusercontent.com."""
        def _opener(request, timeout=None):
            if "api.github.com" in request.full_url:
                raise OSError("HTTP Error 403: rate limit exceeded")
            return _TextResponse("#!/usr/bin/env bash\n--config\n")

        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen", _opener
        )
        text = fetch_github_file_text(
            "weo-soft", "RPi-Jukebox-RFID",
            "installation/install-jukebox.sh",
            "future3/feature/installer-noninteractive-plugins",
        )
        assert text is not None
        assert "--config" in text

    def test_both_fail_returns_none(self, monkeypatch):
        """API and raw fallback both failing -> None."""
        def _boom(request, timeout=None):
            raise OSError("offline")

        monkeypatch.setattr(
            "phoniebox_installer.util.network.urllib.request.urlopen", _boom
        )
        assert fetch_github_file_text(
            "weo-soft", "RPi-Jukebox-RFID", "installation/install-jukebox.sh", "ref"
        ) is None
