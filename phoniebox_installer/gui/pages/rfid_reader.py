"""RFID reader configuration page.

Lets the user decide whether to set up an RFID reader, which reader module to
use, and — depending on the module — configure the reader-specific parameters
(device path, GPIO pins, ...) with suggested defaults. Also controls whether
the reader's dependencies (Python packages / driver setup) are installed.

The parameter definitions live in ``installer/rfid_readers.py``; this page
renders them dynamically for the selected module.
"""

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QVBoxLayout, QWidget,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.gui.widgets import CustomCheckBox, InfoIcon
from phoniebox_installer.installer.rfid_readers import (
    READER_DEFINITIONS, READERS_BY_MODULE,
)

#: (data value, display label) for the dependency handling combo.
DEPS_OPTIONS = [
    ("auto", "Yes — install automatically (default)"),
    ("no", "No — I will install them myself"),
]

RFID_INFO = (
    "RFID Reader",
    "Phoniebox can be controlled with RFID cards/tags if you have an RFID "
    "reader connected.\n\n"
    "Each reader module may ship its own dependencies: Python packages "
    "(requirements.txt) and/or driver & system setup (setup.inc.sh). With "
    "'Install automatically' (default) they are installed during setup.",
)

DEPS_INFO = (
    "Reader Dependencies",
    "Readers like generic_nfcpy or rc522_spi need extra Python packages and "
    "driver/system setup (e.g. udev rules, SPI enable).\n\n"
    "• Yes — install automatically (default)\n"
    "• No — skip; you install them yourself afterwards",
)


