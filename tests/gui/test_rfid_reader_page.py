"""Tests for the RfidReaderPage (RFID reader configuration)."""

from phoniebox_installer.app.event_bus import EventBus
from phoniebox_installer.app.state import InstallerState
from phoniebox_installer.gui.pages.rfid_reader import RfidReaderPage
from phoniebox_installer.installer.rfid_readers import READER_DEFINITIONS


def _make_page():
    state = InstallerState()
    bus = EventBus()
    return RfidReaderPage(state, bus)


def _select_module(page, module):
    idx = page._module_combo.findData(module)
    assert idx >= 0, f"module {module} not in combo"
    page._module_combo.setCurrentIndex(idx)


def test_default_values(qapp):
    """Enabled by default, no reader selected, dependencies 'auto'."""
    page = _make_page()
    assert page._enable_checkbox.isChecked() is True
    assert page._module_combo.currentData() == ""
    assert page._deps_combo.currentData() == "auto"
    assert page.state.rfid_reader_deps == "auto"


def test_module_combo_shows_display_names(qapp):
    """The reader dropdown shows display names, the module stays as data."""
    page = _make_page()
    texts = [page._module_combo.itemText(i)
             for i in range(page._module_combo.count())]
    for definition in READER_DEFINITIONS:
        assert definition.display_name in texts
    # No python package names as visible labels
    assert "pn532_i2c_py532" not in texts


def test_rc522_spi_shows_param_defaults(qapp):
    """Selecting rc522_spi creates its parameter fields with defaults."""
    page = _make_page()
    _select_module(page, "rc522_spi")
    assert set(page._param_widgets) >= {"spi_ce", "pin_irq", "pin_rst",
                                        "mode_legacy", "antenna_gain"}
    assert page._param_widgets["pin_irq"].text() == "24"
    assert page._param_widgets["pin_rst"].text() == "25"
    assert page._param_widgets["spi_ce"].text() == "0"
    assert page._param_widgets["mode_legacy"].isChecked() is False


def test_generic_nfcpy_shows_device_path_param(qapp):
    """Selecting generic_nfcpy offers the device_path field (empty = auto)."""
    page = _make_page()
    _select_module(page, "generic_nfcpy")
    assert "device_path" in page._param_widgets
    assert page._param_widgets["device_path"].placeholderText() == "usb:072f:2200"


def test_validate_requires_module_when_enabled(qapp):
    """Enabled without a reader module → validation fails."""
    page = _make_page()
    valid, msg = page.validate()
    assert valid is False
    assert msg


def test_validate_passes_when_disabled(qapp):
    """Disabled reader → validation always passes."""
    page = _make_page()
    page._enable_checkbox.setChecked(False)
    assert page.validate() == (True, "")


def test_validate_int_range(qapp):
    """Out-of-range integer parameters are rejected."""
    page = _make_page()
    _select_module(page, "rc522_spi")
    page._param_widgets["pin_irq"].setText("99")
    valid, msg = page.validate()
    assert valid is False
    assert "pin_irq" in msg.lower() or "IRQ" in msg


def test_on_leave_saves_module_params_and_deps(qapp):
    """on_leave persists module, parameters and dependency handling."""
    page = _make_page()
    _select_module(page, "generic_nfcpy")
    page._param_widgets["device_path"].setText("usb:072f:2200")
    deps_idx = page._deps_combo.findData("no")
    page._deps_combo.setCurrentIndex(deps_idx)
    page.on_leave()
    assert page.state.rfid_reader_module == "generic_nfcpy"
    assert page.state.rfid_reader_params == {"device_path": "usb:072f:2200"}
    assert page.state.rfid_reader_deps == "no"


def test_on_leave_empty_param_means_auto(qapp):
    """Empty optional parameters are not persisted (auto-detect)."""
    page = _make_page()
    _select_module(page, "generic_nfcpy")
    page.on_leave()
    assert page.state.rfid_reader_module == "generic_nfcpy"
    assert page.state.rfid_reader_params == {}


def test_on_enter_restores_state(qapp):
    """Stored state is restored into the widgets on re-entry."""
    page = _make_page()
    page.state.rfid_reader_module = "generic_nfcpy"
    page.state.rfid_reader_params = {"device_path": "usb:072f:2200"}
    page.state.rfid_reader_deps = "no"
    page.on_enter()
    assert page._module_combo.currentData() == "generic_nfcpy"
    assert page._param_widgets["device_path"].text() == "usb:072f:2200"
    assert page._deps_combo.currentData() == "no"


def test_disabled_reader_disables_fields(qapp):
    """Disabling the reader disables the module/params/deps widgets."""
    page = _make_page()
    _select_module(page, "rc522_spi")
    page._enable_checkbox.setChecked(False)
    assert not page._module_combo.isEnabled()
    assert not page._params_group.isEnabled()
    assert not page._deps_combo.isEnabled()
