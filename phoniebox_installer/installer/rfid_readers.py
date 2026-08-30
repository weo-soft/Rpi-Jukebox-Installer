"""Registry of supported RFID reader modules and their configuration parameters.

This is the single source of truth for the reader list shown in the GUI and
for the reader-specific parameters that can be supplied non-interactively
(via ``RFID_READER_PARAMS`` in the install config file).

The parameter defaults mirror the defaults of the interactive installer
(``query_customization()`` in each reader module under
``components/rfid/hardware/<module>/``). Leaving a parameter empty means
"auto": the reader is configured from its module defaults / auto-detection.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass(frozen=True)
class ReaderParam:
    """Definition of a single reader configuration parameter."""

    key: str
    label: str
    description: str = ""
    default: Any = None
    #: "str" | "int" | "bool"
    param_type: str = "str"
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    placeholder: str = ""


@dataclass(frozen=True)
class ReaderDefinition:
    """Definition of a supported RFID reader module."""

    module: str
    display_name: str
    description: str = ""
    params: List[ReaderParam] = field(default_factory=list)


def _param(key, label, description="", default=None, param_type="str",
           min_value=None, max_value=None, placeholder=""):
    """Shortcut factory for a ReaderParam."""
    return ReaderParam(
        key=key, label=label, description=description, default=default,
        param_type=param_type, min_value=min_value, max_value=max_value,
        placeholder=placeholder,
    )


#: Supported readers, in dropdown order. The display names match the labels
#: the interactive installer shows (components/rfid/hardware/<reader>/description.py).
READER_DEFINITIONS = [
    ReaderDefinition(
        module="pn532_i2c_py532",
        display_name="PN532 reader via I2C using py532 library",
        description=(
            "PN532 NFC/RFID reader connected over I2C. Works with the default "
            "wiring — no configuration parameters are necessary."
        ),
        params=[],
    ),
    ReaderDefinition(
        module="rc522_spi",
        display_name="MFRC522 via SPI",
        description=(
            "MFRC522 RFID reader connected over SPI. The suggested defaults "
            "match the recommended default wiring; if unsure, keep them."
        ),
        params=[
            _param("spi_bus", "SPI bus",
                   "SPI bus number (BCM numbering).",
                   default=0, param_type="int"),
            _param("spi_ce", "SPI CE pin",
                   "SPI chip-select line: 0 = CE0 (GPIO8), 1 = CE1 (GPIO7).",
                   default=0, param_type="int", min_value=0, max_value=1),
            _param("pin_irq", "IRQ GPIO pin",
                   "GPIO pin (BCM numbering) for interrupt-driven card "
                   "detection. 0 disables IRQ and uses polling mode (high CPU).",
                   default=24, param_type="int", min_value=0, max_value=27),
            _param("pin_rst", "Reset GPIO pin",
                   "GPIO pin (BCM numbering) for hardware reset. 0 disables "
                   "the reset pin.",
                   default=25, param_type="int", min_value=0, max_value=27),
            _param("mode_legacy", "4-byte-only legacy mode",
                   "Read only the lower 4 bytes of the card UID (legacy "
                   "behaviour). Only needed for an existing card database "
                   "that stores raw 4-byte IDs.",
                   default=False, param_type="bool"),
            _param("antenna_gain", "Antenna gain",
                   "Antenna gain of the reader.",
                   default=4, param_type="int"),
            _param("log_all_cards", "Log all cards",
                   "Log every detected card to the jukebox log.",
                   default=False, param_type="bool"),
        ],
    ),
    ReaderDefinition(
        module="rdm6300_serial",
        display_name="RDM6300 via serial UART",
        description=(
            "RDM6300 125 kHz RFID reader connected to the UART. Configured "
            "for the default UART (/dev/ttyS0 @ 9600 baud); the generated "
            "rfid.yaml can be adjusted by hand if you use a different serial "
            "port."
        ),
        params=[],
    ),
    ReaderDefinition(
        module="mfrc522_i2c",
        display_name="MFRC522 Reader using I2C via the mfrc522_i2c library",
        description=(
            "MFRC522 RFID reader connected over I2C. The default parameters "
            "should work unless the I2C address was changed."
        ),
        params=[],
    ),
    ReaderDefinition(
        module="generic_nfcpy",
        display_name="Generic NFCPY NFC Reader Module",
        description=(
            "USB/serial NFC readers handled by the nfcpy library. The device "
            "path (e.g. 'usb:072f:2200') identifies the reader. Leave it "
            "empty to auto-detect a uniquely connected NFC device."
        ),
        params=[
            _param("device_path", "Device path",
                   "nfcpy device path, e.g. 'usb:072f:2200' for a USB reader "
                   "or '/dev/ttyUSB0' for a serial one. Empty = auto-detect "
                   "a uniquely connected device.",
                   default="", placeholder="usb:072f:2200"),
        ],
    ),
    ReaderDefinition(
        module="generic_usb",
        display_name="Generic USB Reader",
        description=(
            "USB readers that present themselves as a keyboard. The device "
            "name is usually shown when typing on it; the physical path "
            "disambiguates identical devices."
        ),
        params=[
            _param("device_name", "Device name",
                   "Name of the USB input device (e.g. 'KKMoon USB Keyboard'). "
                   "Empty = auto-detect a uniquely connected keyboard-like "
                   "device.",
                   default="", placeholder="KKMoon USB Keyboard"),
            _param("device_phys", "Device physical path",
                   "Physical USB path, only needed when several devices share "
                   "the same name.",
                   default="", placeholder="usb-1:1.2/input0"),
        ],
    ),
]

#: module name → ReaderDefinition
READERS_BY_MODULE: dict = {d.module: d for d in READER_DEFINITIONS}