class RfidReaderPage(BasePage):
    page_id = "rfid_reader"
    title = "RFID Reader"
    subtitle = "Configure the RFID reader: type, device/pin parameters and dependencies."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._param_widgets = {}   # param key -> widget
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # --- Enable / disable ---
        enable_row = QHBoxLayout()
        enable_row.setSpacing(8)
        self._enable_checkbox = CustomCheckBox("Set up an RFID reader")
        self._enable_checkbox.setChecked(True)
        enable_row.addWidget(self._enable_checkbox)
        enable_row.addWidget(InfoIcon(*RFID_INFO))
        enable_row.addStretch()
        layout.addLayout(enable_row)

        # --- Reader module ---
        module_group = QGroupBox("Reader Type")
        module_layout = QVBoxLayout(module_group)
        self._module_combo = QComboBox()
        self._module_combo.addItem("Select reader…", "")
        for definition in READER_DEFINITIONS:
            self._module_combo.addItem(definition.display_name, definition.module)
        module_layout.addWidget(self._module_combo)
        self._module_description = QLabel("")
        self._module_description.setWordWrap(True)
        self._module_description.setStyleSheet("color: #666; font-size: 12px;")
        module_layout.addWidget(self._module_description)
        layout.addWidget(module_group)

        # --- Reader-specific parameters ---
        self._params_group = QGroupBox("Reader Parameters")
        self._params_form = QFormLayout(self._params_group)
        self._params_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addWidget(self._params_group)

        # --- Dependencies ---
        deps_group = QGroupBox("Dependencies")
        deps_layout = QVBoxLayout(deps_group)
        deps_row = QHBoxLayout()
        deps_row.setSpacing(8)
        deps_row.addWidget(QLabel("Install the reader's Python packages and driver setup:"))
        self._deps_combo = QComboBox()
        for value, label in DEPS_OPTIONS:
            self._deps_combo.addItem(label, value)
        deps_row.addWidget(self._deps_combo, stretch=1)
        deps_row.addWidget(InfoIcon(*DEPS_INFO))
        deps_layout.addLayout(deps_row)
        layout.addWidget(deps_group)

        layout.addStretch()

        # --- Signals ---
        self._module_combo.currentIndexChanged.connect(self._on_module_changed)
        self._enable_checkbox.toggled.connect(self._on_enabled_toggled)

    # ------------------------------------------------------------------
    # Dynamic parameter fields
    # ------------------------------------------------------------------

    def _on_module_changed(self, *_args):
        """Rebuild the parameter form for the newly selected reader module."""
        definition = self._current_definition()
        self._module_description.setText(definition.description if definition else "")
        self._rebuild_param_fields(definition)
        has_params = bool(definition and definition.params)
        self._params_group.setVisible(has_params)

    def _current_definition(self):
        module = self._module_combo.currentData() or ""
        return READERS_BY_MODULE.get(module)

    def _rebuild_param_fields(self, definition):
        """Rebuild the parameter form from the definition's params."""
        while self._params_form.rowCount() > 0:
            self._params_form.removeRow(0)
        self._param_widgets = {}
        if definition is None:
            return
        for param in definition.params:
            widget = self._make_param_field(param)
            self._param_widgets[param.key] = widget
            if param.param_type == "bool":
                self._params_form.addRow("", widget)
            else:
                self._params_form.addRow(f"{param.label}:", widget)

    def _make_param_field(self, param):
        """Create the input widget for a single parameter."""
        if param.param_type == "bool":
            widget = CustomCheckBox(param.label)
            widget.setChecked(bool(param.default))
            return widget
        line = QLineEdit()
        if param.param_type == "int":
            line.setValidator(QIntValidator(
                param.min_value if param.min_value is not None else 0,
                param.max_value if param.max_value is not None else 999999,
                line,
            ))
        if param.placeholder:
            line.setPlaceholderText(param.placeholder)
        if param.default is not None:
            line.setText(str(param.default))
        return line

    def _set_param_value(self, param, widget, value):
        """Write a stored state value back into a parameter widget."""
        if param.param_type == "bool":
            widget.setChecked(bool(value))
        else:
            widget.setText("" if value is None else str(value))

    def _param_value(self, param, widget):
        """Read the current value from a parameter widget."""
        if param.param_type == "bool":
            return widget.isChecked()
        text = widget.text().strip()
        if param.param_type == "int" and text:
            try:
                return int(text)
            except ValueError:
                return text
        return text

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_enabled_toggled(self, *_args):
        """Disable the reader fields when the reader itself is disabled."""
        enabled = self._enable_checkbox.isChecked()
        self._module_combo.setEnabled(enabled)
        self._params_group.setEnabled(enabled)
        self._deps_combo.setEnabled(enabled)

    def on_enter(self):
        """Pre-fill fields from state (restore on back-navigation)."""
        self._enable_checkbox.setChecked(self.state.enable_rfid_reader)
        self._set_combo_data(self._module_combo, self.state.rfid_reader_module)
        # Rebuild parameter fields for the restored module.
        self._on_module_changed()
        definition = self._current_definition()
        if definition is not None:
            for param in definition.params:
                widget = self._param_widgets.get(param.key)
                if widget is None:
                    continue
                value = self.state.rfid_reader_params.get(param.key, param.default)
                self._set_param_value(param, widget, value)
        self._set_combo_data(self._deps_combo, self.state.rfid_reader_deps)
        self._on_enabled_toggled()

    def _set_combo_data(self, combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def validate(self):
        """Validate the page before allowing 'Next'."""
        if not self._enable_checkbox.isChecked():
            return (True, "")
        module = self._module_combo.currentData() or ""
        if not module:
            return (False, "RFID reader is enabled — please select a reader "
                           "type or disable the RFID reader.")
        definition = READERS_BY_MODULE.get(module)
        if definition is None:
            return (True, "")
        for param in definition.params:
            widget = self._param_widgets.get(param.key)
            if widget is None:
                continue
            value = self._param_value(param, widget)
            if param.param_type == "int":
                if value in (None, ""):
                    continue
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    return (False, f"'{param.label}' must be a whole number.")
                if param.min_value is not None and number < param.min_value:
                    return (False, f"'{param.label}' must be at least "
                                   f"{param.min_value}.")
                if param.max_value is not None and number > param.max_value:
                    return (False, f"'{param.label}' must be at most "
                                   f"{param.max_value}.")
        return (True, "")

    def on_leave(self):
        """Save all field values back to state."""
        self.state.enable_rfid_reader = self._enable_checkbox.isChecked()
        self.state.rfid_reader_module = self._module_combo.currentData() or ""
        definition = self._current_definition()
        params = {}
        if definition is not None:
            for param in definition.params:
                widget = self._param_widgets.get(param.key)
                if widget is None:
                    continue
                value = self._param_value(param, widget)
                if value not in (None, ""):
                    params[param.key] = value
        self.state.rfid_reader_params = params
        self.state.rfid_reader_deps = self._deps_combo.currentData() or "auto"
