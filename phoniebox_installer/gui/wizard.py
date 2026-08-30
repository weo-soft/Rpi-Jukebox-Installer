"""
Wizard container widget.

Manages page navigation (Next/Back/Cancel), hosts a QStackedWidget for
page display, and coordinates the page lifecycle via BasePage hooks.

Usage:
    wizard = Wizard(pages_info, state, event_bus)
    wizard.set_page(0)  # start at first page
"""

import logging
from typing import List, Type

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QMessageBox,
)
from PySide6.QtCore import Signal

from phoniebox_installer.app.events import WizardEvents
from phoniebox_installer.gui.pages.base import BasePage

logger = logging.getLogger(__name__)


class Wizard(QWidget):
    """
    Multi-page wizard container with Next/Back/Cancel navigation.

    Uses QStackedWidget for page display and manages the lifecycle
    of each page through the BasePage hooks.
    """

    # Signal emitted when the wizard is cancelled or finished
    finished = Signal()
    cancelled = Signal()

    def __init__(self, page_classes: List[Type[BasePage]],
                 state, event_bus, controller=None, parent=None):
        """
        :param page_classes: Ordered list of page classes (titles come from class attrs)
        :param state: Shared InstallerState
        :param event_bus: Shared EventBus
        :param controller: Shared InstallerController (injected into every page)
        :param parent: Parent QWidget
        """
        super().__init__(parent)

        self._state = state
        self._event_bus = event_bus
        self._controller = controller
        self._pages: List[BasePage] = []
        self._current_index: int = -1
        self._finished: bool = False

        # Build UI
        self._setup_ui(page_classes)

        # Allow pages to auto-advance (e.g. SSH page after a successful test).
        self._event_bus.subscribe(WizardEvents.ADVANCE, self._on_advance)

    def _setup_ui(self, page_classes):
        """Create the wizard layout with navigation and page stack."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- Title Bar ----
        self._title_label = QLabel("")
        self._title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 16px 20px 4px 20px;
            }
        """)
        main_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #666;
                padding: 0px 20px 12px 20px;
            }
        """)
        self._subtitle_label.setWordWrap(True)
        main_layout.addWidget(self._subtitle_label)

        # ---- Page Stack ----
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("""
            QStackedWidget {
                background-color: white;
            }
        """)
        main_layout.addWidget(self._stack, stretch=1)

        # ---- Navigation Bar ----
        nav_widget = QWidget()
        nav_widget.setObjectName("navBar")
        nav_widget.setStyleSheet("""
            #navBar {
                background-color: #f0f0f0;
                border-top: 1px solid #ddd;
            }
        """)
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 12, 20, 12)

        self._back_btn = QPushButton("←  Back")
        self._back_btn.setMinimumWidth(90)
        self._back_btn.clicked.connect(self._on_back)
        nav_layout.addWidget(self._back_btn)

        nav_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        nav_layout.addWidget(self._cancel_btn)

        self._next_btn = QPushButton("Next  →")
        self._next_btn.setMinimumWidth(90)
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self._next_btn)

        main_layout.addWidget(nav_widget)

        # ---- Create Pages ----
        for PageClass in page_classes:
            page = PageClass(self._state, self._event_bus, controller=self._controller)
            self._pages.append(page)
            self._stack.addWidget(page)

        logger.info(f"Wizard initialized with {len(self._pages)} pages")

    # ------------------------------------------------------------------
    # Page Navigation
    # ------------------------------------------------------------------

    def set_page(self, index: int):
        """
        Switch to the page at the given index.

        Calls on_leave() on the current page and on_enter() on the new page.

        :param index: 0-based page index
        """
        if index < 0 or index >= len(self._pages):
            logger.error(f"Invalid page index: {index}")
            return

        # Leave current page
        if self._current_index >= 0:
            self._pages[self._current_index].on_leave()

        # Enter new page
        self._current_index = index
        self._stack.setCurrentIndex(index)
        self._pages[index].on_enter()

        # Update title
        page = self._pages[index]
        self._title_label.setText(page.title)
        self._subtitle_label.setText(page.subtitle)

        # Update navigation buttons
        self._back_btn.setEnabled(index > 0 and not self._finished)

        is_last = (index == len(self._pages) - 1)
        if is_last:
            self._next_btn.setText("Finish")
        else:
            self._next_btn.setText("Next  →")

        self._event_bus.publish(WizardEvents.PAGE_CHANGED, {
            "index": index,
            "page_id": page.page_id,
            "is_last": is_last,
        })

        logger.debug(f"Page changed to {index}: {page.page_id}")

    def current_page(self) -> BasePage:
        """Return the currently active page."""
        return self._pages[self._current_index]

    # ------------------------------------------------------------------
    # Navigation Slots
    # ------------------------------------------------------------------

    def _on_next(self):
        """Handle Next/Finish button click."""
        page = self.current_page()

        # Validate current page
        is_valid, error_msg = page.validate()
        if not is_valid:
            if error_msg:
                QMessageBox.warning(self, "Validation Error", error_msg)
            return

        # Jump to the next relevant page (skipping pages that declare
        # themselves irrelevant for the current flow).
        next_index = self._next_relevant_index(self._current_index + 1)
        if next_index == -1:
            # Commit all pages
            for p in self._pages:
                p.commit()
            self._finished = True
            self._back_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            self._cancel_btn.setEnabled(False)
            self._event_bus.publish(WizardEvents.WIZARD_FINISHED, {})
            self.finished.emit()
            logger.info("Wizard finished")
        else:
            self.set_page(next_index)

    def _on_back(self):
        """Handle Back button click (jumping over non-relevant pages)."""
        prev_index = self._prev_relevant_index(self._current_index - 1)
        if prev_index >= 0:
            self.set_page(prev_index)

    def _next_relevant_index(self, index: int) -> int:
        """Return the first page index >= ``index`` whose page is relevant, or -1."""
        for i in range(index, len(self._pages)):
            if self._pages[i].relevant(self._state):
                return i
        return -1

    def _prev_relevant_index(self, index: int) -> int:
        """Return the last page index <= ``index`` whose page is relevant, or -1."""
        for i in range(index, -1, -1):
            if self._pages[i].relevant(self._state):
                return i
        return -1

    def _on_cancel(self):
        """Handle Cancel button click."""
        reply = QMessageBox.question(
            self,
            "Cancel Installation",
            "Are you sure you want to cancel the installation?\n\n"
            "All progress will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.cancelled.emit()
            logger.info("Wizard cancelled by user")

    def _on_advance(self, payload: dict):
        """Advance one page (requested by a page, e.g. SSH auto-advance)."""
        if self._current_index < 0:
            return
        page_id = payload.get("page_id")
        if page_id and self.current_page().page_id != page_id:
            return
        self._on_next()

    def _page_index(self, page_id: str) -> int:
        """Return the 0-based index of a page by its page_id (or -1)."""
        for i, page in enumerate(self._pages):
            if page.page_id == page_id:
                return i
        return -1

    def reset(self):
        """Re-arm the wizard for a retry after Finish (M14).

        Re-enables the navigation buttons, clears the finished flag,
        and returns to the Summary page for a new attempt.
        """
        self._finished = False
        self._back_btn.setEnabled(True)
        self._next_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self.set_page(self._page_index("summary"))
