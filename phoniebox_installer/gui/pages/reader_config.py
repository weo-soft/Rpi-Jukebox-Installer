"""
Reader configuration page — interactive configuration of manually
configured readers (generic_usb, generic_nfcpy, rc522_spi) after install.

After the installation and the reboot the page establishes a fresh SSH
connection, starts the official run_register_rfid_reader.py tool over a
pseudo-terminal and streams the output into a terminal-like widget. The user
answers the tool's prompts in the input line; the jukebox-daemon is stopped
before and restarted after the configuration (see READER_CONFIG_COMMAND).
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLineEdit,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import SshEvents
from phoniebox_installer.app.readers import MANUAL_CONFIG_READERS


class ReaderConfigPage(BasePage):
    page_id = "reader_config"
    title = "RFID Reader Configuration"
    subtitle = "Configure the selected reader interactively on the Raspberry Pi."

    # Emitted from the SSH session thread; handled on the GUI thread (Qt
    # queues cross-thread signal deliveries automatically).
    _output_received = Signal(str)
    _session_exited = Signal(int)

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._session_active = False
        self._session_started = False
        self._session_done = False
        self._skipped = False
        self._connect_requested = False

        self._setup_ui()

        self._output_received.connect(self._on_output_received)
        self._session_exited.connect(self._on_session_exited)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #333;"
        )
        layout.addWidget(self._status_label)

        self._terminal = QPlainTextEdit()
        self._terminal.setReadOnly(True)
        self._terminal.setStyleSheet(
            "font-family: Monospace, Courier New; font-size: 12px;"
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #555;"
            "border-radius: 4px;"
        )
        layout.addWidget(self._terminal, stretch=1)

        input_row = QHBoxLayout()
        self._prompt_label = QLabel("\u276f")
        self._prompt_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        input_row.addWidget(self._prompt_label)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type your answer here and press Enter\u2026")
        self._input.returnPressed.connect(self._send_input)
        input_row.addWidget(self._input, stretch=1)
        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._send_input)
        input_row.addWidget(self._send_btn)
        layout.addLayout(input_row)

        button_row = QHBoxLayout()
        self._connect_btn = QPushButton("\U0001f504 Connect & Start Configuration")
        self._connect_btn.clicked.connect(self._connect_and_start)
        button_row.addWidget(self._connect_btn)
        self._stop_btn = QPushButton("\u23f9 Stop Session")
        self._stop_btn.clicked.connect(self._stop_session)
        button_row.addWidget(self._stop_btn)
        button_row.addStretch()
        self._skip_btn = QPushButton("\u23ed Skip Configuration")
        self._skip_btn.clicked.connect(self._skip)
        button_row.addWidget(self._skip_btn)
        layout.addLayout(button_row)

        self._set_input_enabled(False)

    def _set_input_enabled(self, enabled: bool):
        self._prompt_label.setEnabled(enabled)
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def relevant(state) -> bool:
        """Only shown when a manually configured reader was selected."""
        return bool(
            state.enable_rfid_reader
            and state.rfid_reader_module in MANUAL_CONFIG_READERS
        )

    def on_enter(self):
        self._terminal.clear()
        self._session_active = False
        self._session_started = False
        self._session_done = False
        self._skipped = False
        self._connect_requested = False
        self._subscribe()

        if self.controller is None:
            self._set_status("Controller not available — cannot configure the reader.")
            return

        if not self.relevant(self.state):
            self._set_status("No interactive reader configuration needed.")
            return

        self._connect_and_start()

    def on_leave(self):
        # Never leave a session running in the background.
        if self.controller is not None:
            self.controller.stop_reader_config_session()
        self._unsubscribe()

    def validate(self):
        if not self.relevant(self.state):
            return (True, "")
        if self._skipped or self._session_done:
            return (True, "")
        if self._session_active:
            return (False, "Please finish the configuration (or skip it) before continuing.")
        return (True, "")

    # ------------------------------------------------------------------
    # Connection + session control
    # ------------------------------------------------------------------

    def _connect_and_start(self):
        if self.controller is None:
            return
        if self._session_started:
            return
        self._connect_requested = True
        self._session_started = True
        self._append_line("Connecting to the Raspberry Pi…")
        self._set_status("\U0001f50c Connecting to the Raspberry Pi…")
        self._connect_btn.setEnabled(False)
        # Reconnect after the reboot; CONNECTED triggers _start_session().
        self.controller.reconnect_ssh()

    def _start_session(self):
        if self.controller is None:
            return
        self._append_line("Connected. Starting the RFID reader configuration…")
        self._set_status("\U0001f6ed Configuration running — follow the prompts in the terminal.")
        self._session_active = True
        self._set_input_enabled(True)
        self._connect_btn.setEnabled(False)
        self.controller.start_reader_config_session(
            on_output=self._output_received.emit,
            on_exit=self._session_exited.emit,
        )

    def _stop_session(self):
        if self.controller is not None:
            self.controller.stop_reader_config_session()
        self._session_active = False
        self._set_input_enabled(False)
        self._set_status("Session stopped.")
        self._connect_btn.setEnabled(True)

    def _skip(self):
        if self.controller is not None:
            self.controller.stop_reader_config_session()
        self._session_active = False
        self._skipped = True
        self._set_input_enabled(False)
        self._set_status("Configuration skipped. You can run it later on the Pi with "
                         "'run_register_rfid_reader.py'.")

    def _send_input(self):
        text = self._input.text()
        if not text or not self._session_active:
            return
        self._input.clear()
        try:
            self.controller.send_reader_config_input(text + "\n")
        except Exception as e:
            self._set_status(f"Could not send input: {e}")

    # ------------------------------------------------------------------
    # SSH event handling
    # ------------------------------------------------------------------

    def _subscribe(self):
        self._event_bus.subscribe(SshEvents.CONNECTED, self._on_ssh_connected)
        self._event_bus.subscribe(SshEvents.AUTH_FAILED, self._on_ssh_error)
        self._event_bus.subscribe(SshEvents.ERROR, self._on_ssh_error)
        self._event_bus.subscribe(SshEvents.HOST_KEY_UNKNOWN, self._on_ssh_error)

    def _unsubscribe(self):
        self._event_bus.unsubscribe(SshEvents.CONNECTED, self._on_ssh_connected)
        self._event_bus.unsubscribe(SshEvents.AUTH_FAILED, self._on_ssh_error)
        self._event_bus.unsubscribe(SshEvents.ERROR, self._on_ssh_error)
        self._event_bus.unsubscribe(SshEvents.HOST_KEY_UNKNOWN, self._on_ssh_error)

    def _on_ssh_connected(self, payload: dict):
        if not self._connect_requested:
            return
        self._start_session()

    def _on_ssh_error(self, payload: dict):
        if not self._connect_requested:
            return
        reason = payload.get("reason") or payload.get("error") or "Unknown error"
        self._connect_requested = False
        self._session_started = False
        self._set_status(f"❌ Connection failed: {reason}")
        self._append_line(f"Connection failed: {reason}")
        self._connect_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Terminal output
    # ------------------------------------------------------------------

    def _on_output_received(self, text: str):
        self._terminal.moveCursor(self._terminal.textCursor().End)
        self._terminal.insertPlainText(text)
        self._terminal.moveCursor(self._terminal.textCursor().End)

    def _on_session_exited(self, exit_code: int):
        self._session_active = False
        self._session_done = True
        self._set_input_enabled(False)
        self._connect_btn.setEnabled(False)
        if exit_code == 0:
            self._set_status("✅ Configuration finished. The jukebox-daemon has been "
                             "restarted. You can now continue.")
        else:
            self._set_status(f"⚠️ Configuration ended with exit code {exit_code}. "
                             "The jukebox-daemon has been restarted. You can retry later "
                             "on the Pi or skip this step.")

    def _set_status(self, text: str):
        self._status_label.setText(text)

    def _append_line(self, text: str):
        self._terminal.appendPlainText(text)
