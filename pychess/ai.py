"""LLM-backed chess opponent supporting local (OpenAI-compatible), OpenAI and Anthropic."""

from __future__ import annotations

import random
import re

import chess

from .settings import ProviderConfig

MAX_ATTEMPTS = 3

SYSTEM_PROMPT = (
    "You are a chess engine playing a game against a human. "
    "You will receive the current position and the list of legal moves. "
    "Pick exactly one move from the legal move list. "
    "End your reply with a final line of the form `MOVE: <uci>`, for example `MOVE: e7e5`."
)

STYLE = {
    "beginner": (
        "Your opponent is a beginner. Play like a friendly casual player around 800 Elo: "
        "make reasonable but simple moves and occasionally miss tactics."
    ),
    "intermediate": (
        "Your opponent is an intermediate club player. Play solid chess around 1500 Elo: "
        "develop pieces, look for basic tactics and avoid blunders."
    ),
    "advanced": (
        "Your opponent is a strong player. Play the strongest move you can find, "
        "around 2000 Elo: avoid blunders, punish mistakes and watch your opponent's threats. "
        "Keep any reasoning brief."
    ),
}

# Reasoning effort per difficulty. The difficulty prompt (STYLE) sets playing strength;
# higher effort made advanced mode far too slow for little gain in move quality.
EFFORT = {"beginner": "low", "intermediate": "low", "advanced": "low"}
# Each step up (minimal -> low -> medium) can multiply response time on gpt-5 models.
OPENAI_REASONING_EFFORT = {"beginner": "minimal", "intermediate": "minimal", "advanced": "minimal"}
_OPENAI_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")
_EFFORT_MODEL_PREFIXES = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-4-6",
)
# Models that accept the server-side refusal fallback (`fallbacks: "default"`).
_FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")

_MOVE_LINE = re.compile(r"MOVE:\s*`?([a-h][1-8][a-h][1-8][qrbn]?)", re.IGNORECASE)
_UCI_TOKEN = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")


class AIError(Exception):
    """A user-presentable failure talking to the AI provider."""


def describe_position(board: chess.Board) -> str:
    replay = board.root()
    sans = []
    for move in board.move_stack:
        sans.append(replay.san(move))
        replay.push(move)
    history = " ".join(
        f"{i // 2 + 1}. {san}" if i % 2 == 0 else san for i, san in enumerate(sans)
    ) or "(no moves yet)"
    side = "White" if board.turn == chess.WHITE else "Black"
    legal = " ".join(m.uci() for m in board.legal_moves)
    return (
        f"You play {side}.\n"
        f"Moves so far: {history}\n"
        f"Current position (FEN): {board.fen()}\n"
        f"Board (uppercase = White, lowercase = Black):\n{board}\n"
        f"Legal moves (UCI): {legal}"
    )


def parse_move(text: str, board: chess.Board) -> chess.Move | None:
    candidates = _MOVE_LINE.findall(text)[::-1] + _UCI_TOKEN.findall(text)[::-1]
    for token in candidates:
        try:
            move = chess.Move.from_uci(token.lower())
        except ValueError:
            continue
        if move in board.legal_moves:
            return move
    # Some models answer in SAN despite instructions ("MOVE: Nf3").
    match = re.search(r"MOVE:\s*`?([^\s`]+)", text, re.IGNORECASE)
    if match:
        try:
            return board.parse_san(match.group(1))
        except ValueError:
            pass
    return None


class ChessAI:
    def __init__(self, provider: str, config: ProviderConfig, difficulty: str):
        self.provider = provider
        self.config = config
        self.difficulty = difficulty

    @property
    def label(self) -> str:
        return f"{self.provider} · {self.config.model}"

    def choose_move(self, board: chess.Board) -> tuple[chess.Move, str | None]:
        """Return the AI's move and an optional note to show the user."""
        prompt = f"{STYLE[self.difficulty]}\n\n{describe_position(board)}"
        feedback = ""
        for _ in range(MAX_ATTEMPTS):
            reply = self._complete(prompt + feedback)
            move = parse_move(reply, board)
            if move is not None:
                return move, None
            last = reply.strip().splitlines()[-1] if reply.strip() else "(empty reply)"
            feedback = (
                f"\n\nYour previous answer `{last[:80]}` was not a legal move. "
                "Choose one move from the legal move list and finish with `MOVE: <uci>`."
            )
        move = random.choice(list(board.legal_moves))
        return move, "The AI didn't produce a legal move, so a random legal move was played."

    def _complete(self, prompt: str) -> str:
        if self.provider == "anthropic":
            return self._complete_anthropic(prompt)
        return self._complete_openai(prompt)

    def _complete_anthropic(self, prompt: str) -> str:
        import anthropic

        model = self.config.model
        client = anthropic.Anthropic(api_key=self.config.api_key or None, timeout=180.0)
        kwargs = dict(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        if model.startswith(_EFFORT_MODEL_PREFIXES):
            kwargs["output_config"] = {"effort": EFFORT[self.difficulty]}
        try:
            if model in _FALLBACK_MODELS:
                response = client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                response = client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            raise AIError("Anthropic rejected the API key. Check Settings.") from None
        except anthropic.NotFoundError:
            raise AIError(f"Anthropic model '{model}' was not found. Check Settings.") from None
        except anthropic.APIStatusError as e:
            raise AIError(f"Anthropic error ({e.status_code}): {e.message}") from None
        except anthropic.APIConnectionError:
            raise AIError("Could not reach the Anthropic API. Check your connection.") from None
        except anthropic.AnthropicError as e:
            raise AIError(f"Anthropic error: {e}") from None

        if response.stop_reason == "refusal":
            raise AIError("The Anthropic model declined to answer.")
        return "".join(block.text for block in response.content if block.type == "text")

    def _complete_openai(self, prompt: str) -> str:
        import openai

        api_key = self.config.api_key or None
        if self.provider == "local":
            api_key = api_key or "local"  # local servers usually ignore the key
        name = "Local model server" if self.provider == "local" else "OpenAI"
        kwargs = dict(
            model=self.config.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        if self.provider == "openai" and self.config.model.startswith(_OPENAI_REASONING_PREFIXES):
            kwargs["reasoning_effort"] = OPENAI_REASONING_EFFORT[self.difficulty]
        try:
            client = openai.OpenAI(
                api_key=api_key, base_url=self.config.base_url or None, timeout=180.0
            )
            try:
                response = client.chat.completions.create(**kwargs)
            except openai.BadRequestError as e:
                # Not every reasoning model accepts every effort level (e.g. "minimal").
                if "reasoning_effort" not in kwargs or "reasoning" not in str(e.message).lower():
                    raise
                kwargs["reasoning_effort"] = "low"
                response = client.chat.completions.create(**kwargs)
        except openai.AuthenticationError:
            raise AIError(f"{name} rejected the API key. Check Settings.") from None
        except openai.NotFoundError:
            raise AIError(f"{name}: model '{self.config.model}' was not found.") from None
        except openai.APIStatusError as e:
            raise AIError(f"{name} error ({e.status_code}): {e.message}") from None
        except openai.APIConnectionError:
            where = self.config.base_url or "the OpenAI API"
            raise AIError(f"Could not reach {where}. Is the server running?") from None
        except openai.OpenAIError as e:
            raise AIError(f"{name} error: {e}") from None

        return response.choices[0].message.content or ""
