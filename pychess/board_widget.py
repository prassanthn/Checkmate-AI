"""Interactive chess board: drag-and-drop / click moves, hints, snap-back on illegal drops."""

from __future__ import annotations

import chess
import chess.svg
from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QInputDialog, QSizePolicy, QWidget

from .theme import BOARD_DARK as DARK
from .theme import BOARD_LIGHT as LIGHT

SELECTED = QColor(242, 184, 75, 150)
LAST_MOVE = QColor(242, 196, 90, 115)
HINT = QColor(15, 23, 42, 85)
HOVER_TARGET = QColor(242, 184, 75, 110)
CHECK = QColor(255, 60, 60)

DRAG_THRESHOLD = 4
MARGIN = 18          # room around the board for its shadow
CORNER_RADIUS = 10


def explain_illegal(board: chess.Board, origin: int, target: int) -> str:
    piece = board.piece_at(origin)
    name = chess.piece_name(piece.piece_type)
    frm, to = chess.square_name(origin), chess.square_name(target)
    occupant = board.piece_at(target)

    if occupant and occupant.color == piece.color:
        return f"Illegal move: you can't capture your own {chess.piece_name(occupant.piece_type)}."
    pseudo_legal = any(m.from_square == origin and m.to_square == target
                       for m in board.pseudo_legal_moves)
    if pseudo_legal:
        if board.is_check():
            return "Illegal move: your king is in check and that move doesn't get it out of check."
        if piece.piece_type == chess.KING:
            return f"Illegal move: the king can't move to {to}, that square is attacked."
        return f"Illegal move: that {name} is pinned. Moving it would expose your king."
    if piece.piece_type == chess.KING and abs(chess.square_file(origin) - chess.square_file(target)) == 2:
        return "Illegal move: you can't castle right now."
    suffix = " (Your king is in check!)" if board.is_check() else ""
    return f"Illegal move: a {name} can't move from {frm} to {to}.{suffix}"


