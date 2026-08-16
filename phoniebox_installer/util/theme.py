"""Application theming helpers.

The installer uses a light color scheme with hardcoded light backgrounds.
On systems with a dark desktop theme (e.g. Breeze Dark), Qt would otherwise
keep the light-on-dark palette (white text) while our stylesheets force light
backgrounds — producing unreadable white-on-white widgets. We therefore force
a light Fusion palette at startup.
"""

from PySide6.QtGui import QPalette, QColor


def apply_light_theme(app) -> None:
    """Force a light Fusion palette onto the given QApplication."""
    app.setStyle("Fusion")

    palette = QPalette()
    # Window + default text
    palette.setColor(QPalette.Window, QColor("#f5f5f5"))
    palette.setColor(QPalette.WindowText, QColor("#333333"))
    # Input fields, lists, tables
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#fafafa"))
    palette.setColor(QPalette.Text, QColor("#333333"))
    # Buttons
    palette.setColor(QPalette.Button, QColor("#e6e6e6"))
    palette.setColor(QPalette.ButtonText, QColor("#333333"))
    # Selection / highlight
    palette.setColor(QPalette.Highlight, QColor("#1976d2"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    # Tooltips
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#333333"))
    # Placeholder text (line edits)
    palette.setColor(QPalette.PlaceholderText, QColor("#999999"))
    # Disabled text
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#999999"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#999999"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#999999"))

    app.setPalette(palette)
