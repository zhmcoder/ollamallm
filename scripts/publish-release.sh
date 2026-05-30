#!/usr/bin/env bash
# Publish GitHub Release v0.1.0 with tarball asset.
# Usage: GITHUB_TOKEN=ghp_xxx ./scripts/publish-release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c "import pathlib,re; t=pathlib.Path('$ROOT/pyproject.toml').read_text(); print(re.search(r'^version\s*=\s*\"([^\"]+)\"', t, re.M).group(1))")"
TAG="v${VERSION}"
ARCHIVE="ollamallm-${VERSION}.tar.gz"
REPO="zhmcoder/ollamallm"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "错误: 请设置 GITHUB_TOKEN 环境变量"
  echo "  GITHUB_TOKEN=ghp_xxx ./scripts/publish-release.sh"
  exit 1
fi

cd "$ROOT"
"$ROOT/scripts/release.sh" | tail -3

DIST="$ROOT/dist/$ARCHIVE"
if [[ ! -f "$DIST" ]]; then
  echo "错误: 找不到 $DIST"
  exit 1
fi

echo "推送代码与 tag..."
git push "https://zhmcoder:${GITHUB_TOKEN}@github.com/${REPO}.git" main
git tag -a "$TAG" -m "Release ${TAG}" 2>/dev/null || git tag -f "$TAG" -m "Release ${TAG}"
git push "https://zhmcoder:${GITHUB_TOKEN}@github.com/${REPO}.git" "$TAG" --force

echo "创建 GitHub Release..."
RELEASE_JSON=$(curl -sS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${REPO}/releases" \
  -d "{\"tag_name\":\"${TAG}\",\"name\":\"${TAG}\",\"body\":\"Initial release: recommend Ollama models for your Mac/GPU hardware.\",\"draft\":false,\"prerelease\":false}")

UPLOAD_URL=$(echo "$RELEASE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('upload_url','').split('{')[0])" 2>/dev/null || true)

if [[ -z "$UPLOAD_URL" ]]; then
  echo "Release 可能已存在，尝试获取..."
  UPLOAD_URL=$(curl -sS \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    "https://api.github.com/repos/${REPO}/releases/tags/${TAG}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('upload_url','').split('{')[0])")
fi

if [[ -z "$UPLOAD_URL" ]]; then
  echo "错误: 无法创建 Release"
  echo "$RELEASE_JSON"
  exit 1
fi

echo "上传 $ARCHIVE ..."
curl -sS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Content-Type: application/gzip" \
  --data-binary @"$DIST" \
  "${UPLOAD_URL}?name=${ARCHIVE}"

echo ""
echo "完成!"
echo "Release: https://github.com/${REPO}/releases/tag/${TAG}"
echo ""
echo "Homebrew 安装:"
echo "  brew tap zhmcoder/ollamallm https://github.com/zhmcoder/ollamallm"
echo "  brew install ollamallm"
