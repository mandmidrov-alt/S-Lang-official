#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
ARCH=${S_LANG_DEB_ARCH:-amd64}
BIN="$ROOT/dist/linux-x86_64/slang"
OUT="$ROOT/dist/packages"
PKGROOT="$ROOT/build/debroot"
[ -x "$BIN" ] || { echo "Build binary first: $BIN" >&2; exit 1; }
rm -rf "$PKGROOT" "$OUT"
mkdir -p "$PKGROOT/DEBIAN" "$PKGROOT/usr/bin"
cp "$BIN" "$PKGROOT/usr/bin/slang"
chmod 755 "$PKGROOT/usr/bin/slang"
cat > "$PKGROOT/DEBIAN/control" <<CTL
Package: slang-language
Version: 1.0
Section: devel
Priority: optional
Architecture: $ARCH
Maintainer: S-Lang Project
Description: S-Lang programming language runtime
 High-level task-oriented programming language.
CTL
mkdir -p "$OUT"
dpkg-deb --build "$PKGROOT" "$OUT/S-Lang-1.0-linux-$ARCH.deb"
echo "$OUT/S-Lang-1.0-linux-$ARCH.deb"
