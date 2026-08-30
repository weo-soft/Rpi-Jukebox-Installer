"""Network utilities: mDNS discovery and port scanning."""

import base64
import concurrent.futures
import json
import logging
import os
import socket
import subprocess
import threading
import urllib.parse
import urllib.request
from typing import List, Optional

from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

from phoniebox_installer.app.events import DiscoveryEvents, DeviceInfo

logger = logging.getLogger(__name__)

MDNS_SERVICE_TYPE = "_ssh._tcp.local."


def _github_api_headers() -> dict:
    """Headers for GitHub REST API calls.

    A personal access token from the environment (``GITHUB_TOKEN`` or
    ``GH_TOKEN``) is sent as a Bearer token when present — this raises the
    unauthenticated rate limit from 60 to 5000 requests/hour.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "phoniebox-installer",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_github_branches(owner: str, repo: str = "RPi-Jukebox-RFID",
                          timeout: float = 5.0) -> List[str]:
    """Fetch the branch names of a public GitHub repository.

    Tries the GitHub REST API first (with the token from ``GITHUB_TOKEN``/
    ``GH_TOKEN`` when present). The unauthenticated API is subject to a 60
    requests/hour per-IP rate limit, so on any API failure (rate limit,
    offline, ...) the branch list is instead queried with ``git ls-remote
    --heads`` over HTTPS, which is not subject to that rate limit.

    Returns an empty list on any failure so the caller can fall back to
    manual entry.

    :param owner: GitHub user or organization (e.g. 'MiczFlor')
    :param repo: Repository name (defaults to the Phoniebox repository)
    :param timeout: Per-request timeout in seconds
    :return: List of branch names
    """
    branches, api_ok = _fetch_github_branches_api(owner, repo, timeout)
    if api_ok:
        return branches
    logger.debug("GitHub branches API unavailable for %s/%s, "
                 "falling back to git ls-remote", owner, repo)
    return _fetch_github_branches_via_git(owner, repo, timeout)


def _fetch_github_branches_api(owner: str, repo: str,
                               timeout: float) -> tuple:
    """Branch fetch via the GitHub REST API.

    :return: ``(branch_names, api_ok)`` — ``api_ok`` is False when the API
        could not serve the list (rate limit, offline, HTTP error, ...).
    """
    branches: List[str] = []
    for page in range(1, 6):  # safety cap ~500 branches
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/branches"
            f"?per_page=100&page={page}"
        )
        try:
            request = urllib.request.Request(
                url, headers=_github_api_headers(),
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.debug("GitHub branch fetch failed for %s/%s: %s",
                         owner, repo, exc)
            return branches, False
        if not isinstance(data, list):
            return branches, False
        branches.extend(
            entry["name"]
            for entry in data
            if isinstance(entry, dict) and entry.get("name")
        )
        if len(data) < 100:  # page not full -> no further pages
            return branches, True
    return branches, True


def _fetch_github_branches_via_git(owner: str, repo: str,
                                   timeout: float) -> List[str]:
    """Fallback branch fetch via ``git ls-remote --heads`` over HTTPS."""
    url = f"https://github.com/{owner}/{repo}.git"
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", url],
            capture_output=True, text=True,
            timeout=max(15.0, timeout + 10.0),
        )
    except Exception as exc:
        logger.debug("git ls-remote failed for %s/%s: %s", owner, repo, exc)
        return []
    if result.returncode != 0:
        logger.debug("git ls-remote failed for %s/%s: %s",
                     owner, repo, result.stderr.strip())
        return []
    branches = []
    for line in result.stdout.splitlines():
        _, _, name = line.partition("\t")
        prefix = "refs/heads/"
        if name.startswith(prefix):
            branches.append(name[len(prefix):])
    return branches


def fetch_github_file_text(owner: str, repo: str, path: str, ref: str,
                           timeout: float = 5.0) -> Optional[str]:
    """Fetch a text file's content at a specific ref.

    Tries the GitHub REST contents API first — it serves the exact branch tip
    (no CDN staleness) and supports refs that contain slashes (e.g.
    ``future3/feature/installer-noninteractive-config``) via URL-encoding. If
    the API is unavailable or rate-limited (60 requests/hour per IP
    unauthenticated), falls back to ``raw.githubusercontent.com``, which is
    not subject to that rate limit and supports branch refs with slashes too.

    :param owner: GitHub user or organization (e.g. 'weo-soft')
    :param repo: Repository name (e.g. 'RPi-Jukebox-RFID')
    :param path: Repository path of the file (e.g.
        'installation/install-jukebox.sh')
    :param ref: Branch name, tag or commit SHA to fetch at
    :param timeout: Per-request timeout in seconds
    :return: File content as text, or ``None`` on any failure
    """
    content = _fetch_github_file_text_api(owner, repo, path, ref, timeout)
    if content is not None:
        return content
    logger.debug("GitHub contents API unavailable for %s/%s@%s, "
                 "falling back to raw.githubusercontent.com",
                 owner, repo, ref)
    return _fetch_raw_github_file_text(owner, repo, path, ref, timeout)


def _fetch_github_file_text_api(owner: str, repo: str, path: str, ref: str,
                                timeout: float) -> Optional[str]:
    """File fetch via the GitHub REST contents API (base64-encoded)."""
    query = urllib.parse.urlencode({"ref": ref})
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?{query}"
    try:
        request = urllib.request.Request(
            url, headers=_github_api_headers(),
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("GitHub file fetch failed for %s/%s@%s: %s",
                     owner, repo, ref, exc)
        return None
    if not isinstance(data, dict) or not data.get("content"):
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("Failed to decode %s/%s@%s content: %s",
                     owner, repo, ref, exc)
        return None


def _fetch_raw_github_file_text(owner: str, repo: str, path: str, ref: str,
                                timeout: float) -> Optional[str]:
    """Fallback file fetch via ``raw.githubusercontent.com``."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "phoniebox-installer"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("raw.githubusercontent fetch failed for %s/%s@%s: %s",
                     owner, repo, ref, exc)
        return None


