"""Reader configuration page — interactive configuration of manually
configured readers (generic_usb, generic_nfcpy, rc522_spi) after install.

After the installation and the reboot the page establishes a fresh SSH
connection, starts the official run_register_rfid_reader.py tool over a
pseudo-terminal and streams the output into a terminal-like widget. The user
answers the tool's prompts in the input line; the jukebox-daemon is stopped
before and restarted after the configuration (see READER_CONFIG_COMMAND).
"""

import re
import socket
import threading

from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLineEdit,
    QProgressBar,
)

from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import SshEvents
from phoniebox_installer.app.readers import MANUAL_CONFIG_READERS

#: Seconds without any remote output before the page warns the user that the
#: configuration process may be stuck (helps to distinguish a real hang from a
#: long-running but silent command).
NO_OUTPUT_WARNING_SECONDS = 20

#: Seconds the page waits after a successful reader configuration before
#: rebooting the Raspberry Pi (the new reader config is only fully applied
#: after a reboot).
REBOOT_COUNTDOWN_SECONDS = 30

#: Complete ANSI escape sequences: CSI (colors/cursor), OSC (e.g. title) and
#: single-character escapes. The terminal widget cannot render them, so they
#: are stripped before display. Note: the single-char class must exclude '[' and
#: ']' — those introduce CSI/OSC sequences and must not be consumed separately,
#: otherwise an incomplete CSI tail (e.g. ESC[96) would be mangled.
_ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI: ESC [ params ... final byte
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC: ESC ] ... BEL or ESC backslash
    r"|\x1b[^\[\]]"                        # single-char escapes (not CSI/OSC starts)
)


def strip_ansi(text: str, pending: str = "") -> tuple:
    """Remove ANSI escape sequences from ``text``.

    A chunk boundary may cut an escape sequence in half (e.g. ``ESC[9`` at the
    end of one chunk and ``2m`` at the start of the next). ``pending`` carries
    such an incomplete tail from the previous chunk.

    :param text: New raw output chunk
    :param pending: Incomplete escape tail from the previous chunk
    :return: ``(clean_text, pending)`` for the next call
    """
    combined = pending + text
    clean = _ANSI_ESCAPE_RE.sub("", combined)
    idx = clean.rfind("\x1b")
    if idx != -1:
        # After substitution only incomplete escapes remain → keep the tail.
        return clean[:idx], clean[idx:]
    return clean, ""


