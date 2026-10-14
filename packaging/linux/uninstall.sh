#!/bin/sh
# Remove Checkmate AI. Your settings and game history in ~/.pychess are kept.
set -e
rm -rf "$HOME/.local/share/checkmate-ai"
rm -f "$HOME/.local/share/applications/checkmate-ai.desktop"
echo "Checkmate AI removed. (Settings and history remain in ~/.pychess)"
