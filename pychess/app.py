"""Main window: game flow, AI turns, move list and the info bar."""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

import chess
import chess.svg
from PySide6.QtCore import QByteArray, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import theme
from .ai import AIError, ChessAI
from .board_widget import BoardWidget
from .history import GameHistory, GameRecord, format_duration
from .history_dialog import RESULT_COLORS, HistoryDialog
from .settings import DIFFICULTIES, PROVIDER_LABELS, Settings
from .settings_dialog import SettingsDialog

MODE_DESCRIPTIONS = {
    "beginner": "Possible moves are highlighted. The AI plays casually.",
    "intermediate": "No move hints. The AI plays like a club player.",
    "advanced": "No move hints. The AI plays its strongest moves.",
}


class AISignals(QObject):
    # Emitted from the worker thread; Qt queues delivery onto the GUI thread.
    done = Signal(int, str, str)    # game id, move uci, note
    failed = Signal(int, str)       # game id, error message


class Segmented(QFrame):
    """A row of mutually exclusive toggle buttons (a segmented control)."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for key, label in options:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setChecked(key == value)
            button.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(button)
            self.buttons[key] = button
            layout.addWidget(button, 1)

    def set_value(self, key: str) -> None:
        self.buttons[key].setChecked(True)
        self.changed.emit(key)


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)
    label = QLabel(title.upper())
    label.setObjectName("CardTitle")
    layout.addWidget(label)
    return frame, layout


def piece_icon(symbol: str = "N", size: int = 64) -> QIcon:
    svg = chess.svg.piece(chess.Piece.from_symbol(symbol)).encode()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg)).render(painter)
    painter.end()
    return QIcon(pixmap)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(theme.APP_NAME)
        self.setWindowIcon(piece_icon())
        self.resize(1120, 840)
        self.setMinimumSize(900, 760)

        self.settings = Settings.load()
        self.history = GameHistory()
        self.board = chess.Board()
        self.game_id = 0
        self.ai_thinking = False
        self.game_started = time.monotonic()
        self.game_finished = False

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)

        self.ai_signals = AISignals()
        self.ai_signals.done.connect(self._on_ai_done)
        self.ai_signals.failed.connect(self._on_ai_failed)

        self.thinking_timer = QTimer(self)
        self.thinking_timer.setInterval(1000)
        self.thinking_timer.timeout.connect(self._update_thinking)

        self.board_widget = BoardWidget(self.board)
        self.board_widget.move_made.connect(self._on_player_move)
        self.board_widget.info.connect(self.show_info)

        central = QWidget()
        central.setObjectName("Central")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(18, 8, 20, 6)
        body.setSpacing(18)
        body.addWidget(self.board_widget, 1)
        body.addWidget(self._build_side_panel())
        root.addLayout(body, 1)
        root.addWidget(self._build_info_bar())
        self.setCentralWidget(central)

        self._add_shortcuts()
        self._apply_difficulty()
        self._update_opponent()
        self._update_record()
        self.new_game()

    # ----- UI construction ------------------------------------------------------------------

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 14, 22, 14)
        layout.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(piece_icon("N", 40).pixmap(40, 40))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel(theme.APP_NAME)
        title.setObjectName("AppTitle")
        subtitle = QLabel("Play chess against an AI opponent")
        subtitle.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)

        layout.addWidget(logo)
        layout.addLayout(titles)
        layout.addStretch(1)

        self.retry_button = self._button("Retry AI move", self._start_ai_turn, "Ask the AI again")
        self.retry_button.setEnabled(False)
        self.undo_button = self._button("Undo", self.undo, "Take back your last move (Ctrl+Z)")
        self.resign_button = self._button("Resign", self.resign, "Give up this game (counts as a loss)")
        history_button = self._button("History", self.open_history, "Past games and statistics (Ctrl+H)")
        settings_button = self._button("Settings", self.open_settings, "AI provider and model (Ctrl+,)")
        new_button = self._button("New game", self.new_game, "Start a new game (Ctrl+N)")
        new_button.setObjectName("Primary")
        for button in (self.retry_button, self.undo_button, self.resign_button, history_button,
                       settings_button, new_button):
            layout.addWidget(button)
        return header

    def _button(self, text: str, slot, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.clicked.connect(slot)
        return button

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(14)

        # Game options
        game_card, game_layout = card("Game")
        self.mode_control = Segmented(
            [(d, d.capitalize()) for d in DIFFICULTIES], self.settings.difficulty
        )
        self.mode_control.changed.connect(self._on_difficulty_changed)
        self.mode_description = QLabel()
        self.mode_description.setObjectName("Muted")
        self.mode_description.setWordWrap(True)
        self.mode_description.setMinimumHeight(self.mode_description.fontMetrics().lineSpacing() * 2 + 4)
        play_as = QLabel("Play as")
        play_as.setObjectName("Muted")
        self.color_control = Segmented(
            [("white", "White"), ("black", "Black")], self.settings.player_color
        )
        self.color_control.setToolTip("Takes effect when you start a new game")
        self.color_control.changed.connect(self._on_color_changed)
        game_layout.addWidget(self.mode_control)
        game_layout.addWidget(self.mode_description)
        game_layout.addSpacing(4)
        game_layout.addWidget(play_as)
        game_layout.addWidget(self.color_control)
        clock_row = QHBoxLayout()
        clock_caption = QLabel("Game time")
        clock_caption.setObjectName("Muted")
        self.clock_label = QLabel("00:00")
        self.clock_label.setObjectName("Clock")
        clock_row.addWidget(clock_caption)
        clock_row.addStretch(1)
        clock_row.addWidget(self.clock_label)
        game_layout.addSpacing(4)
        game_layout.addLayout(clock_row)
        layout.addWidget(game_card)

        # Opponent
        opp_card, opp_layout = card("Opponent")
        row = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        self.model_label = QLabel()
        self.model_label.setObjectName("ModelName")
        self.provider_label = QLabel()
        self.provider_label.setObjectName("Muted")
        names.addWidget(self.model_label)
        names.addWidget(self.provider_label)
        self.status_pill = QLabel()
        self.status_pill.setObjectName("StatusPill")
        row.addLayout(names, 1)
        row.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignTop)
        opp_layout.addLayout(row)
        layout.addWidget(opp_card)

        # Record (wins / losses / draws across all games)
        record_card, record_layout = card("Your record")
        stats = QHBoxLayout()
        stats.setSpacing(6)
        self.record_labels: dict[str, QLabel] = {}
        for key, caption in (("win", "Wins"), ("loss", "Losses"), ("draw", "Draws")):
            column = QVBoxLayout()
            column.setSpacing(0)
            value = QLabel("0")
            value.setObjectName("StatValue")
            value.setStyleSheet(f"color: {RESULT_COLORS[key]};")
            label = QLabel(caption)
            label.setObjectName("Muted")
            column.addWidget(value)
            column.addWidget(label)
            stats.addLayout(column, 1)
            self.record_labels[key] = value
        record_layout.addLayout(stats)
        self.record_totals = QLabel()
        self.record_totals.setObjectName("Muted")
        record_layout.addWidget(self.record_totals)
        layout.addWidget(record_card)

        # Moves
        moves_card, moves_layout = card("Moves")
        self.move_table = QTableWidget(0, 3)
        self.move_table.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.move_table.verticalHeader().hide()
        self.move_table.setShowGrid(False)
        self.move_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.move_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.move_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.move_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.move_table.setColumnWidth(0, 40)
        self.move_table.verticalHeader().setDefaultSectionSize(30)
        self.move_table.setMinimumHeight(110)
        moves_layout.addWidget(self.move_table, 1)
        layout.addWidget(moves_card, 1)
        return panel

    def _build_info_bar(self) -> QWidget:
        wrapper = QWidget()
        outer = QHBoxLayout(wrapper)
        outer.setContentsMargins(20, 6, 20, 16)
        self.info_bar = QFrame()
        self.info_bar.setObjectName("InfoBar")
        inner = QHBoxLayout(self.info_bar)
        inner.setContentsMargins(14, 10, 14, 10)
        self.info_label = QLabel()
        self.info_label.setObjectName("InfoText")
        self.info_label.setWordWrap(True)
        inner.addWidget(self.info_label)
        outer.addWidget(self.info_bar)
        return wrapper

    def _add_shortcuts(self) -> None:
        for key, slot in (("Ctrl+N", self.new_game), ("Ctrl+Z", self.undo),
                          ("Ctrl+,", self.open_settings), ("Ctrl+H", self.open_history)):
            action = QAction(self)
            action.setShortcut(key)
            action.triggered.connect(slot)
            self.addAction(action)

    # ----- status displays ------------------------------------------------------------------

    def show_info(self, text: str, level: str = "info") -> None:
        self.info_label.setText(text)
        self.info_bar.setProperty("level", level)
        repolish(self.info_bar)

    def _set_status(self, state: str, text: str) -> None:
        self.status_pill.setText(text)
        self.status_pill.setProperty("state", state)
        repolish(self.status_pill)

    def _update_opponent(self) -> None:
        self.model_label.setText(self.settings.active.model)
        self.provider_label.setText(PROVIDER_LABELS[self.settings.provider].split(" (")[0])

    def _update_clock(self) -> None:
        self.clock_label.setText(format_duration(time.monotonic() - self.game_started))

    def _update_record(self) -> None:
        s = self.history.summary()
        self.record_labels["win"].setText(str(s.wins))
        self.record_labels["loss"].setText(str(s.losses))
        self.record_labels["draw"].setText(str(s.draws))
        self.record_totals.setText(
            f"{s.games} games · {format_duration(s.total_seconds)} played · {s.total_moves} moves"
        )

    def open_history(self) -> None:
        HistoryDialog(self.history, self).exec()
        self._update_record()  # history may have been cleared

    def _refresh_moves(self) -> None:
        replay = self.board.root()
        sans = []
        for move in self.board.move_stack:
            sans.append(replay.san(move))
            replay.push(move)
        rows = (len(sans) + 1) // 2
        self.move_table.setRowCount(rows)
        for row in range(rows):
            number = QTableWidgetItem(f"{row + 1}.")
            number.setForeground(Qt.GlobalColor.gray)
            self.move_table.setItem(row, 0, number)
            for col in (1, 2):
                index = row * 2 + col - 1
                item = QTableWidgetItem(sans[index] if index < len(sans) else "")
                if index == len(sans) - 1:
                    item.setForeground(Qt.GlobalColor.white)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.move_table.setItem(row, col, item)
        self.move_table.scrollToBottom()

    # ----- settings / modes -----------------------------------------------------------------

    def _apply_difficulty(self) -> None:
        self.board_widget.show_hints = self.settings.difficulty == "beginner"
        self.mode_description.setText(MODE_DESCRIPTIONS[self.settings.difficulty])
        self.board_widget.update()

    def _on_difficulty_changed(self, difficulty: str) -> None:
        self.settings.difficulty = difficulty
        self.settings.save()
        self._apply_difficulty()
        hints = "Move hints are on." if difficulty == "beginner" else "Move hints are off."
        self.show_info(f"{difficulty.capitalize()} mode. {hints}")

    def _on_color_changed(self, color: str) -> None:
        self.settings.player_color = color
        self.settings.save()
        self.show_info(f"You'll play {color.capitalize()} when you start a new game.")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        dialog.apply_to(self.settings)
        self.settings.save()
        self._update_opponent()
        self.show_info(f"Settings saved. Opponent: {self.settings.provider} · {self.settings.active.model}")
        if self._is_ai_turn() and not self.ai_thinking:
            self._start_ai_turn()

    # ----- game flow -------------------------------------------------------------------------

    def _player_color(self) -> chess.Color:
        return self.board_widget.player_color

    def _is_ai_turn(self) -> bool:
        return not self.board.is_game_over(claim_draw=True) and self.board.turn != self._player_color()

    def new_game(self) -> None:
        self.game_id += 1
        self.ai_thinking = False
        self.retry_button.setEnabled(False)
        self.board.reset()
        self.game_started = time.monotonic()
        self.game_finished = False
        self.resign_button.setEnabled(True)
        self.undo_button.setEnabled(True)
        self._update_clock()
        self.clock_timer.start()
        self.board_widget.player_color = chess.WHITE if self.settings.player_color == "white" else chess.BLACK
        self.board_widget.interactive = True
        self.board_widget.reset_interaction()
        self._refresh_moves()
        if self._is_ai_turn():
            self._start_ai_turn()
        else:
            self._set_status("your-turn", "Your turn")
            self.show_info("New game. You play White. Drag a piece or click it, then click a target square.")

    def resign(self) -> None:
        if self.game_finished:
            return
        answer = QMessageBox.question(self, "Resign", "Resign this game? It will count as a loss.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.game_id += 1  # ignore any pending AI answer
        self.ai_thinking = False
        self._finish_game("loss", "resigned", "You resigned. The AI wins.")

    def undo(self) -> None:
        if self.game_finished:
            self.show_info("The game is over. Start a new game to play again.", "warning")
            return
        if not self.board.move_stack:
            self.show_info("Nothing to undo.", "warning")
            return
        self.game_id += 1  # discard any AI answer that is still pending
        self.ai_thinking = False
        self.board.pop()
        if self.board.turn != self._player_color() and self.board.move_stack:
            self.board.pop()
        self.board_widget.interactive = True
        self.board_widget.reset_interaction()
        self._refresh_moves()
        if self._is_ai_turn():  # e.g. playing Black and undid back to the start
            self._start_ai_turn()
        else:
            self.retry_button.setEnabled(False)
            self._set_status("your-turn", "Your turn")
            self.show_info("Move undone. Your turn.")

    def _on_player_move(self, uci: str) -> None:
        self._refresh_moves()
        self.board_widget.update()
        if self._check_game_over():
            return
        self._start_ai_turn()

    def _start_ai_turn(self) -> None:
        if not self._is_ai_turn() or self.ai_thinking:
            return
        self.ai_thinking = True
        self.retry_button.setEnabled(False)
        self.board_widget.interactive = False
        ai = ChessAI(self.settings.provider, self.settings.active, self.settings.difficulty)
        self._thinking_label = ai.label
        self._thinking_started = time.monotonic()
        self._update_thinking()
        self.thinking_timer.start()
        threading.Thread(
            target=self._ai_worker, args=(ai, self.board.copy(), self.game_id), daemon=True
        ).start()

    def _update_thinking(self) -> None:
        if not self.ai_thinking:
            self.thinking_timer.stop()
            return
        elapsed = int(time.monotonic() - self._thinking_started)
        self._set_status("thinking", f"Thinking… {elapsed}s")
        self.show_info(f"AI ({self._thinking_label}) is thinking… {elapsed}s")

    def _ai_worker(self, ai: ChessAI, board: chess.Board, game_id: int) -> None:
        try:
            move, note = ai.choose_move(board)
            self.ai_signals.done.emit(game_id, move.uci(), note or "")
        except AIError as e:
            self.ai_signals.failed.emit(game_id, str(e))
        except Exception as e:  # noqa: BLE001 - surface anything unexpected in the info bar
            self.ai_signals.failed.emit(game_id, f"Unexpected AI error: {e}")

    def _on_ai_done(self, game_id: int, uci: str, note: str) -> None:
        if game_id != self.game_id:
            return
        self.ai_thinking = False
        move = chess.Move.from_uci(uci)
        san = self.board.san(move)
        self.board.push(move)
        self.board_widget.interactive = True
        self.board_widget.update()
        self._refresh_moves()
        if self._check_game_over():
            return
        self._set_status("your-turn", "Your turn")
        msg = f"AI played {san}. Your move."
        if self.board.is_check():
            msg = f"AI played {san}. Check! Protect your king."
        self.show_info(f"{msg} {note}".strip(), "warning" if note or self.board.is_check() else "info")

    def _on_ai_failed(self, game_id: int, message: str) -> None:
        if game_id != self.game_id:
            return
        self.ai_thinking = False
        self.retry_button.setEnabled(True)
        self._set_status("error", "Error")
        self.show_info(f"{message} Fix it in Settings, then press Retry AI move.", "error")

    def _check_game_over(self) -> bool:
        outcome = self.board.outcome(claim_draw=True)
        if outcome is None:
            return False
        reason = outcome.termination.name.replace("_", " ").lower()
        if outcome.winner is None:
            self._finish_game("draw", reason, f"Draw ({reason}).")
        elif outcome.winner == self._player_color():
            self._finish_game("win", reason, "Checkmate. You win!")
        else:
            self._finish_game("loss", reason, "Checkmate. The AI wins.")
        return True

    def _finish_game(self, result: str, reason: str, text: str) -> None:
        self.game_finished = True
        self.clock_timer.stop()
        self.retry_button.setEnabled(False)
        self.resign_button.setEnabled(False)
        self.undo_button.setEnabled(False)
        self.board_widget.interactive = False
        self.board_widget.reset_interaction()

        duration = int(time.monotonic() - self.game_started)
        self.history.add(GameRecord(
            finished_at=datetime.now().isoformat(timespec="seconds"),
            result=result,
            reason=reason,
            player_color="white" if self._player_color() == chess.WHITE else "black",
            difficulty=self.settings.difficulty,
            opponent=f"{self.settings.provider} · {self.settings.active.model}",
            moves=(len(self.board.move_stack) + 1) // 2,
            duration_seconds=duration,
        ))
        self._update_record()
        self._update_clock()

        self._set_status("over", "Game over")
        self.show_info(f"Game over: {text} Game time {format_duration(duration)}.", "warning")
        QMessageBox.information(self, "Game over", f"{text}\n\nGame time: {format_duration(duration)}")


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(theme.APP_NAME)
    theme.apply(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
