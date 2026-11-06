#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) TARGET=macos-x64 ;;
  arm64|aarch64) TARGET=macos-arm64 ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 1 ;;
esac
BIN="$ROOT/dist/$TARGET/slang"
OUT="$ROOT/dist/packages"
ROOTPKG="$ROOT/build/pkgroot"
[ -x "$BIN" ] || { echo "Build binary first: $BIN" >&2; exit 1; }
rm -rf "$ROOTPKG"
mkdir -p "$ROOTPKG/usr/local/bin" "$OUT"
cp "$BIN" "$ROOTPKG/usr/local/bin/slang"
chmod 755 "$ROOTPKG/usr/local/bin/slang"
pkgbuild --root "$ROOTPKG" --identifier org.slang.language --version 1.0 --install-location / "$OUT/S-Lang-1.0-macos-$([ "$ARCH" = x86_64 ] && echo x64 || echo arm64).pkg"
echo "$OUT/S-Lang-1.0-macos-$([ "$ARCH" = x86_64 ] && echo x64 || echo arm64).pkg"