class ReaderConfigPage(BasePage):
    page_id = "reader_config"
    title = "RFID Reader Configuration"
    subtitle = "Configure the selected reader interactively on the Raspberry Pi."

    # Emitted from the SSH session thread; handled on the GUI thread (Qt
    # queues cross-thread signal deliveries automatically).
    _output_received = Signal(str)
    _session_exited = Signal(int)
    # Emitted from the availability-poll thread; handled on the GUI thread.
    _reachable = Signal(bool)

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._session_active = False
        self._session_started = False
        self._session_done = False
        self._skipped = False
        self._connect_requested = False
        self._ansi_pending = ""

        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._reboot_sent = False
        self._reboot_cancelled = False
        self._seen_down = False

        self._setup_ui()

        self._output_received.connect(self._on_output_received)
        self._session_exited.connect(self._on_session_exited)

        # Warns when no remote output arrives for a while (the session may be
        # stuck). Reset by every received output chunk.
        self._no_output_timer = QTimer(self)
        self._no_output_timer.setSingleShot(True)
        self._no_output_timer.setInterval(NO_OUTPUT_WARNING_SECONDS * 1000)
        self._no_output_timer.timeout.connect(self._on_no_output)

        # Reboot countdown + reachability polling (after a successful config).
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._poll_availability)
        self._reachable.connect(self._on_reachable)

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

        # Post-configuration reboot (a fresh reboot applies the new reader
        # config). Hidden until the configuration finished successfully.
        self._countdown_label = QLabel("")
        self._countdown_label.setWordWrap(True)
        self._countdown_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #b04a00;"
        )
        self._countdown_label.setVisible(False)
        layout.addWidget(self._countdown_label)

        self._reboot_spinner = QProgressBar()
        self._reboot_spinner.setRange(0, 0)  # indeterminate
        self._reboot_spinner.setTextVisible(False)
        self._reboot_spinner.setFixedHeight(16)
        self._reboot_spinner.setVisible(False)
        layout.addWidget(self._reboot_spinner)

        reboot_row = QHBoxLayout()
        self._restart_now_btn = QPushButton("\U0001f504 Restart Now")
        self._restart_now_btn.clicked.connect(self._restart_now)
        reboot_row.addWidget(self._restart_now_btn)
        self._cancel_reboot_btn = QPushButton("Cancel Restart")
        self._cancel_reboot_btn.clicked.connect(self._cancel_reboot)
        reboot_row.addWidget(self._cancel_reboot_btn)
        reboot_row.addStretch()
        layout.addLayout(reboot_row)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)

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
        self._ansi_pending = ""
        self._session_active = False
        self._session_started = False
        self._session_done = False
        self._skipped = False
        self._connect_requested = False
        # Reset the reboot state.
        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._reboot_sent = False
        self._reboot_cancelled = False
        self._seen_down = False
        self._countdown_label.setVisible(False)
        self._reboot_spinner.setVisible(False)
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)
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
        self._no_output_timer.stop()
        self._timer.stop()
        self._poll_timer.stop()
        self._unsubscribe()

    def validate(self):
        if not self.relevant(self.state):
            return (True, "")
        if self._skipped or self._session_done:
            return (True, "")
        if self._session_active:
            return (False, "Please finish the configuration (or skip it) before continuing.")
        return (True, "")

    def commit(self):
        """On wizard finish, honour the pending reboot intent."""
        if (self._session_done and not self._reboot_cancelled
                and not self._reboot_sent):
            self._do_reboot()

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
        try:
            self.controller.start_reader_config_session(
                on_output=self._output_received.emit,
                on_exit=self._session_exited.emit,
            )
        except Exception as e:
            # A failed session start (e.g. SSH dropped again) must be visible
            # instead of leaving the page stuck on "Configuration running".
            self._session_active = False
            self._session_started = False
            self._connect_requested = False
            self._set_input_enabled(False)
            self._connect_btn.setEnabled(True)
            self._set_status(f"❌ Could not start the configuration session: {e}")
            self._append_line(f"Error: {e}")
            return
        self._no_output_timer.start()

    def _stop_session(self):
        if self.controller is not None:
            self.controller.stop_reader_config_session()
        self._session_active = False
        self._no_output_timer.stop()
        self._set_input_enabled(False)
        self._set_status("Session stopped.")
        self._connect_btn.setEnabled(True)

    def _skip(self):
        if self.controller is not None:
            self.controller.stop_reader_config_session()
        self._session_active = False
        self._skipped = True
        self._no_output_timer.stop()
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
        clean, self._ansi_pending = strip_ansi(text, self._ansi_pending)
        if not clean:
            # Only ANSI codes / an incomplete escape tail — nothing to show yet.
            return
        # Move to the end with the correct PySide6 enum (QTextCursor.End does
        # not exist on the instance) — otherwise the slot throws inside the Qt
        # event loop and the remote output is never displayed.
        self._terminal.moveCursor(QTextCursor.MoveOperation.End)
        self._terminal.insertPlainText(clean)
        self._terminal.moveCursor(QTextCursor.MoveOperation.End)
        # Any output means the remote process is alive — restart the no-output
        # watchdog.
        if self._session_active:
            self._no_output_timer.start()

    def _on_no_output(self):
        """Show a warning when no remote output arrived for a while."""
        if not self._session_active:
            return
        self._set_status(
            "⚠️ No output received from the Raspberry Pi for a while — the "
            "configuration process may be stuck. Check the connection or stop "
            "the session (⏹ Stop Session) and retry."
        )
        self._append_line("(No output received — the remote process may be stuck.)")

    def _on_session_exited(self, exit_code: int):
        self._session_active = False
        self._session_done = True
        self._no_output_timer.stop()
        self._set_input_enabled(False)
        self._connect_btn.setEnabled(False)
        if exit_code == 0:
            self._set_status("✅ Configuration finished. The Raspberry Pi will be "
                             "restarted to apply the new reader configuration.")
            self._start_reboot_countdown()
        else:
            self._set_status(f"⚠️ Configuration ended with exit code {exit_code}. "
                             "The jukebox-daemon has been restarted. You can retry later "
                             "on the Pi or skip this step.")

    # ------------------------------------------------------------------
    # Post-configuration reboot
    # ------------------------------------------------------------------

    def _start_reboot_countdown(self):
        self._countdown_remaining = REBOOT_COUNTDOWN_SECONDS
        self._countdown_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #b04a00;"
        )
        self._update_countdown_label()
        self._countdown_label.setVisible(True)
        self._restart_now_btn.setVisible(True)
        self._restart_now_btn.setEnabled(True)
        self._cancel_reboot_btn.setVisible(True)
        self._cancel_reboot_btn.setEnabled(True)
        self._timer.start()

    def _tick(self):
        if self._reboot_sent or self._reboot_cancelled:
            return
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._do_reboot()
        else:
            self._update_countdown_label()

    def _update_countdown_label(self):
        self._countdown_label.setText(
            "\U0001f504 The Raspberry Pi will restart automatically in "
            f"{self._countdown_remaining} s\u2026"
        )

    def _restart_now(self):
        self._do_reboot()

    def _cancel_reboot(self):
        if self._reboot_sent:
            return
        self._reboot_cancelled = True
        self._timer.stop()
        self._countdown_label.setText(
            "Restart cancelled. Please restart the Pi manually later."
        )
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)

    def _do_reboot(self):
        if self._reboot_sent or self._reboot_cancelled:
            return
        self._reboot_sent = True
        self._timer.stop()
        self._countdown_label.setText("\U0001f504 Restarting the Raspberry Pi\u2026")
        self._restart_now_btn.setVisible(False)
        self._cancel_reboot_btn.setVisible(False)
        self._reboot_spinner.setVisible(True)
        self._start_availability_poll()
        if self.controller is not None:
            self.controller.reboot_target()

    def _start_availability_poll(self):
        self._seen_down = False
        self._poll_timer.start()
        self._poll_availability()

    def _poll_availability(self):
        if not self.state.target_host:
            return
        threading.Thread(target=self._emit_reachability, daemon=True).start()

    def _emit_reachability(self):
        self._reachable.emit(self._check_reachable())

    def _check_reachable(self) -> bool:
        """Return True if the SSH port accepts a connection (Pi is back up)."""
        host = self.state.target_host
        port = self.state.ssh_port
        if not host:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                return s.connect_ex((host, port)) == 0
        except OSError:
            return False

    def _on_reachable(self, reachable: bool):
        if reachable:
            if self._seen_down:
                # The Pi went offline and is back — reboot complete.
                self._poll_timer.stop()
                self._reboot_spinner.setVisible(False)
                self._countdown_label.setStyleSheet(
                    "font-size: 16px; font-weight: bold; color: #2a7d2a;"
                )
                self._countdown_label.setText(
                    "\u2705 Restart complete — the Raspberry Pi is back online. "
                    "You can now close the installer."
                )
        else:
            self._seen_down = True

    def _set_status(self, text: str):
        self._status_label.setText(text)

    def _append_line(self, text: str):
        self._terminal.appendPlainText(text)
