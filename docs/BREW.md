# Homebrew 安装

## 方式一：Tap 安装（推荐）

本项目已包含 `Formula/ollamallm.rb`，可直接 tap 本仓库：

```bash
brew tap zhmcoder/ollamallm https://github.com/zhmcoder/ollamallm
brew install ollamallm
```

或一条命令：

```bash
brew install zhmcoder/ollamallm/ollamallm
```

> 首次安装需 GitHub Release 已发布 `ollamallm-0.1.0.tar.gz`，见下方「发布新版本」。

## 方式二：本地源码安装（开发/未发布 Release 时）

```bash
git clone https://github.com/zhmcoder/ollamallm.git
cd ollamallm
chmod +x scripts/brew-install-local.sh
./scripts/brew-install-local.sh
```

## 方式三：pip 安装

```bash
pip install git+https://github.com/zhmcoder/ollamallm.git
```

## 发布新版本（维护者）

```bash
# 1. 更新 pyproject.toml 中的 version
# 2. 提交并打 tag
git tag v0.1.0 && git push origin v0.1.0

# 3. 生成 tarball 与 SHA256
./scripts/release.sh

# 4. 将 dist/ollamallm-0.1.0.tar.gz 上传到 GitHub Release
# 5. 更新 Formula/ollamallm.rb 中的 sha256 并推送
```

## 验证

```bash
ollamallm help
ollamallm
```
