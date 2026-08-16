"""Reusable custom Qt widgets."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QToolButton, QVBoxLayout, QWidget


class CollapsibleGroupBox(QGroupBox):
    """A group box with a clickable title that collapses/expands the content.

    The native group box title is not drawn; an embedded QToolButton renders
    the title with a collapse arrow instead. ``title()`` still returns the
    logical title (used e.g. by layout checks and tests).
    """

    def __init__(self, title: str = "", parent=None, collapsed: bool = False):
        super().__init__("", parent)
        self._box_title = title

        self._toggle = QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.DownArrow if not collapsed else Qt.RightArrow)
        self._toggle.setStyleSheet(
            "QToolButton { border: none; background: transparent; "
            "font-weight: bold; padding: 2px 4px; }"
        )
        self._toggle.clicked.connect(self._on_toggled)

        self._content = QWidget(self)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        # Match the padding of a plain QGroupBox (default ~9 px) so content is
        # not crammed against the border; small gap between title and content.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(9, 9, 9, 9)
        outer.setSpacing(4)
        outer.addWidget(self._toggle)
        outer.addWidget(self._content)
        self._content.setVisible(not collapsed)

    def title(self) -> str:
        """Logical title of the group box (native title is not drawn)."""
        return self._box_title

    def content_layout(self) -> QVBoxLayout:
        """Return the layout used to add the collapsible content."""
        return self._content_layout

    def is_collapsed(self) -> bool:
        """True when the content is currently collapsed.

        Uses the toggle's checked state (the source of truth) rather than the
        widget visibility, which is always False on a not-yet-shown page.
        """
        return not self._toggle.isChecked()

    def _on_toggled(self, checked: bool):
        self._content.setVisible(checked)
        self._toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
