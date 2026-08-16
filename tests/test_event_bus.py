"""Tests for the EventBus system."""

from PySide6.QtCore import QCoreApplication

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.events import SshEvents


class TestEventBus:
    """Test suite for EventBus subscribe/publish/unsubscribe."""

    def test_subscribe_and_publish(self, qapp):
        """Handler receives published events."""
        bus = EventBus()
        received = []

        def handler(payload):
            received.append(payload)

        bus.subscribe(SshEvents.CONNECTED, handler)
        bus.publish(SshEvents.CONNECTED, {"host": "test"})

        # Process Qt events to deliver the signal
        QCoreApplication.processEvents()

        assert len(received) == 1
        assert received[0] == {"host": "test"}

    def test_unsubscribe(self, qapp):
        """Handler no longer receives events after unsubscribe."""
        bus = EventBus()
        received = []

        def handler(payload):
            received.append(payload)

        bus.subscribe(SshEvents.CONNECTED, handler)
        bus.unsubscribe(SshEvents.CONNECTED, handler)
        bus.publish(SshEvents.CONNECTED, {"host": "test"})

        QCoreApplication.processEvents()

        assert len(received) == 0

    def test_multiple_handlers(self, qapp):
        """Multiple handlers for the same event."""
        bus = EventBus()
        received_a = []
        received_b = []

        def handler_a(payload):
            received_a.append(payload)

        def handler_b(payload):
            received_b.append(payload)

        bus.subscribe(SshEvents.CONNECTED, handler_a)
        bus.subscribe(SshEvents.CONNECTED, handler_b)
        bus.publish(SshEvents.CONNECTED, {"host": "test"})

        QCoreApplication.processEvents()

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_handler_exception_does_not_crash(self, qapp):
        """An exception in one handler doesn't affect others."""
        bus = EventBus()
        received = []

        def crashing_handler(payload):
            raise RuntimeError("Boom!")

        def normal_handler(payload):
            received.append(payload)

        bus.subscribe(SshEvents.CONNECTED, crashing_handler)
        bus.subscribe(SshEvents.CONNECTED, normal_handler)
        bus.publish(SshEvents.CONNECTED, {"host": "test"})

        QCoreApplication.processEvents()

        assert len(received) == 1  # normal handler still got the event

    def test_unhandled_event_no_error(self, qapp):
        """Publishing an event with no handlers doesn't raise errors."""
        bus = EventBus()
        # Should not raise
        bus.publish("nonexistent.event", {})
        QCoreApplication.processEvents()
