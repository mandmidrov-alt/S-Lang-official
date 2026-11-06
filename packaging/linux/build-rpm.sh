#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
BIN="$ROOT/dist/linux-x86_64/slang"
OUT="$ROOT/dist/packages"
TOP="$ROOT/build/rpmbuild"
[ -x "$BIN" ] || { echo "Build binary first: $BIN" >&2; exit 1; }
rm -rf "$TOP"; mkdir -p "$TOP/BUILD" "$TOP/RPMS" "$TOP/SOURCES" "$TOP/SPECS" "$TOP/SRPMS"
mkdir -p "$TOP/SOURCES/payload/usr/bin"; cp "$BIN" "$TOP/SOURCES/payload/usr/bin/slang"; chmod 755 "$TOP/SOURCES/payload/usr/bin/slang"
cat > "$TOP/SPECS/slang.spec" <<SPEC
Name: slang-language
Version: 1.0
Release: 1
Summary: S-Lang programming language runtime
License: MIT
BuildArch: x86_64
%description
S-Lang high-level programming language runtime.
%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/bin
cp %{_sourcedir}/payload/usr/bin/slang %{buildroot}/usr/bin/slang
%files
/usr/bin/slang
SPEC
rpmbuild --define "_topdir $TOP" -bb "$TOP/SPECS/slang.spec"
mkdir -p "$OUT"; cp "$TOP"/RPMS/x86_64/*.rpm "$OUT/S-Lang-1.0-linux-x86_64.rpm"
echo "$OUT/S-Lang-1.0-linux-x86_64.rpm"
