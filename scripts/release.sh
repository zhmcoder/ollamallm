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

# Reproducible tarball (stable SHA256 for Homebrew; macOS tar lacks --mtime)
python3 - "$ROOT" "$DIST/$ARCHIVE" <<'PY'
import gzip
import io
import sys
import tarfile
from pathlib import Path

root = Path(sys.argv[1])
archive = Path(sys.argv[2])
fixed_mtime = 0

def add_dir(tar, base: Path, rel: Path = Path(".")):
    for path in sorted(base.rglob("*")):
        if path.is_dir():
            continue
        arcname = str(rel / path.relative_to(base))
        if arcname.startswith(".git") or "/.git" in arcname:
            continue
        if arcname.startswith("dist") or "/dist/" in arcname:
            continue
        if "__pycache__" in arcname or arcname.endswith(".egg-info"):
            continue
        if ".cursor" in arcname.split("/"):
            continue
        info = tar.gettarinfo(str(path), arcname=arcname)
        info.mtime = fixed_mtime
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        with open(path, "rb") as f:
            tar.addfile(info, f)

includes = ["pyproject.toml", "README.md", "LICENSE", "ollamallm", "docs"]
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
    for name in includes:
        p = root / name
        if p.is_dir():
            add_dir(tar, p, Path(name))
        elif p.exists():
            info = tar.gettarinfo(str(p), arcname=name)
            info.mtime = fixed_mtime
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            with open(p, "rb") as f:
                tar.addfile(info, f)

with gzip.GzipFile(filename=str(archive), mode="wb", mtime=0) as gz:
    gz.write(buf.getvalue())
PY

SHA="$(shasum -a 256 "$DIST/$ARCHIVE" | awk '{print $1}')"

echo "Created: $DIST/$ARCHIVE"
echo "SHA256:  $SHA"
echo ""
echo "Update Formula/ollamallm.rb sha256 to:"
echo "  sha256 \"$SHA\""
echo ""
echo "GitHub release asset URL (after upload):"
echo "  https://github.com/zhmcoder/ollamallm/releases/download/v${VERSION}/${ARCHIVE}"
