#!/usr/bin/env bash
# Build release tarball and print SHA256 for Formula/ollamallm.rb
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c "import pathlib,re; t=pathlib.Path('$ROOT/pyproject.toml').read_text(); print(re.search(r'^version\s*=\s*\"([^\"]+)\"', t, re.M).group(1))")"
DIST="$ROOT/dist"
ARCHIVE="ollamallm-${VERSION}.tar.gz"
FORMULA="$ROOT/Formula/ollamallm.rb"

mkdir -p "$DIST"
rm -f "$DIST/$ARCHIVE"

tar -czf "$DIST/$ARCHIVE" -C "$ROOT" \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '*.egg-info' \
  --exclude '__pycache__' \
  --exclude '.cursor' \
  pyproject.toml README.md LICENSE ollamallm docs Formula

SHA="$(shasum -a 256 "$DIST/$ARCHIVE" | awk '{print $1}')"

echo "Created: $DIST/$ARCHIVE"
echo "SHA256:  $SHA"
echo ""
echo "Update Formula/ollamallm.rb sha256 to:"
echo "  sha256 \"$SHA\""
echo ""
echo "GitHub release asset URL (after upload):"
echo "  https://github.com/zhmcoder/ollamallm/releases/download/v${VERSION}/${ARCHIVE}"
