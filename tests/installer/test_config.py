"""Tests for the ConfigManager."""

from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.installer.config import ConfigManager, InstallationOptions


def test_load_returns_empty_dict_if_no_file(tmp_path):
    """No config file → empty dict."""
    cfg = ConfigManager(config_path=tmp_path / "nonexistent.yaml")
    assert cfg.load() == {}


def test_save_and_load_roundtrip(tmp_path):
    """save() then load() returns the same data."""
    path = tmp_path / "config.yaml"
    cfg = ConfigManager(config_path=path)
    cfg.load()
    cfg.language = "de"
    cfg.save()

    cfg2 = ConfigManager(config_path=path)
    cfg2.load()
    assert cfg2.language == "de"


def test_set_options_preserves_data(tmp_path):
    """Options are serialized and deserialized correctly."""
    path = tmp_path / "config.yaml"
    cfg = ConfigManager(config_path=path)
    cfg.load()
    cfg.set_options(InstallationOptions(enable_samba=True, git_branch="develop"))
    cfg.save()

    cfg2 = ConfigManager(config_path=path)
    cfg2.load()
    assert cfg2.get_options().enable_samba is True
    assert cfg2.get_options().git_branch == "develop"


def test_add_recent_host_maintains_order(tmp_path):
    """Most recent host first; re-adding moves it to the front."""
    cfg = ConfigManager(config_path=tmp_path / "config.yaml")
    cfg.load()
    cfg.add_recent_host("a")
    cfg.add_recent_host("b")
    cfg.add_recent_host("a")
    assert cfg.recent_hosts == ["a", "b"]


def test_add_recent_host_caps_at_10(tmp_path):
    """Recent hosts list is capped at 10 entries."""
    cfg = ConfigManager(config_path=tmp_path / "config.yaml")
    cfg.load()
    for i in range(15):
        cfg.add_recent_host(f"host{i}")
    assert len(cfg.recent_hosts) == 10
    assert cfg.recent_hosts[0] == "host14"


def test_generate_install_config_yaml(tmp_path):
    """generate_install_config_yaml() produces the expected structure."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState(git_user="MiczFlor", git_branch="future3/main", enable_samba=True)
    yaml_dict = cfg.generate_install_config_yaml(state)
    assert yaml_dict["phoniebox"]["git_user"] == "MiczFlor"
    assert yaml_dict["options"]["enable_samba"] is True
    assert yaml_dict["options"]["enable_static_ip"] is True


def test_generate_install_config_env(tmp_path):
    """generate_install_config_env() produces flat KEY=VALUE lines."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState(
        git_user="MiczFlor",
        git_branch="future3/main",
        existing_install_action="backup",
        audio_hifiberry_board="hifiberry-dacplus",
    )
    env = cfg.generate_install_config_env(state)
    assert "GIT_USER='MiczFlor'" in env
    assert "ENABLE_SAMBA=false" in env
    assert "ENABLE_STATIC_IP=true" in env
    assert "EXISTING_INSTALL_ACTION='backup'" in env
    assert "HIFIBERRY_BOARD='hifiberry-dacplus'" in env


def test_language_get_set(tmp_path):
    """language property reads/writes the language setting."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    cfg.load()
    assert cfg.language == "en"
    cfg.language = "de"
    assert cfg.language == "de"
