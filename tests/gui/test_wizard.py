"""Tests for the Wizard container."""

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.app.events import WizardEvents
from phoniebox_installer.gui.wizard import Wizard
from phoniebox_installer.gui.pages.base import BasePage


class _PageA(BasePage):
    page_id = "a"
    title = "Page A"


class _PageB(BasePage):
    page_id = "b"
    title = "Page B"


class _PageC(BasePage):
    page_id = "c"
    title = "Page C"


def _make_wizard(page_classes=None, state=None, bus=None):
    page_classes = page_classes or [_PageA, _PageB, _PageC]
    state = state or InstallerState()
    bus = bus or EventBus()
    return Wizard(page_classes, state, bus)


class TestWizard:
    """Test suite for the Wizard container."""

    def test_wizard_initializes_with_all_pages(self, qapp):
        """All page classes are instantiated and added to the stack."""
        eight = [_PageA, _PageB, _PageC, _PageA, _PageB, _PageC, _PageA, _PageB]
        wizard = _make_wizard(page_classes=eight)
        assert len(wizard._pages) == 8
        assert wizard._stack.count() == 8

    def test_set_page_updates_title_and_navigation(self, qapp):
        """Title label reflects the active page."""
        wizard = _make_wizard()
        wizard.set_page(0)
        assert wizard._title_label.text() == "Page A"
        wizard.set_page(1)
        assert wizard._title_label.text() == "Page B"
        assert wizard._current_index == 1

    def test_back_button_disabled_on_first_page(self, qapp):
        """Back button is disabled on page 0."""
        wizard = _make_wizard()
        wizard.set_page(0)
        assert not wizard._back_btn.isEnabled()

    def test_next_button_shows_finish_on_last_page(self, qapp):
        """Next button shows 'Finish' on the last page."""
        wizard = _make_wizard()
        wizard.set_page(2)
        assert wizard._next_btn.text() == "Finish"

    def test_navigate_forward_and_back(self, qapp):
        """Next/Back move between pages."""
        wizard = _make_wizard()
        wizard.set_page(0)
        wizard._on_next()
        assert wizard._current_index == 1
        wizard._on_back()
        assert wizard._current_index == 0

    def test_cancel_shows_confirmation_dialog(self, qapp, monkeypatch):
        """Cancel emits the cancelled signal after confirmation."""
        wizard = _make_wizard()
        wizard.set_page(0)

        monkeypatch.setattr(
            QMessageBox, "question", lambda *a, **k: QMessageBox.Yes
        )

        emitted = []
        wizard.cancelled.connect(lambda: emitted.append(True))
        wizard._on_cancel()
        assert emitted == [True]

    def test_next_triggers_validate_on_current_page(self, qapp):
        """validate() is called before Next."""
        validated = []

        class _Validating(_PageA):
            def validate(self):
                validated.append(self.page_id)
                return (True, "")

        wizard = _make_wizard(page_classes=[_Validating, _PageB])
        wizard.set_page(0)
        wizard._on_next()
        assert validated == ["a"]
        assert wizard._current_index == 1

    def test_validate_failure_blocks_next(self, qapp, monkeypatch):
        """A failing validate() blocks navigation."""
        class _Failing(_PageA):
            def validate(self):
                return (False, "nope")

        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

        wizard = _make_wizard(page_classes=[_Failing, _PageB])
        wizard.set_page(0)
        wizard._on_next()
        assert wizard._current_index == 0  # still on first page

    def test_finish_triggers_commit_on_all_pages(self, qapp):
        """commit() is called on all pages when finishing."""
        committed = []

        class _Committing(BasePage):
            page_id = "c"
            title = "C"

            def commit(self):
                committed.append(self.page_id)

        wizard = _make_wizard(page_classes=[_Committing, _Committing])
        wizard.set_page(1)
        wizard._on_next()  # Finish on last page
        assert committed == ["c", "c"]
        assert wizard._finished is True
        assert not wizard._next_btn.isEnabled()

    def test_page_lifecycle_order(self, qapp):
        """on_enter/on_leave are called in the right order."""
        events = []

        def make_page(page_id):
            class _P(BasePage):
                page_id = page_id
                title = page_id

                def on_enter(self):
                    events.append(f"enter:{page_id}")

                def on_leave(self):
                    events.append(f"leave:{page_id}")

            return _P

        wizard = _make_wizard(page_classes=[make_page("x"), make_page("y")])
        wizard.set_page(0)
        assert events == ["enter:x"]
        wizard.set_page(1)
        assert events == ["enter:x", "leave:x", "enter:y"]

    def test_wizard_emits_page_changed_event(self, qapp):
        """PAGE_CHANGED event is emitted on every page switch."""
        bus = EventBus()
        received = []
        bus.subscribe(WizardEvents.PAGE_CHANGED, received.append)

        wizard = _make_wizard(bus=bus)
        wizard.set_page(0)
        QCoreApplication.processEvents()

        assert len(received) == 1
        assert received[0]["index"] == 0
        assert received[0]["page_id"] == "a"
        assert received[0]["is_last"] is False
