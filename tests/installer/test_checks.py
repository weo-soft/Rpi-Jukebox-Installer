"""Tests for the system-check evaluation rules (non-GUI)."""

from phoniebox_installer.installer.checks import evaluate, CHECKS


def test_git_missing_returns_warn_not_fail():
    """Git missing → warn (installed by the script during install)."""
    assert evaluate("has_git", "no") == "warn"
    assert evaluate("has_git", "yes") == "pass"


def test_internet_missing_returns_fail():
    """Internet missing → fail (critical)."""
    assert evaluate("has_internet", "no") == "fail"
    assert evaluate("has_internet", "yes") == "pass"


def test_python_old_version_returns_fail():
    """Python < 3.9 → fail."""
    assert evaluate("has_python", "Python 3.7.3") == "fail"
    assert evaluate("has_python", "Python 3.11.2") == "pass"


def test_pip_and_docker_not_checked():
    """pip and docker are no longer part of the pre-flight checks."""
    keys = {key for key, _, _, _ in CHECKS}
    assert "has_pip" not in keys
    assert "has_docker" not in keys
