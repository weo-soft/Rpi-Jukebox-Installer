"""System check page — pre-flight checks via SSH, results as ✅/⚠️/❌."""

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel
from phoniebox_installer.gui.pages.base import BasePage
from phoniebox_installer.app.events import CheckEvents
from phoniebox_installer.installer.checks import CHECKS


class SystemCheckPage(BasePage):
    page_id = "system_check"
    title = "System Check"
    subtitle = "Checking your Raspberry Pi before installation."

    def __init__(self, state, event_bus, controller=None, parent=None):
        super().__init__(state, event_bus, controller=controller, parent=parent)
        self._results = {}    # key → Wert (typisiert); zusätzlich "status": {key: pass|warn|fail}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self._status = QLabel("Running checks…")
        layout.addWidget(self._status)
        self._table = QTableWidget(len(CHECKS), 3)
        self._table.setHorizontalHeaderLabels(["Check", "Result", "Value"])
        for row, (_, label, _, _) in enumerate(CHECKS):
            self._table.setItem(row, 0, QTableWidgetItem(label))
        layout.addWidget(self._table)

    def on_enter(self):
        self.event_bus.subscribe(CheckEvents.CHECK_COMPLETED, self._on_completed)
        if self.controller is not None:
            self.controller.run_system_check()

    def _on_completed(self, payload):
        self._results.update(payload)
        self._update_table()

    def _update_table(self):
        status = self._results.get("status", {})
        for row, (key, _, _, _) in enumerate(CHECKS):
            value = str(self._results.get(key, ""))
            st = status.get(key, "pending")
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "pending": "⏳"}[st]
            self._table.setItem(row, 1, QTableWidgetItem(icon))
            self._table.setItem(row, 2, QTableWidgetItem(value))

    def validate(self):
        status = self._results.get("status", {})
        fails = [k for k, _, _, _ in CHECKS if status.get(k) == "fail"]
        if fails:
            return (False, f"Critical checks failed: {', '.join(fails)}")
        return (True, "")

    def on_leave(self):
        self.event_bus.unsubscribe(CheckEvents.CHECK_COMPLETED, self._on_completed)
