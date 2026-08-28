"""
Base class for all wizard pages.

Each page follows a lifecycle managed by the Wizard container:
    1. on_enter() — called when the page becomes active (load from self.state)
    2. validate() → (bool, error_message) — called when user clicks "Next"
    3. on_leave() — called when leaving the page (save to state)
    4. commit() — called at wizard completion (final persistence)

Pages are QWidget subclasses. They receive the shared InstallerState,
EventBus and InstallerController on construction.
"""

from typing import Tuple

from PySide6.QtWidgets import QWidget


class BasePage(QWidget):
    """
    Abstract base class for all wizard pages.

    Subclasses must provide:
    - A unique page_id class attribute
    - A descriptive title and subtitle

    Subclasses may override:
    - validate() for input validation
    - on_enter() / on_leave() / commit() for state management
    """

    page_id: str = "base"
    title: str = "Untitled Page"
    subtitle: str = ""

    def __init__(self, state, event_bus, controller=None, parent=None):
        """
        :param state: Shared InstallerState instance (from controller)
        :param event_bus: Shared EventBus instance
        :param controller: Shared InstallerController instance (optional)
        :param parent: Parent QWidget
        """
        super().__init__(parent)
        self._state = state
        self._event_bus = event_bus
        self._controller = controller

    # ------------------------------------------------------------------
    # Lifecycle Hooks (override in subclasses)
    # ------------------------------------------------------------------

    def on_enter(self):
        """
        Called when this page becomes the active page in the wizard.

        Use this to populate UI fields from self._state.
        """
        pass

    def validate(self) -> Tuple[bool, str]:
        """
        Validate the page before allowing "Next".

        Called when the user clicks the "Next" button.

        :return: (is_valid, error_message). If is_valid is False,
                 error_message is shown to the user.
        """
        return (True, "")

    @staticmethod
    def relevant(state) -> bool:
        """
        Whether this page participates in the current wizard flow.

        The wizard skips pages that report ``False`` when navigating. The
        default is to always include a page; conditional pages (e.g. the
        post-install reader configuration) override this based on ``state``.

        :param state: The shared InstallerState
        :return: True to include the page, False to skip it
        """
        return True

    def on_leave(self):
        """
        Called when leaving this page (either Next or Back).

        Use this to save UI field values back to self._state.
        """
        pass

    def commit(self):
        """
        Called at wizard completion (after the last page).

        Use this for final persistence or cleanup actions.
        """
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def state(self):
        """Access the shared InstallerState."""
        return self._state

    @property
    def event_bus(self):
        """Access the shared EventBus."""
        return self._event_bus

    @property
    def controller(self):
        """Access the shared InstallerController (may be None in unit tests)."""
        return self._controller
