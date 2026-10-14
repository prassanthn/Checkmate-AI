"""Persistent application settings (AI provider, model, difficulty...)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_PATH = Path.home() / ".pychess" / "settings.json"

PROVIDERS = ("local", "openai", "anthropic")
PROVIDER_LABELS = {
    "local": "Local (OpenAI-compatible: Ollama, LM Studio, ...)",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
}
MODEL_SUGGESTIONS = {
    "local": ["llama3.1", "qwen2.5", "mistral", "gemma2"],
    "openai": ["gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4o"],
    "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
}
DEFAULT_BASE_URLS = {
    "local": "http://localhost:11434/v1",
    "openai": "",
    "anthropic": "",
}
API_KEY_ENV_VARS = {
    "local": None,
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

DIFFICULTIES = ("beginner", "intermediate", "advanced")


@dataclass
class ProviderConfig:
    model: str
    api_key: str = ""
    base_url: str = ""


def _default_providers() -> dict[str, ProviderConfig]:
    return {
        name: ProviderConfig(model=MODEL_SUGGESTIONS[name][0], base_url=DEFAULT_BASE_URLS[name])
        for name in PROVIDERS
    }


@dataclass
class Settings:
    provider: str = "anthropic"
    providers: dict[str, ProviderConfig] = field(default_factory=_default_providers)
    difficulty: str = "beginner"
    player_color: str = "white"

    @property
    def active(self) -> ProviderConfig:
        return self.providers[self.provider]

    @classmethod
    def load(cls) -> Settings:
        settings = cls()
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings

        if data.get("provider") in PROVIDERS:
            settings.provider = data["provider"]
        if data.get("difficulty") in DIFFICULTIES:
            settings.difficulty = data["difficulty"]
        if data.get("player_color") in ("white", "black"):
            settings.player_color = data["player_color"]
        for name, cfg in (data.get("providers") or {}).items():
            if name in PROVIDERS and isinstance(cfg, dict):
                current = settings.providers[name]
                settings.providers[name] = ProviderConfig(
                    model=cfg.get("model") or current.model,
                    api_key=cfg.get("api_key", ""),
                    base_url=cfg.get("base_url", current.base_url),
                )
        return settings

    def save(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
