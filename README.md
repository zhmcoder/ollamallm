# ollamallm

根据 Mac 或显卡硬件，推荐可安装的 Ollama 模型。

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

- [产品需求文档](docs/PRD.md)
- [Homebrew 安装说明](docs/BREW.md)
