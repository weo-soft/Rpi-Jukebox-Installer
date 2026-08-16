"""
Central EventBus based on Qt Signals for decoupled communication.

All components (GUI pages, SSH manager, installer, controller)
communicate exclusively through the EventBus. This ensures:
- GUI pages never directly call SSH commands
- SSH threads can safely emit events to the GUI thread
- Components are independently testable with mocked events

Usage:
    event_bus = EventBus()

    # Subscribe
    event_bus.subscribe(SshEvents.CONNECTED, self._on_ssh_connected)

    # Publish
    event_bus.publish(SshEvents.CONNECTED, {"host": "192.168.1.100"})

    # Unsubscribe
    event_bus.unsubscribe(SshEvents.CONNECTED, self._on_ssh_connected)
"""

import logging
from typing import Callable, Dict, List

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


class EventBus(QObject):
    """
    Central event dispatcher.

    Uses Qt's Signal/Slot mechanism for thread-safe communication
    between background threads (SSH, network scanning) and the GUI.

    Events are identified by string event types (see events.py).
    Handlers are Python callables that receive a dict payload.
    """

    # Generic Signal — carries event_type and payload dict
    _signal = Signal(str, dict)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        # event_type → list of (callable, qt_connection)
        self._handlers: Dict[str, List[Callable]] = {}
        # Connect the internal signal to our dispatcher
        self._signal.connect(self._dispatch)

    def subscribe(self, event_type: str, handler: Callable[[dict], None]):
        """
        Register a handler for a specific event type.

        :param event_type: String event type (e.g., SshEvents.CONNECTED)
        :param handler: Callable that receives a dict payload
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed: {event_type} → {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable[[dict], None]):
        """
        Remove a handler for a specific event type.

        :param event_type: String event type
        :param handler: Previously registered callable
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Unsubscribed: {event_type} → {handler.__name__}")

    def publish(self, event_type: str, payload: dict = None):
        """
        Publish an event asynchronously.

        Thread-safe: can be called from any thread. The signal emission
        is queued and dispatched in the receiver's thread (GUI main thread).

        :param event_type: String event type
        :param payload: Dict with event data (default: empty dict)
        """
        if payload is None:
            payload = {}
        self._signal.emit(event_type, payload)

    @Slot(str, dict)
    def _dispatch(self, event_type: str, payload: dict):
        """
        Internal slot that dispatches events to registered handlers.

        Runs in the GUI main thread (connected via Qt::AutoConnection).

        :param event_type: String event type
        :param payload: Event payload dict
        """
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.debug(f"No handlers for event: {event_type}")
            return

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.error(
                    f"Handler {handler.__name__} failed for "
                    f"event {event_type}: {e}",
                    exc_info=True
                )
