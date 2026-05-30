# ollamallm

根据 Mac 或显卡硬件，推荐可安装的 Ollama 模型。

**一条命令，零参数** — 自动检测本机或查询指定设备，输出全部可安装的 Ollama 模型及 `ollama pull` 命令。支持 Apple Silicon / Intel Mac 区分、126+ 模型库、在线 catalog 合并。

[功能简介](docs/INTRO.md) · [安装说明](docs/BREW.md) · [需求文档](docs/PRD.md)

## 安装

### Homebrew（推荐）

```bash
# 已发布 Release 后
brew tap zhmcoder/ollamallm https://github.com/zhmcoder/ollamallm
brew install ollamallm
```

本地源码安装（开发阶段）：

```bash
./scripts/brew-install-local.sh
```

### pip

```bash
pip install .
```

## 用法

```bash
ollamallm                         # 查本机
ollamallm M2 Pro 16GB             # 查指定 Mac
ollamallm MacBook Pro 2020 Intel  # 指定 Intel
ollamallm RTX 4090                # 查显卡
ollamallm help                    # 帮助
```

也可不安装，直接运行：

```bash
python -m ollamallm
python -m ollamallm M2 Pro 16GB
```

## 文档

- [项目功能简介](docs/INTRO.md)
- [产品需求文档](docs/PRD.md)
- [Homebrew 安装说明](docs/BREW.md)
