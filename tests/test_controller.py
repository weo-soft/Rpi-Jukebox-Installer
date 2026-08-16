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
