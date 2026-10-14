"""Persistent record of finished games (results, length, duration)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

HISTORY_PATH = Path.home() / ".pychess" / "history.json"

RESULTS = ("win", "loss", "draw")


@dataclass
class GameRecord:
    finished_at: str       # ISO timestamp (local time)
    result: str            # "win" | "loss" | "draw"
    reason: str            # e.g. "checkmate", "stalemate", "resigned"
    player_color: str      # "white" | "black"
    difficulty: str
    opponent: str          # "provider · model"
    moves: int             # full moves played
    duration_seconds: int


@dataclass
class Summary:
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    total_seconds: int = 0
    total_moves: int = 0


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class GameHistory:
    def __init__(self, path: Path = HISTORY_PATH):
        self.path = path
        self.records: list[GameRecord] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.records = [GameRecord(**item) for item in data]
        except (OSError, ValueError, TypeError):
            pass

    def add(self, record: GameRecord) -> None:
        self.records.append(record)
        self._save()

    def clear(self) -> None:
        self.records.clear()
        self._save()

    def summary(self) -> Summary:
        s = Summary(games=len(self.records))
        for r in self.records:
            s.wins += r.result == "win"
            s.losses += r.result == "loss"
            s.draws += r.result == "draw"
            s.total_seconds += r.duration_seconds
            s.total_moves += r.moves
        return s

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(r) for r in self.records], indent=2), encoding="utf-8"
        )
