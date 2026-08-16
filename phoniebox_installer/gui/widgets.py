"""Reusable custom Qt widgets."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QCheckBox, QGroupBox, QToolButton, QVBoxLayout, QWidget


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


class CustomCheckBox(QCheckBox):
    """A checkbox with a self-painted indicator.

    The Fusion style hardcodes a faint gray indicator border that the palette
    cannot override, and styling ``QCheckBox::indicator`` in a stylesheet
    replaces the native checkmark (which would then need a separate image).
    This widget paints the box and the checkmark itself, so the border can be
    tinted per state (e.g. blue when checked) without losing the checkmark and
    without any image files.

    Keyboard interaction, ``toggled()`` signals and state handling are
    inherited unchanged from ``QCheckBox``.
    """

    #: Indicator side length in pixels.
    INDICATOR_SIZE = 16

    def _focus_line_span(self) -> "tuple[QPointF, QPointF]":
        """Return start/end of the text underline used as the focus hint.

        The line runs only underneath the actual text (measured via the
        widget font) and is clamped to the widget bounds. An earlier focus
        frame around the text looked like a box over the label; one around
        the indicator extended past x=0 and (with antialiasing) corrupted
        the whole rendering while focused.
        """
        x0 = self.INDICATOR_SIZE + 6
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        x1 = min(x0 + text_width, self.width() - 1)
        if x1 < x0:
            x1 = x0  # widget too narrow for the text area -> zero-length line
        y = self.height() - 2
        return QPointF(x0, y), QPointF(x1, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = self.INDICATOR_SIZE
        rect = QRectF(0, (self.height() - size) / 2.0, size, size)

        if not self.isEnabled():
            border = QColor("#c0c0c0")
        elif self.isChecked():
            border = QColor("#1976d2")
        elif self.underMouse():
            border = QColor("#64b5f6")  # subtle hover hint (not the checked blue)
        else:
            border = QColor("#9c9c9c")

        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(border, 1.5))
        painter.drawRoundedRect(rect, 3, 3)

        if self.isChecked() and self.isEnabled():
            pen = QPen(border, 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            points = [
                QPointF(rect.left() + 3.5, rect.center().y() + 1.0),
                QPointF(rect.center().x() - 1.0, rect.bottom() - 3.5),
                QPointF(rect.right() - 3.0, rect.top() + 4.0),
            ]
            painter.drawPolyline(QPolygonF(points))

        # Text (consistent with the forced light theme).
        text = QColor("#333333" if self.isEnabled() else "#999999")
        text_rect = QRectF(size + 6, 0, self.width() - size - 6, self.height())
        painter.setPen(text)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        # Focus hint: a short underline beneath the text (see _focus_line_span).
        if self.hasFocus():
            start, end = self._focus_line_span()
            painter.setPen(QPen(QColor("#1976d2"), 1))
            painter.drawLine(start, end)

        painter.end()
