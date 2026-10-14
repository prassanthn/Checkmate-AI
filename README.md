# Checkmate AI

A desktop chess app (PySide6, dark theme) where you play against an AI opponent backed by an LLM.

## Features

- Drag and drop pieces, or click a piece and then click a target square.
- Illegal moves are rejected: the piece slides back to its original square and the
  info bar at the bottom explains why (pinned piece, king in check, wrong movement...).
- Three modes:
  - **Beginner**: legal moves for the selected piece are highlighted (dots for quiet
    moves, rings for captures, green tint for the square under the dragged piece).
    The AI plays casually.
  - **Intermediate**: no move hints. The AI plays like a club player.
  - **Advanced**: no move hints. The AI is asked to play its strongest moves (and uses
    more reasoning effort on Anthropic models).
- Configurable AI provider and model (**Settings**):
  - **Local**: any OpenAI-compatible server, e.g. Ollama (`http://localhost:11434/v1`)
    or LM Studio (`http://localhost:1234/v1`)
  - **OpenAI**
  - **Anthropic**
- Undo, resign, play as White or Black, move list, check / checkmate / draw detection.
- Game clock, plus a saved history of every finished game: result (win / loss / draw and
  why), moves, how long it took, mode and opponent. The side panel shows your record and
  **History** (Ctrl+H) shows all games with totals (win rate, total time, total moves).

If the model replies with an illegal move, it is asked again (up to 3 attempts) before a
random legal move is played. Connection or API errors appear in the info bar, and you can
press **Retry AI Move** after fixing the settings.

## Run

```
uv run main.py
```

(or `uv run python -m pychess`)

## Building standalone apps

```
uv run python scripts/build.py
```

builds a self-contained package for the OS you run it on (PyInstaller can't cross-compile):

| Platform | Output (in `dist/`) | How to run |
|---|---|---|
| Windows | `CheckmateAI-windows-x64.zip` | Unzip, run `Checkmate AI.exe` |
| macOS | `CheckmateAI-macos-arm64.zip` | Unzip, right-click `Checkmate AI.app` → Open (the first time; the app isn't signed) |
| Linux / ChromeOS | `CheckmateAI-linux-<arch>.tar.gz` | Extract, run `./install.sh` (adds it to the app launcher) |

To build all platforms, push the repo to GitHub and run the **Build** workflow
(`.github/workflows/build.yml`) from the Actions tab, or push a tag like `v1.0.0` to also
publish a release with all packages attached.

**ChromeOS:** turn on Linux (Settings → Advanced → Developers), then copy the Linux
package into "Linux files" and run `./install.sh` in the Terminal. Intel/AMD Chromebooks
use the `x64` package. ARM Chromebooks use `arm64`, which needs the Linux environment to
be Debian 13 or newer (check with `ldd --version`: glibc 2.39+).

## Configuration

Settings are saved in `~/.pychess/settings.json` and game history in `~/.pychess/history.json`. If you leave the API key empty, the
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` environment variables are used. Keys typed into
the Settings dialog are stored there in plain text.

## License

[MIT](LICENSE)