class BoardWidget(QWidget):
    move_made = Signal(str)        # UCI of the move the human played
    info = Signal(str, str)        # message, level ("info" | "warning" | "error")

    def __init__(self, board: chess.Board, parent: QWidget | None = None):
        super().__init__(parent)
        self.board = board
        self.player_color = chess.WHITE
        self.show_hints = True
        self.interactive = True
        self.selected: int | None = None
        self.drag_square: int | None = None
        self.drag_pos: QPointF | None = None
        self.press_pos: QPointF | None = None
        self.snap_square: int | None = None
        self.snap_pos: QPointF | None = None
        # Vector piece images (the standard set bundled with python-chess).
        self._piece_svgs = {
            symbol: QSvgRenderer(QByteArray(chess.svg.piece(chess.Piece.from_symbol(symbol)).encode()))
            for symbol in "KQRBNPkqrbnp"
        }

        self.snap_anim = QVariantAnimation(self)
        self.snap_anim.setDuration(200)
        self.snap_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.snap_anim.valueChanged.connect(self._on_snap_step)
        self.snap_anim.finished.connect(self._on_snap_done)

        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ----- public API -------------------------------------------------------------------

    @property
    def flipped(self) -> bool:
        return self.player_color == chess.BLACK

    def reset_interaction(self) -> None:
        self.selected = self.drag_square = self.drag_pos = self.press_pos = None
        self.snap_anim.stop()
        self.snap_square = self.snap_pos = None
        self.update()

    # ----- geometry ---------------------------------------------------------------------

    def _square_size(self) -> float:
        return max(1.0, (min(self.width(), self.height()) - 2 * MARGIN) / 8)

    def _origin(self) -> QPointF:
        size = self._square_size() * 8
        return QPointF((self.width() - size) / 2, (self.height() - size) / 2)

    def square_rect(self, square: int) -> QRectF:
        s = self._square_size()
        file, rank = chess.square_file(square), chess.square_rank(square)
        col = 7 - file if self.flipped else file
        row = rank if self.flipped else 7 - rank
        o = self._origin()
        return QRectF(o.x() + col * s, o.y() + row * s, s, s)

    def square_at(self, pos: QPointF) -> int | None:
        s = self._square_size()
        o = self._origin()
        col, row = int((pos.x() - o.x()) // s), int((pos.y() - o.y()) // s)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        file = 7 - col if self.flipped else col
        rank = row if self.flipped else 7 - row
        return chess.square(file, rank)

    # ----- mouse handling -----------------------------------------------------------------

    def _players_turn(self) -> bool:
        return self.interactive and self.board.turn == self.player_color and not self.board.is_game_over()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.snap_anim.state() == QVariantAnimation.State.Running:
            return
        pos = event.position()
        square = self.square_at(pos)
        if square is None:
            return
        if not self._players_turn():
            if not self.board.is_game_over():
                self.info.emit("Please wait, it's the AI's turn.", "info")
            return

        piece = self.board.piece_at(square)
        if piece and piece.color == self.player_color:
            self.selected = square
            self.drag_square = square
            self.drag_pos = None  # becomes a drag once the mouse moves past the threshold
            self.press_pos = pos
        elif self.selected is not None:
            self._attempt_move(self.selected, square)
        elif piece:
            self.info.emit("That's your opponent's piece. Select one of your own pieces.", "warning")
        self.update()

    def mouseMoveEvent(self, event):
        if self.drag_square is None:
            return
        pos = event.position()
        if self.drag_pos is None and (pos - self.press_pos).manhattanLength() < DRAG_THRESHOLD:
            return
        self.drag_pos = pos
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.drag_square is None:
            return
        origin, pos, dragged = self.drag_square, event.position(), self.drag_pos is not None
        self.drag_square = self.drag_pos = self.press_pos = None
        if not dragged:
            self.update()  # plain click: keep the piece selected
            return
        target = self.square_at(pos)
        if target is None:
            self.info.emit("Piece dropped outside the board, so it went back.", "warning")
            self._snap_back(origin, pos)
        elif target != origin:
            self._attempt_move(origin, target, drop_pos=pos)
        self.update()

    def _attempt_move(self, origin: int, target: int, drop_pos: QPointF | None = None) -> None:
        candidates = [m for m in self.board.legal_moves
                      if m.from_square == origin and m.to_square == target]
        if candidates:
            move = candidates[0]
            if len(candidates) > 1:  # promotion
                move = self._ask_promotion(candidates)
                if move is None:
                    if drop_pos is not None:
                        self._snap_back(origin, drop_pos)
                    return
            self.selected = None
            self.board.push(move)
            self.move_made.emit(move.uci())
            return

        occupant = self.board.piece_at(target)
        if drop_pos is None and occupant and occupant.color == self.player_color:
            self.selected = target  # click on another own piece: switch selection
            return
        self.info.emit(explain_illegal(self.board, origin, target), "error")
        if drop_pos is not None:
            self._snap_back(origin, drop_pos)

    def _ask_promotion(self, moves: list[chess.Move]) -> chess.Move | None:
        names = {chess.piece_name(m.promotion).capitalize(): m for m in moves}
        order = [n for n in ("Queen", "Rook", "Bishop", "Knight") if n in names]
        choice, ok = QInputDialog.getItem(self, "Promotion", "Promote pawn to:", order, 0, False)
        return names[choice] if ok else None

    # ----- snap-back animation ------------------------------------------------------------

    def _snap_back(self, origin: int, from_pos: QPointF) -> None:
        self.snap_square = origin
        self.snap_anim.setStartValue(from_pos)
        self.snap_anim.setEndValue(self.square_rect(origin).center())
        self.snap_anim.start()

    def _on_snap_step(self, value):
        self.snap_pos = value
        self.update()

    def _on_snap_done(self):
        self.snap_square = self.snap_pos = None
        self.update()

    # ----- painting -------------------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self._square_size()
        board = self.board
        o = self._origin()
        board_rect = QRectF(o.x(), o.y(), s * 8, s * 8)

        # soft drop shadow
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(MARGIN, 0, -2):
            p.setBrush(QColor(0, 0, 0, int(26 * (1 - i / MARGIN)) + 2))
            p.drawRoundedRect(board_rect.adjusted(-i, -i + 4, i, i + 4),
                              CORNER_RADIUS + i, CORNER_RADIUS + i)

        clip = QPainterPath()
        clip.addRoundedRect(board_rect, CORNER_RADIUS, CORNER_RADIUS)
        p.setClipPath(clip)

        for square in chess.SQUARES:
            rect = self.square_rect(square)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            p.fillRect(rect, LIGHT if light else DARK)

        if board.move_stack:
            last = board.peek()
            for sq in (last.from_square, last.to_square):
                p.fillRect(self.square_rect(sq), LAST_MOVE)
        if self.selected is not None:
            p.fillRect(self.square_rect(self.selected), SELECTED)
        if board.is_check():
            king = board.king(board.turn)
            if king is not None:
                rect = self.square_rect(king)
                glow = QRadialGradient(rect.center(), s * 0.6)
                glow.setColorAt(0.0, CHECK)
                glow.setColorAt(0.55, QColor(CHECK.red(), CHECK.green(), CHECK.blue(), 150))
                glow.setColorAt(1.0, QColor(CHECK.red(), CHECK.green(), CHECK.blue(), 0))
                p.fillRect(rect, glow)

        hint_targets = self._hint_targets()
        if self.drag_pos is not None and self.show_hints:
            hover = self.square_at(self.drag_pos)
            if hover in hint_targets:
                p.fillRect(self.square_rect(hover), HOVER_TARGET)

        self._draw_coordinates(p, s)

        hidden = {self.drag_square if self.drag_pos is not None else None, self.snap_square}
        for square, piece in board.piece_map().items():
            if square not in hidden:
                self._draw_piece(p, piece, self.square_rect(square).center(), s)

        for target, capture in hint_targets.items():
            rect = self.square_rect(target)
            p.setBrush(Qt.BrushStyle.NoBrush if capture else HINT)
            if capture:
                p.setPen(QPen(HINT, s * 0.08))
                p.drawEllipse(rect.adjusted(s * 0.06, s * 0.06, -s * 0.06, -s * 0.06))
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(rect.center(), s * 0.16, s * 0.16)

        p.setClipping(False)  # the dragged piece may leave the board
        if self.drag_pos is not None and self.drag_square is not None:
            self._draw_piece(p, board.piece_at(self.drag_square), self.drag_pos, s * 1.1)
        if self.snap_pos is not None and self.snap_square is not None:
            piece = board.piece_at(self.snap_square)
            if piece:
                self._draw_piece(p, piece, self.snap_pos, s)
        p.end()

    def _hint_targets(self) -> dict[int, bool]:
        """Legal target squares for the selected piece (beginner mode only) -> is_capture."""
        if not self.show_hints or self.selected is None or not self._players_turn():
            return {}
        return {m.to_square: self.board.is_capture(m)
                for m in self.board.legal_moves if m.from_square == self.selected}

    def _draw_coordinates(self, p: QPainter, s: float) -> None:
        font = QFont()
        font.setPixelSize(max(9, int(s * 0.16)))
        font.setBold(True)
        p.setFont(font)
        pad = s * 0.05
        for i in range(8):
            file = 7 - i if self.flipped else i
            rank = i if self.flipped else 7 - i
            bottom = self.square_rect(chess.square(file, 0 if not self.flipped else 7))
            left = self.square_rect(chess.square(0 if not self.flipped else 7, rank))
            p.setPen(DARK if (file + (0 if not self.flipped else 7)) % 2 else LIGHT)
            p.drawText(bottom.adjusted(pad, pad, -pad, -pad),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, chess.FILE_NAMES[file])
            p.setPen(DARK if ((0 if not self.flipped else 7) + rank) % 2 else LIGHT)
            p.drawText(left.adjusted(pad, pad, -pad, -pad),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, chess.RANK_NAMES[rank])

    def _draw_piece(self, p: QPainter, piece: chess.Piece, center: QPointF, s: float) -> None:
        size = s * 0.92
        rect = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
        self._piece_svgs[piece.symbol()].render(p, rect)
