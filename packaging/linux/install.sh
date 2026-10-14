#!/bin/sh
# Install Checkmate AI for the current user (Linux desktops and ChromeOS Linux).
# Adds a launcher entry, so on a Chromebook the app shows up under "Linux apps".
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET="$HOME/.local/share/checkmate-ai"
APPS="$HOME/.local/share/applications"

# Qt needs a few system libraries that minimal installs (like ChromeOS Linux) lack.
if command -v apt-get >/dev/null 2>&1; then
    echo "Installing required system libraries (may ask for your password)..."
    sudo apt-get install -y --no-install-recommends \
        libxcb-cursor0 libxkbcommon-x11-0 libegl1 libgl1 libfontconfig1 libdbus-1-3 \
        || echo "Warning: could not install system libraries; the app may not start."
fi

if [ "$SRC" != "$TARGET" ]; then
    rm -rf "$TARGET"
    mkdir -p "$TARGET"
    cp -R "$SRC"/. "$TARGET"/
fi

mkdir -p "$APPS"
sed "s|@DIR@|$TARGET|g" "$TARGET/checkmate-ai.desktop.in" > "$APPS/checkmate-ai.desktop"
chmod +x "$APPS/checkmate-ai.desktop" "$TARGET/checkmate-ai"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true

echo "Checkmate AI installed. Launch it from your app launcher, or run: $TARGET/checkmate-ai"
