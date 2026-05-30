#!/usr/bin/env bash
# Install ollamallm via Homebrew from local source (no GitHub required)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c "import pathlib,re; t=pathlib.Path('$ROOT/pyproject.toml').read_text(); print(re.search(r'^version\s*=\s*\"([^\"]+)\"', t, re.M).group(1))")"
DIST="$ROOT/dist"
ARCHIVE="ollamallm-${VERSION}.tar.gz"
FORMULA_TMP="$(mktemp -t ollamallm-formula.XXXXXX.rb)"

mkdir -p "$DIST"
tar -czf "$DIST/$ARCHIVE" -C "$ROOT" \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '*.egg-info' \
  --exclude '__pycache__' \
  --exclude '.cursor' \
  pyproject.toml README.md LICENSE ollamallm docs

SHA="$(shasum -a 256 "$DIST/$ARCHIVE" | awk '{print $1}')"

cat > "$FORMULA_TMP" <<RUBY
class Ollamallm < Formula
  include Language::Python::Virtualenv

  desc "Recommend Ollama models based on your Mac or GPU hardware"
  homepage "https://github.com/zhmcoder/ollamallm"
  url "file://${DIST}/${ARCHIVE}"
  sha256 "${SHA}"
  license "MIT"
  version "${VERSION}"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("\#{bin}/ollamallm help")
    assert_match "ollamallm", output
  end
end
RUBY

echo "Installing ollamallm ${VERSION} via Homebrew..."
HOMEBREW_NO_AUTO_UPDATE=1 brew install --formula "$FORMULA_TMP"
rm -f "$FORMULA_TMP"

echo ""
echo "Done. Try: ollamallm help"
