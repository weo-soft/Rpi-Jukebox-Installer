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


def get_app_stylesheet() -> str:
    """Return the global control stylesheet.

    The flat Fusion palette alone leaves buttons nearly indistinguishable from
    the light window background, so we add borders, hover/pressed states and
    contrast here. Checkbox/radio indicators are left to the native Fusion
    style (which draws its own checkmark/dot).
    """
    css = """
        QMainWindow {
            background-color: #f5f5f5;
        }

        QPushButton {
            background-color: #ffffff;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            padding: 5px 14px;
            color: #333333;
        }
        QPushButton:hover {
            background-color: #eef4fb;
            border-color: #1976d2;
        }
        QPushButton:pressed {
            background-color: #dce9f7;
        }
        QPushButton:disabled {
            background-color: #f2f2f2;
            color: #999999;
            border-color: #dddddd;
        }

        QCheckBox, QRadioButton {
            color: #333333;
            spacing: 6px;
        }

        QLineEdit {
            background-color: #ffffff;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            padding: 4px 8px;
            color: #333333;
        }
        QLineEdit:focus {
            border-color: #1976d2;
        }

        QGroupBox {
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 8px;
            color: #333333;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }

        QTableWidget, QPlainTextEdit, QTextEdit, QListWidget {
            background-color: #ffffff;
            border: 1px solid #c8c8c8;
            color: #333333;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            border: 1px solid #c8c8c8;
            padding: 4px 6px;
            color: #333333;
        }
    """
    return css
