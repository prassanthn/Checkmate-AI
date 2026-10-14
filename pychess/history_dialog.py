"""Dialog listing past games with overall statistics."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .history import GameHistory, format_duration

RESULT_COLORS = {"win": "#6ee7a0", "loss": "#ff8a8a", "draw": "#8a93a6"}


def stat_tile(value: str, label: str, color: str | None = None) -> QFrame:
    tile = QFrame()
    tile.setObjectName("Card")
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(0)
    number = QLabel(value)
    number.setObjectName("StatValue")
    if color:
        number.setStyleSheet(f"color: {color};")
    caption = QLabel(label.upper())
    caption.setObjectName("CardTitle")
    layout.addWidget(number)
    layout.addWidget(caption)
    return tile


class HistoryDialog(QDialog):
    def __init__(self, history: GameHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.setWindowTitle("Game history")
        self.resize(820, 520)

        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(18, 18, 18, 18)
        self.layout_.setSpacing(14)

        self.tiles = QHBoxLayout()
        self.tiles.setSpacing(10)
        self.layout_.addLayout(self.tiles)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Result", "You", "Mode", "Opponent", "Moves", "Duration"]
        )
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(30)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.layout_.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Clear history")
        self.clear_button.clicked.connect(self._clear)
        close_button = QPushButton("Close")
        close_button.setObjectName("Primary")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        self.layout_.addLayout(buttons)

        self._populate()

    def _populate(self) -> None:
        while self.tiles.count():
            self.tiles.takeAt(0).widget().deleteLater()
        s = self.history.summary()
        win_rate = f"{round(100 * s.wins / s.games)}%" if s.games else "–"
        for value, label, color in (
            (str(s.games), "Games", None),
            (str(s.wins), "Wins", RESULT_COLORS["win"]),
            (str(s.losses), "Losses", RESULT_COLORS["loss"]),
            (str(s.draws), "Draws", RESULT_COLORS["draw"]),
            (win_rate, "Win rate", None),
            (format_duration(s.total_seconds), "Total time", None),
            (str(s.total_moves), "Total moves", None),
        ):
            self.tiles.addWidget(stat_tile(value, label, color))

        records = list(reversed(self.history.records))  # newest first
        self.table.setRowCount(len(records))
        for row, r in enumerate(records):
            try:
                when = datetime.fromisoformat(r.finished_at).strftime("%d %b %Y  %H:%M")
            except ValueError:
                when = r.finished_at
            result = QTableWidgetItem(f"{r.result.capitalize()} · {r.reason}")
            result.setForeground(QColor(RESULT_COLORS.get(r.result, "#e7eaf0")))
            cells = [
                QTableWidgetItem(when), result,
                QTableWidgetItem(r.player_color.capitalize()),
                QTableWidgetItem(r.difficulty.capitalize()),
                QTableWidgetItem(r.opponent),
                QTableWidgetItem(str(r.moves)),
                QTableWidgetItem(format_duration(r.duration_seconds)),
            ]
            for col, item in enumerate(cells):
                self.table.setItem(row, col, item)
        self.clear_button.setEnabled(bool(records))

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self, "Clear history", "Delete the record of all past games? This can't be undone."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self._populate()
