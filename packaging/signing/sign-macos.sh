#!/bin/sh
set -eu
: "${MACOS_CERT_P12:?MACOS_CERT_P12 must point to a .p12 certificate}"
: "${MACOS_CERT_PASSWORD:?MACOS_CERT_PASSWORD is required}"
: "${MACOS_SIGN_IDENTITY:?MACOS_SIGN_IDENTITY is required}"

KEYCHAIN="${RUNNER_TEMP:-/tmp}/slang-signing.keychain-db"
KEYCHAIN_PASSWORD="$(uuidgen)"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security import "$MACOS_CERT_P12" -k "$KEYCHAIN" -P "$MACOS_CERT_PASSWORD" -T /usr/bin/productsign -T /usr/bin/security
security set-key-partition-list -S apple-tool:,apple:,productsign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security list-keychains -d user -s "$KEYCHAIN"
security default-keychain -s "$KEYCHAIN"

for unsigned in "$@"; do
  [ -f "$unsigned" ] || { echo "Missing package: $unsigned" >&2; exit 1; }
  signed="${unsigned%.pkg}.signed.pkg"
  productsign --sign "$MACOS_SIGN_IDENTITY" "$unsigned" "$signed"
  pkgutil --check-signature "$signed"
  mv "$signed" "$unsigned"
done

if [ -n "${APPLE_NOTARY_API_KEY_FILE:-}" ] && [ -n "${APPLE_NOTARY_KEY_ID:-}" ] && [ -n "${APPLE_NOTARY_ISSUER_ID:-}" ]; then
  for pkg in "$@"; do
    xcrun notarytool submit "$pkg" \
      --key "$APPLE_NOTARY_API_KEY_FILE" \
      --key-id "$APPLE_NOTARY_KEY_ID" \
      --issuer "$APPLE_NOTARY_ISSUER_ID" \
      --wait
    xcrun stapler staple "$pkg"
    xcrun stapler validate "$pkg"
  done
fi

security delete-keychain "$KEYCHAIN" || true
