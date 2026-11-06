#!/bin/sh
set -eu
PREFIX="${HOME}/.local/bin"
SOURCE="$(CDPATH= cd -- "$(dirname "$0")/../../dist/linux-$(uname -m)" && pwd)/slang"
if [ ! -f "$SOURCE" ]; then
  echo "Build slang first: python3 packaging/build-runtime.py" >&2
  exit 1
fi
mkdir -p "$PREFIX"
cp "$SOURCE" "$PREFIX/slang"
chmod +x "$PREFIX/slang"
echo "S-Lang installed to $PREFIX/slang"
echo "Ensure ~/.local/bin is in PATH."
