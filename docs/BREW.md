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

### 一键发布（推荐）

```bash
# 需要 GitHub Personal Access Token（repo 权限）
GITHUB_TOKEN=ghp_你的token ./scripts/publish-release.sh
```

脚本会自动：打 tarball → 推送 main + tag → 创建 Release → 上传安装包。

### 手动发布

```bash
./scripts/release.sh
git push origin main
git tag v0.1.0 && git push origin v0.1.0
```

然后打开 [GitHub Releases 新建页](https://github.com/zhmcoder/ollamallm/releases/new)：

1. **Choose a tag** → `v0.1.0`
2. **Release title** → `v0.1.0`
3. 上传 `dist/ollamallm-0.1.0.tar.gz`
4. 点击 **Publish release**

### 发布后 Homebrew 安装

```bash
brew tap zhmcoder/ollamallm https://github.com/zhmcoder/ollamallm
brew install ollamallm
```

## 验证

```bash
ollamallm help
ollamallm
```
