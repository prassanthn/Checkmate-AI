"""Build a standalone Checkmate AI package for the current OS with PyInstaller.

    uv run python scripts/build.py

PyInstaller cannot cross-compile, so run this on each target OS (CI does this via
.github/workflows/build.yml). Output goes to dist/:

    Windows  CheckmateAI-windows-<arch>.zip   (folder with "Checkmate AI.exe")
    macOS    CheckmateAI-macos-<arch>.zip     ("Checkmate AI.app")
    Linux    CheckmateAI-linux-<arch>.tar.gz  (also the ChromeOS build; run ./install.sh)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
PACKAGING = ROOT / "packaging"
APP_NAME = "Checkmate AI"
LINUX_NAME = "checkmate-ai"


def arch() -> str:
    machine = platform.machine().lower()
    return {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)


def make_icon() -> Path:
    """Render the knight piece (bundled with python-chess) to a 512px PNG."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import chess
    import chess.svg
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    _app = QGuiApplication.instance() or QGuiApplication([])
    image = QImage(512, 512, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    svg = chess.svg.piece(chess.Piece.from_symbol("N")).encode()
    QSvgRenderer(QByteArray(svg)).render(painter)
    painter.end()
    BUILD.mkdir(exist_ok=True)
    path = BUILD / "icon.png"
    image.save(str(path))
    return path


def run_pyinstaller(name: str, icon: Path) -> None:
    args = [
        sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
        "--name", name,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(icon),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        "--exclude-module", "tkinter",
    ]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "dev.checkmateai.app"]
    subprocess.run(args, check=True, cwd=ROOT)


def package_windows() -> Path:
    folder = DIST / APP_NAME
    out = DIST / f"CheckmateAI-windows-{arch()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in folder.rglob("*"):
            zf.write(file, Path(APP_NAME) / file.relative_to(folder))
    return out


def package_macos() -> Path:
    out = DIST / f"CheckmateAI-macos-{arch()}.zip"
    # ditto keeps the symlinks and metadata an .app bundle relies on.
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(DIST / f"{APP_NAME}.app"), str(out)], check=True)
    return out


def package_linux(icon: Path) -> Path:
    folder = DIST / LINUX_NAME
    shutil.copy(icon, folder / "checkmate-ai.png")
    shutil.copy(PACKAGING / "linux" / "checkmate-ai.desktop.in", folder)
    for script in ("install.sh", "uninstall.sh"):
        target = folder / script
        shutil.copy(PACKAGING / "linux" / script, target)
        target.chmod(0o755)
    out = DIST / f"CheckmateAI-linux-{arch()}.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.add(folder, arcname=LINUX_NAME)
    return out


def main() -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    icon = make_icon()
    if sys.platform == "win32":
        run_pyinstaller(APP_NAME, icon)
        out = package_windows()
    elif sys.platform == "darwin":
        run_pyinstaller(APP_NAME, icon)
        out = package_macos()
    else:
        run_pyinstaller(LINUX_NAME, icon)
        out = package_linux(icon)
    print(f"\nBuilt {out.relative_to(ROOT)} ({out.stat().st_size / 1_048_576:.0f} MB)")


if __name__ == "__main__":
    main()
