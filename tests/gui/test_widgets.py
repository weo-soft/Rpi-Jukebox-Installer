"""Tests for custom widgets (CustomCheckBox)."""

from PySide6.QtWidgets import QCheckBox

from phoniebox_installer.gui.widgets import CustomCheckBox


def _count_color(widget, color, x0, x1, y0, y1):
    """Count pixels of the exact color within the given region."""
    img = widget.grab().toImage()
    n = 0
    for y in range(y0, min(y1, img.height())):
        for x in range(x0, min(x1, img.width())):
            if img.pixelColor(x, y).name() == color:
                n += 1
    return n


def _indicator_region(widget):
    """The 16x16 indicator area (left-aligned, vertically centered)."""
    cy = widget.height() // 2
    return (0, 17, cy - 8, cy + 8)


def test_custom_checkbox_is_a_qcheckbox(qapp):
    """CustomCheckBox behaves like a QCheckBox (signals, state)."""
    cb = CustomCheckBox("x")
    assert isinstance(cb, QCheckBox)

    states = []
    cb.toggled.connect(states.append)
    cb.setChecked(True)
    assert cb.isChecked() is True
    assert states == [True]


def test_checked_shows_blue_border_and_checkmark(qapp):
    """A checked box draws the design blue border AND the checkmark.

    This is the core fix: styling must not lose the checkmark.
    """
    cb = CustomCheckBox("x")
    cb.setChecked(True)
    cb.resize(120, 24)
    cb.show()
    qapp.processEvents()

    x0, x1, y0, y1 = _indicator_region(cb)
    # Border + checkmark both use the design blue #1976d2.
    assert _count_color(cb, "#1976d2", x0, x1, y0, y1) > 8


def test_unchecked_has_no_checked_blue(qapp):
    """An unchecked box never uses the checked design blue."""
    cb = CustomCheckBox("x")
    cb.setChecked(False)
    cb.resize(120, 24)
    cb.show()
    qapp.processEvents()

    x0, x1, y0, y1 = _indicator_region(cb)
    # Hover may tint the border light blue, but never the checked blue.
    assert _count_color(cb, "#1976d2", x0, x1, y0, y1) == 0


def test_focus_hint_stays_inside_widget_bounds(qapp):
    """Regression: the focus hint must never extend outside the widget.

    A focus frame around the indicator (``rect.adjusted(-2, ...)``) reached
    negative x and, combined with antialiasing, corrupted the entire widget
    rendering while focused on real displays (border and checkmark vanished).
    The focus hint is a short underline beneath the text; both endpoints must
    stay inside the widget bounds.
    """
    cb = CustomCheckBox("x")
    cb.resize(120, 24)
    start, end = cb._focus_line_span()
    assert start.x() >= 0 and start.y() >= 0
    assert end.x() <= cb.width() - 1
    assert end.y() <= cb.height() - 1
    assert end.x() >= start.x()  # non-negative span, never reversed
    # A narrow widget still yields a valid (clamped) span.
    cb.resize(18, 16)
    start2, end2 = cb._focus_line_span()
    assert end2.x() >= start2.x()