class MdnsDiscovery:
    """Discovers Raspberry Pis via mDNS/Bonjour (zeroconf).

    mDNS is continuous by nature, but already-present devices answer
    immediately, so the browse is bounded by `timeout` and then signals
    SCAN_COMPLETED.
    """

    def __init__(self, event_bus, timeout: float = 5.0):
        self._event_bus = event_bus
        self._timeout = timeout
        self._zeroconf = None
        self._browser = None

    def scan(self):
        """Start async mDNS scan in background thread."""
        self._event_bus.publish(DiscoveryEvents.SCAN_STARTED, {"method": "mdns"})
        thread = threading.Thread(target=self._scan_sync, daemon=True)
        thread.start()

    def _scan_sync(self):
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(
            self._zeroconf, MDNS_SERVICE_TYPE,
            handlers=[self._on_service_state_change]
        )
        # Bound the browse window, then stop + signal completion.
        threading.Timer(self._timeout, self._finish).start()

    def _finish(self):
        if self._zeroconf is not None:
            self.stop()
        self._event_bus.publish(DiscoveryEvents.SCAN_COMPLETED, {"method": "mdns"})

    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            try:
                info = zeroconf.get_service_info(service_type, name)
            except Exception:
                info = None
            if info:
                addresses = [
                    socket.inet_ntoa(addr) for addr in info.addresses
                ]
                hostname = info.server.rstrip('.')
                for addr in addresses:
                    device = DeviceInfo(
                        ip_address=addr,
                        hostname=hostname,
                        discovery_method="mdns",
                    )
                    self._event_bus.publish(
                        DiscoveryEvents.DEVICE_FOUND,
                        {"device": device}
                    )

    def stop(self):
        if self._browser is not None:
            self._browser.cancel()
            self._browser = None
        if self._zeroconf is not None:
            self._zeroconf.close()
            self._zeroconf = None


class PortScanner:
    """Scans local subnet for hosts with SSH port 22 open.

    Probing is parallelized with a thread pool: a sequential sweep of a /24
    would spend up to ``timeout`` seconds on each unreachable host, so a Pi at
    ``x.x.x.60`` could take tens of seconds to surface. With ``workers``
    parallel probes, all 254 hosts are covered in a handful of waves.
    """

    def __init__(self, event_bus, timeout: float = 0.3, workers: int = 64):
        self._event_bus = event_bus
        self._timeout = timeout
        self._workers = workers

    def scan_subnet(self, subnet: str = None):
        """Start subnet scan in background thread."""
        subnet = subnet or self._detect_subnet()
        thread = threading.Thread(
            target=self._scan_subnet_sync, args=(subnet,), daemon=True
        )
        thread.start()

    def _detect_subnet(self) -> str:
        """Detect local subnet (e.g., 192.168.1)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return '.'.join(ip.split('.')[:3])
        except Exception:
            return '192.168.1'

    def _scan_subnet_sync(self, subnet: str):
        """Probe all /24 hosts in parallel, then signal completion."""
        logger.info(f"Scanning {subnet}.0/24 for SSH...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = [
                pool.submit(self._probe_host, subnet, i)
                for i in range(1, 255)
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass

        self._event_bus.publish(DiscoveryEvents.SCAN_COMPLETED, {"method": "scan"})

    def _probe_host(self, subnet: str, i: int):
        """Probe a single host and publish a DeviceInfo if SSH is open."""
        ip = f"{subnet}.{i}"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._timeout)
                if sock.connect_ex((ip, 22)) != 0:
                    return
        except Exception:
            return

        device = DeviceInfo(
            ip_address=ip,
            hostname=self._reverse_dns(ip),
            discovery_method="scan",
        )
        self._event_bus.publish(DiscoveryEvents.DEVICE_FOUND, {"device": device})

    def _reverse_dns(self, ip: str, timeout: float = 0.5) -> str:
        """Best-effort reverse DNS lookup, bounded so it can't stall the scan."""
        result = [ip]

        def _lookup():
            try:
                result[0] = socket.gethostbyaddr(ip)[0]
            except Exception:
                pass

        thread = threading.Thread(target=_lookup, daemon=True)
        thread.start()
        thread.join(timeout)
        return result[0]
