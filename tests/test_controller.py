"""Tests for the InstallerController."""

import pytest
from PySide6.QtCore import QCoreApplication

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import SshEvents
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.controller import InstallerController


class TestInstallerController:
    """Test suite for the InstallerController."""

    def test_initial_state(self):
        """Controller starts with default state."""
        bus = EventBus()
        controller = InstallerController(bus)
        state = controller.get_state()

        assert state.mode == "new"
        assert state.target_host == ""
        assert state.ssh_user == "pi"

    def test_set_mode(self):
        """Mode can be set to 'new' or 'update'."""
        bus = EventBus()
        controller = InstallerController(bus)

        controller.set_mode("update")
        assert controller.get_state().mode == "update"

        with pytest.raises(ValueError):
            controller.set_mode("invalid")

    def test_set_target(self):
        """Target host and port can be set."""
        bus = EventBus()
        controller = InstallerController(bus)

        controller.set_target("192.168.1.100", 2222)
        assert controller.get_state().target_host == "192.168.1.100"
        assert controller.get_state().ssh_port == 2222

    def test_set_credentials(self):
        """SSH credentials can be set."""
        bus = EventBus()
        controller = InstallerController(bus)

        controller.set_credentials("admin", "secret", "/path/to/key")
        state = controller.get_state()
        assert state.ssh_user == "admin"
        assert state.ssh_password == "secret"
        assert state.ssh_key_file == "/path/to/key"

    def test_ssh_connected_updates_state(self, qapp):
        """SshEvents.CONNECTED updates state.ssh_authenticated."""
        bus = EventBus()
        controller = InstallerController(bus)

        bus.publish(SshEvents.CONNECTED, {"host": "192.168.1.100"})
        QCoreApplication.processEvents()

        assert controller.get_state().ssh_authenticated is True

    def test_ssh_auth_failed_updates_state(self, qapp):
        """SshEvents.AUTH_FAILED updates state.ssh_authenticated to False."""
        bus = EventBus()
        controller = InstallerController(bus)

        bus.publish(SshEvents.AUTH_FAILED, {"reason": "Wrong password"})
        QCoreApplication.processEvents()

        assert controller.get_state().ssh_authenticated is False

    def test_custom_state_preserved(self):
        """Controller with custom initial state preserves values."""
        state = InstallerState(mode="update", ssh_user="admin")
        bus = EventBus()
        controller = InstallerController(bus, state)

        assert controller.get_state().mode == "update"
        assert controller.get_state().ssh_user == "admin"

    # ------------------------------------------------------------------
    # Post-install reader configuration
    # ------------------------------------------------------------------

    def test_needs_reader_config_for_manual_readers(self):
        """needs_reader_config() only for manually configured readers."""
        bus = EventBus()
        controller = InstallerController(bus)
        controller.state.enable_rfid_reader = True
        controller.state.rfid_reader_module = "generic_usb"
        assert controller.needs_reader_config() is True

        controller.state.rfid_reader_module = "pn532_i2c_py532"
        assert controller.needs_reader_config() is False

        controller.state.rfid_reader_module = "generic_usb"
        controller.state.enable_rfid_reader = False
        assert controller.needs_reader_config() is False

    def test_reconnect_ssh_uses_state_credentials(self):
        """reconnect_ssh() closes the old session and forwards the credentials."""
        bus = EventBus()
        controller = InstallerController(bus)
        controller.state.target_host = "phoniebox.local"
        controller.state.ssh_port = 2222
        controller.state.ssh_user = "pi"
        controller.state.ssh_password = "secret"
        controller.state.ssh_key_file = None

        calls = []

        class _FakeSsh:
            def disconnect(self):
                calls.append("disconnect")

            def connect(self, host, port, user, password, key_filename):
                calls.append((host, port, user, password, key_filename))

        controller.set_ssh_manager(_FakeSsh())
        controller.reconnect_ssh()

        assert calls == ["disconnect", ("phoniebox.local", 2222, "pi", "secret", None)]

    def test_start_reader_config_session_delegates(self):
        """start_reader_config_session passes callbacks to the manager."""
        bus = EventBus()
        controller = InstallerController(bus)

        seen = []

        class _FakeSsh:
            def start_interactive_session(self, command, on_output=None, on_exit=None):
                seen.append((command, on_output, on_exit))

        controller.set_ssh_manager(_FakeSsh())

        def out(t):
            pass

        def exit_cb(code):
            pass

        controller.start_reader_config_session(on_output=out, on_exit=exit_cb)
        assert len(seen) == 1
        assert "run_register_rfid_reader.py" in seen[0][0]
        assert seen[0][1] is out
        assert seen[0][2] is exit_cb

    def test_send_and_stop_reader_config_delegate(self):
        """send_reader_config_input / stop_reader_config_session delegate to SSH."""
        bus = EventBus()
        controller = InstallerController(bus)
        seen = []

        class _FakeSsh:
            def send_input(self, data):
                seen.append(("send", data))

            def stop_interactive_session(self):
                seen.append("stop")

        controller.set_ssh_manager(_FakeSsh())
        controller.send_reader_config_input("2\n")
        controller.stop_reader_config_session()

        assert seen == [("send", "2\n"), "stop"]
