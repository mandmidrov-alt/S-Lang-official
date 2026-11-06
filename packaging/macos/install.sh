#!/bin/sh
set -eu
PREFIX="${HOME}/.local/s-lang/1.0"
SOURCE="$(CDPATH= cd -- "$(dirname "$0")/../../dist/macos-$(uname -m)" && pwd)/slang"
if [ ! -f "$SOURCE" ]; then
  echo "Build slang first: python3 packaging/build-runtime.py" >&2
  exit 1
fi
mkdir -p "$PREFIX/bin"
cp "$SOURCE" "$PREFIX/bin/slang"
chmod +x "$PREFIX/bin/slang"
mkdir -p "$HOME/.local/bin"
ln -sf "$PREFIX/bin/slang" "$HOME/.local/bin/slang"
echo "S-Lang installed. Ensure ~/.local/bin is in PATH."
