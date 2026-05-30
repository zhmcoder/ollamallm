# ollamallm 项目功能简介

## 是什么

**ollamallm** 是一款命令行工具，帮助你在安装 Ollama 模型之前，快速判断「这台 Mac 或显卡能跑哪些大模型」。

只需一条命令，即可获得按推荐等级排序的模型列表，以及可直接复制的 `ollama pull` 安装命令。

```bash
ollamallm                  # 查本机
ollamallm M2 Pro 16GB      # 查指定设备
```

---

## 解决什么问题

本地运行 LLM 时，最常见的困惑是：

- **不知道能跑多大模型** — 8B、14B、70B 到底能不能装？
- **Mac 和 PC 算法不同** — Apple Silicon 用统一内存，Intel Mac 和 NVIDIA 显卡又是另一套逻辑
- **型号容易搞混** — 同样是 MacBook Pro 2020，可能是 Intel，也可能是 M1
- **模型太多选不过来** — Ollama 库持续更新，手动查对照表很费时间

ollamallm 把这些判断自动化，让你**事前选型、避免反复下载和 OOM**。

---

## 核心功能

### 1. 本机自动检测

无参数运行 `ollamallm`，自动读取当前 Mac 的：

- CPU 架构（Apple Silicon / Intel）
- 芯片型号、内存容量、GPU 信息
- 可用推理内存（扣除系统与 KV Cache 预留）

并输出所有可安装的 Ollama 模型推荐。

### 2. 指定设备查询

支持输入 Mac 或显卡型号，例如：

```bash
ollamallm MacBook Air M1 8GB
ollamallm MacBook Pro 2019
ollamallm MacBook Pro 2020 Intel
ollamallm RTX 4090
```

适合购机前评估、帮他人选型等场景。

### 3. Intel / Apple 芯片智能识别

Mac 推荐必须区分 CPU 类型，因为结果差异很大：

| CPU | 特点 | 推荐策略 |
|-----|------|----------|
| **Apple Silicon** | 统一内存 + Metal GPU 加速 | 按内存推荐 7B～70B |
| **Intel** | 以 CPU 推理为主，速度较慢 | 建议 7B 以下，标注速度警告 |

- 输入 `MacBook Pro 2019` → 自动判定为 Intel
- 输入 `M2 Pro 16GB` → 自动判定为 Apple Silicon
- 输入 `MacBook Pro 2020` 无法确定 → 弹出 **1 / 2** 让你选择，或在型号中加 `Intel` / `M1` 一次说清

### 4. 全量模型库匹配

- 内置 **126+** 主流 Ollama 模型规格
- 在线合并 [ollama.com](https://ollama.com) 官方模型体积数据
- 按 **Q4_K_M** 量化估算内存占用
- 输出**全部**可安装模型，而非只列几个小模型

### 5. 分级推荐

| 等级 | 含义 |
|------|------|
| ⭐ 最佳 | 内存充裕，运行流畅 |
| ✅ 推荐 | 可正常运行 |
| ⚠️ 勉强 | 能加载，长 context 可能 OOM |
| ❌ 不推荐 | 内存不足 |

每条推荐附带：模型体积、预估速度、`ollama pull` 命令。

---

## 设计原则：命令一定要简单

日常只用两条命令，无需记参数：

```bash
ollamallm              # 查本机
ollamallm <型号>       # 查设备，型号直接写在后面
```

---

## 适用人群

- 刚接触 Ollama、不确定能跑什么模型的 Mac 用户
- 准备在 Apple Silicon / Intel Mac 上部署本地 LLM 的开发者
- 拥有 NVIDIA 显卡、想快速评估可运行模型的 PC 用户
- 需要帮他人推荐模型配置的技术支持场景

---

## 安装

```bash
# Homebrew
brew tap zhmcoder/ollamallm https://github.com/zhmcoder/ollamallm
brew install ollamallm

# pip
pip install git+https://github.com/zhmcoder/ollamallm.git
```

---

## 输出示例

```
检测到本机配置
──────────────────────────────────────
设备    : MacBook Pro
CPU 架构: Apple Silicon
芯片    : Apple M3 (10-core GPU)
内存    : 16 GB 统一内存
可用推理: ~9.5 GB

推荐 Ollama 模型
──────────────────────────────────────
⭐ llama3.1:8b          ~4.9 GB   ~32 tok/s   ollama pull llama3.1:8b
⭐ qwen2.5:7b           ~4.4 GB   ~32 tok/s   ollama pull qwen2.5:7b
✅ gemma2:9b            ~6.0 GB   ~32 tok/s   ollama pull gemma2:9b
⚠️ qwen2.5:14b          ~8.7 GB   ~30 tok/s   ollama pull qwen2.5:14b

共 78 个可安装模型
```

---

## 相关链接

- 仓库：https://github.com/zhmcoder/ollamallm
- [产品需求文档](PRD.md)
- [Homebrew 安装说明](BREW.md)
