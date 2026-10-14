"""Dialog for choosing the AI provider, model, API key and endpoint."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from .settings import (
    API_KEY_ENV_VARS, MODEL_SUGGESTIONS, PROVIDER_LABELS, PROVIDERS, Settings,
)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._providers = copy.deepcopy(settings.providers)
        self._current = settings.provider

        self.provider_combo = QComboBox()
        for name in PROVIDERS:
            self.provider_combo.addItem(PROVIDER_LABELS[name], name)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.base_url_edit = QLineEdit()

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("Hint")

        form = QFormLayout()
        form.addRow("AI provider:", self.provider_combo)
        form.addRow("Model:", self.model_combo)
        form.addRow("API key:", self.api_key_edit)
        form.addRow("Base URL:", self.base_url_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.hint)
        layout.addWidget(buttons)

        self.provider_combo.setCurrentIndex(PROVIDERS.index(self._current))
        self._load_fields(self._current)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

    def _on_provider_changed(self) -> None:
        self._store_fields(self._current)
        self._current = self.provider_combo.currentData()
        self._load_fields(self._current)

    def _load_fields(self, provider: str) -> None:
        cfg = self._providers[provider]
        self.model_combo.clear()
        self.model_combo.addItems(MODEL_SUGGESTIONS[provider])
        self.model_combo.setCurrentText(cfg.model)
        self.api_key_edit.setText(cfg.api_key)
        self.base_url_edit.setText(cfg.base_url)

        env_var = API_KEY_ENV_VARS[provider]
        self.api_key_edit.setPlaceholderText(
            f"Leave empty to use the {env_var} environment variable" if env_var
            else "Usually not needed for local servers"
        )
        self.base_url_edit.setEnabled(provider != "anthropic")
        self.base_url_edit.setPlaceholderText(
            "Leave empty for the official API" if provider == "openai" else ""
        )
        hints = {
            "local": "Any OpenAI-compatible server works. Ollama: http://localhost:11434/v1, "
                     "LM Studio: http://localhost:1234/v1. The model must be pulled/loaded first.",
            "openai": "Uses the OpenAI Chat Completions API.",
            "anthropic": "Uses the Anthropic Messages API.",
        }
        self.hint.setText(hints[provider] + "\nAPI keys entered here are stored in plain text in ~/.pychess/settings.json.")

    def _store_fields(self, provider: str) -> None:
        cfg = self._providers[provider]
        cfg.model = self.model_combo.currentText().strip() or cfg.model
        cfg.api_key = self.api_key_edit.text().strip()
        cfg.base_url = self.base_url_edit.text().strip()

    def apply_to(self, settings: Settings) -> None:
        self._store_fields(self._current)
        settings.provider = self._current
        settings.providers = self._providers
