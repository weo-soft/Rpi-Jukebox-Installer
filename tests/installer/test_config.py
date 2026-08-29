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


def test_generate_install_config_yaml_plugins(tmp_path):
    """generate_install_config_yaml() includes the plugins section."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState(
        setup_spotify=True,
        spotify_client_id="abc123",
        enable_jellyfin=True,
        jellyfin_host="http://jellyfin.local:8096",
        jellyfin_api_key="jf-key",
    )
    yaml_dict = cfg.generate_install_config_yaml(state)
    plugins = yaml_dict["plugins"]
    assert plugins["spotify"] == {
        "setup": True,
        "client_id": "abc123",
        "redirect_uri": "",
        "device_name": "Phoniebox",
    }
    assert plugins["jellyfin"]["enable"] is True
    assert plugins["jellyfin"]["host"] == "http://jellyfin.local:8096"
    assert plugins["jellyfin"]["api_key"] == "jf-key"


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


def test_generate_install_config_env_plugins(tmp_path):
    """Spotify/Jellyfin options are exported to the flat config file."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState(
        setup_spotify=True,
        spotify_client_id="abc123",
        spotify_redirect_uri="http://127.0.0.1:3000/api/v1/spotify/oauth/callback",
        spotify_device_name="Kitchen",
        enable_jellyfin=True,
        jellyfin_host="http://jellyfin.local:8096",
        jellyfin_api_key="jf-key",
    )
    env = cfg.generate_install_config_env(state)
    assert "SETUP_SPOTIFY=true" in env
    assert "SPOTIFY_CLIENT_ID='abc123'" in env
    assert "SPOTIFY_REDIRECT_URI='http://127.0.0.1:3000/api/v1/spotify/oauth/callback'" in env
    assert "SPOTIFY_DEVICE_NAME='Kitchen'" in env
    assert "ENABLE_JELLYFIN=true" in env
    assert "JELLYFIN_HOST='http://jellyfin.local:8096'" in env
    assert "JELLYFIN_API_KEY='jf-key'" in env


def test_generate_install_config_env_plugins_disabled(tmp_path):
    """Disabled plugins export booleans only — no credentials."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState()
    env = cfg.generate_install_config_env(state)
    assert "SETUP_SPOTIFY=false" in env
    assert "ENABLE_JELLYFIN=false" in env
    assert "SPOTIFY_CLIENT_ID=" not in env
    assert "JELLYFIN_HOST=" not in env


def test_generate_install_config_env_manual_reader_skips_rfid(tmp_path):
    """Manual-config readers are not configured by the non-interactive install.

    The install scripts forward the reader module to
    run_register_rfid_reader.py, which aborts with a RuntimeError when the
    reader requires interactive customization but no terminal is available.
    Such readers are configured interactively after the reboot by the
    ReaderConfigPage, so the install step must skip them.
    """
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState(enable_rfid_reader=True, rfid_reader_module="generic_nfcpy")
    env = cfg.generate_install_config_env(state)
    assert "ENABLE_RFID_READER=false" in env
    assert "RFID_READER_MODULE" not in env


def test_generate_install_config_env_auto_reader_keeps_module(tmp_path):
    """Readers with module defaults are still configured non-interactively."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    state = InstallerState(enable_rfid_reader=True, rfid_reader_module="pn532_i2c_py532")
    env = cfg.generate_install_config_env(state)
    assert "ENABLE_RFID_READER=true" in env
    assert "RFID_READER_MODULE='pn532_i2c_py532'" in env


def test_language_get_set(tmp_path):
    """language property reads/writes the language setting."""
    cfg = ConfigManager(config_path=tmp_path / "c.yaml")
    cfg.load()
    assert cfg.language == "en"
    cfg.language = "de"
    assert cfg.language == "de"
