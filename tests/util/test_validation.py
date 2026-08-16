"""Tests for the input validation helpers."""

from phoniebox_installer.util.validation import parse_github_branch_url


def test_parse_tree_url_with_slashed_branch():
    """A /tree/<branch> URL is split into owner, repo and branch."""
    parsed = parse_github_branch_url(
        "https://github.com/weo-soft/RPi-Jukebox-RFID/"
        "tree/future3/feature/installer-noninteractive-config"
    )
    assert parsed == (
        "weo-soft",
        "RPi-Jukebox-RFID",
        "future3/feature/installer-noninteractive-config",
    )


def test_parse_repo_root_url():
    """A repo URL without /tree/ yields an empty branch."""
    assert parse_github_branch_url(
        "https://github.com/MiczFlor/RPi-Jukebox-RFID"
    ) == ("MiczFlor", "RPi-Jukebox-RFID", "")


def test_parse_url_with_git_suffix():
    """A trailing .git is stripped from the repo name."""
    assert parse_github_branch_url(
        "https://github.com/weo-soft/RPi-Jukebox-RFID.git"
    ) == ("weo-soft", "RPi-Jukebox-RFID", "")


def test_parse_url_with_trailing_slash():
    """A trailing slash is tolerated."""
    assert parse_github_branch_url(
        "https://github.com/weo-soft/RPi-Jukebox-RFID/"
    ) == ("weo-soft", "RPi-Jukebox-RFID", "")


def test_parse_invalid_url():
    """Non-GitHub URLs return None."""
    assert parse_github_branch_url("") is None
    assert parse_github_branch_url("not-a-url") is None
    assert parse_github_branch_url("https://example.com/foo/bar") is None
    assert parse_github_branch_url("https://github.com/just-owner") is None
