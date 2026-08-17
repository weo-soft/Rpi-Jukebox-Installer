"""Reusable custom Qt widgets."""

import html

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractButton, QCheckBox, QGroupBox, QMessageBox, QToolButton, QToolTip,
    QVBoxLayout, QWidget,
)


def _wrap_tooltip(text: str) -> str:
    """Return the description as a fixed-width, wrapped, high-contrast tooltip.

    Qt tooltips do not wrap by default; constraining the width in the rich text
    forces line wrapping. The colors are set explicitly so the tooltip stays
    readable even when the desktop runs in dark mode.
    """
    escaped = html.escape(text).replace("\n", "<br>")
    return (
        "<div style='width: 380px; white-space: normal; "
        "color: #333333; background-color: #ffffff; "
        "padding: 6px 8px;'>{}</div>"
    ).format(escaped)


class InfoIcon(QAbstractButton):
    """A clickable info icon with a fast, wrapped tooltip and a click popup.

    The badge is painted instead of using an emoji so it never clips and looks
    identical on every platform and theme. Hovering shows the description
    almost immediately (``QToolTip.setDelay()`` is not exposed by PySide6, so
    the widget displays the tooltip itself); a left click opens it in an
    information dialog.
    """

    #: Delay before the tooltip appears (ms).
    TOOLTIP_DELAY_MS = 150

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._description = description
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(18, 18)
        self.setFocusPolicy(Qt.NoFocus)
        self.clicked.connect(self._show_info)

        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.setInterval(self.TOOLTIP_DELAY_MS)
        self._tooltip_timer.timeout.connect(self._show_tooltip_now)
        self.installEventFilter(self)

    def _show_info(self):
        QToolTip.hideText()
        QMessageBox.information(self, self._title, self._description)

    def _show_tooltip_now(self):
        pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        QToolTip.showText(pos, _wrap_tooltip(self._description), self)

    def eventFilter(self, watched, event):
        if watched is self:
            if event.type() == QEvent.Enter:
                self._tooltip_timer.start()
            elif event.type() == QEvent.Leave:
                self._tooltip_timer.stop()
                QToolTip.hideText()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("#1976d2")
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(color, 1.4))
        painter.drawEllipse(QRectF(1, 1, 16, 16))
        font = self.font()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QRectF(1, 1, 16, 16), Qt.AlignCenter, "i")
        painter.end()


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

    def sizeHint(self):
        """Ensure the painted indicator and label fit without clipping.

        The native QCheckBox size hint assumes the default ~13 px indicator, so
        the layout would otherwise size the widget a few pixels too small and
        the self-painted label would be clipped at the right edge.
        """
        fm = self.fontMetrics()
        width = self.INDICATOR_SIZE + 6 + fm.horizontalAdvance(self.text()) + 6
        height = max(self.INDICATOR_SIZE, fm.height()) + 6
        return QSize(width, height)

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
        # Inset by half the pen width: the border is drawn centered on the
        # path, so without the inset the left/top half of the stroke would be
        # clipped at the widget edge (visually "cut off" left border).
        pen_width = 1.5
        inset = pen_width / 2.0
        rect = QRectF(
            inset,
            (self.height() - (size - 2 * inset)) / 2.0,
            size - 2 * inset,
            size - 2 * inset,
        )

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
