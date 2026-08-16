"""Tests for the light theme helper."""

from PySide6.QtGui import QPalette

from phoniebox_installer.util.theme import apply_light_theme


def test_apply_light_theme_sets_dark_text_on_light_background(qapp):
    """Text is dark and backgrounds are light after applying the theme."""
    apply_light_theme(qapp)
    palette = qapp.palette()
    assert palette.color(QPalette.Text).lightness() < 128
    assert palette.color(QPalette.WindowText).lightness() < 128
    assert palette.color(QPalette.ButtonText).lightness() < 128
    assert palette.color(QPalette.Window).lightness() > 128
    assert palette.color(QPalette.Base).lightness() > 128


def test_apply_light_theme_sets_fusion_style(qapp):
    """The Fusion style is active (light, cross-platform)."""
    apply_light_theme(qapp)
    assert "fusion" in qapp.style().objectName().lower()
