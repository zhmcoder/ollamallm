# ollamallm 产品需求文档（PRD）

| 字段 | 内容 |
|------|------|
| 产品名称 | ollamallm |
| 版本 | v0.3 Draft |
| 日期 | 2026-05-30 |
| 状态 | 需求分析（含 Intel / Apple CPU 区分、极简 CLI） |

---

## 1. 产品概述

**ollamallm** 是一款命令行工具，帮助用户根据硬件配置快速判断「本机或指定设备能安装并流畅运行哪些 Ollama 模型」。

核心价值：降低本地 LLM 选型门槛——**一条命令、零参数**，即可获得按推荐等级排序的模型列表及安装命令。

### 1.1 核心命令（仅两条）

```bash
ollamallm                    # 本机：自动检测，直接出结果
ollamallm MacBook Pro M3      # 查型号：把型号写在后面即可
```

**就这么简单。** 不需要记参数、不需要子命令、不需要引号（除非 shell 特殊字符）。

| 你想做什么 | 输入 |
|-----------|------|
| 查本机 | `ollamallm` |
| 查 Mac | `ollamallm M2 Pro 16GB` |
| 查 Mac（Intel） | `ollamallm MacBook Pro 2019` 或 `ollamallm MacBook Pro 2020 Intel` |
| 查显卡 | `ollamallm RTX 4090` |

CPU 不确定时（如 `MacBook Pro 2020`），工具会**自动弹出选项让你按 1 或 2 选择**，无需额外参数。

---

## 2. 问题背景

### 2.1 用户痛点

| 痛点 | 描述 |
|------|------|
| 内存/显存估算困难 | Ollama 模型以参数量 + 量化格式命名（如 `llama3.1:8b`），实际占用与 Q4/Q8/FP16 强相关 |
| Mac 与 PC 逻辑不同 | Apple Silicon 使用统一内存，无独立 VRAM；PC 以 GPU 显存为瓶颈 |
| Intel / Apple 芯片混淆 | 同名 Mac 产品线（如 MacBook Pro 2020）可能为 Intel 或 M 系列，推荐结果差异极大 |
| 型号规格分散 | Mac 型号（M2 Pro 18GB vs M2 Pro 32GB）与显卡型号（3060 8GB vs 3060 12GB）差异大 |
| 模型_catalog 变化快 | Ollama 库持续更新，用户难以维护对照表 |

### 2.2 产品机会

- **本地优先**：Ollama 用户以开发者、AI 爱好者为主，CLI 工具契合使用习惯
- **Mac 用户强需求**：统一内存架构下「能跑多大模型」是购买决策与日常使用的核心问题
- **可离线运行**：检测与匹配逻辑可完全本地完成，无需联网（模型 catalog 可内置或可选更新）

---

## 3. 目标与成功指标

### 3.1 产品目标

1. **准确**：推荐结果与业界内存估算误差 ≤ 15%（以 Q4_K_M 为基准）
2. **易用**：零参数即可使用；**日常仅一条命令**，型号直接写在命令后面
3. **可解释**：每条推荐附带内存占用、推荐等级、预估速度及 `ollama pull` 命令
4. **CPU 透明**：输出中明确展示 CPU 架构（Apple Silicon / Intel）；不确定时交互选择，**不要求用户记参数**

### 3.2 成功指标（MVP 后）

| 指标 | 目标 |
|------|------|
| 本机检测成功率 | macOS ≥ 99%，Linux/Windows（有 GPU）≥ 90% |
| 设备型号解析成功率 | Mac 常见型号 ≥ 95%，主流 NVIDIA 显卡 ≥ 90% |
| CPU 架构判定准确率 | 含年份/Model ID 输入 ≥ 98%；仅产品线名称且无年份时正确触发用户选择 |
| 推荐误报率（OOM 风险） | 「推荐运行」等级误报 < 5% |
| 命令响应时间 | < 500ms（不含网络拉取模型） |

---

## 4. 功能分析

### 4.1 功能一：本机自动检测（`ollamallm`）

#### 4.1.1 描述

无参数运行时，自动采集本机硬件信息，计算可用推理内存预算，输出匹配的 Ollama 模型列表。

#### 4.1.2 检测维度

**macOS（优先支持）**

| 检测项 | 采集方式 | 用途 |
|--------|----------|------|
| **CPU 架构** | `sysctl machdep.cpu.brand_string` / Apple → `Apple M*`，Intel → `Intel Core *` | 区分 Apple Silicon / Intel，决定推荐策略 |
| 芯片型号 | `system_profiler SPHardwareDataType` | M1/M2/M3/M4 及 Pro/Max/Ultra；或 Intel 具体型号 |
| 内存容量 | `system_profiler SPHardwareDataType` | 推理内存上限（Apple 统一内存 / Intel 系统内存） |
| GPU | Apple Silicon 规格库 / Intel 集显或独显检测 | 速度预估与是否 GPU 加速 |
| 内存带宽 | 芯片规格库映射 | 速度预估（Intel 显著低于 Apple Silicon） |
| 设备型号 | `MacBookPro18,3` 等 Model Identifier | 展示、校验、规格库反查 |

**Linux / Windows（Phase 2）**

| 检测项 | 采集方式 | 用途 |
|--------|----------|------|
| GPU 型号 | `nvidia-smi` / ROCm | 显存容量 |
| 显存大小 | `nvidia-smi --query-gpu=memory.total` | 推理上限 |
| 系统内存 | `/proc/meminfo` / WMI | CPU offload 场景 |
| 多 GPU | 枚举 GPU 列表 | 求和或分别推荐 |

#### 4.1.3 内存预算算法

```
可用推理内存 = 总内存（或显存）
             - 系统保留（macOS: 4GB，Windows/Linux: 2GB）
             - KV Cache 预留（默认 2GB，对应 4K-8K context）
             - Ollama 运行时开销（~0.5GB）
```

**推荐等级划分**

| 等级 | 条件 | 用户感知 |
|------|------|----------|
| ⭐ 最佳推荐 | 模型 Q4 占用 ≤ 可用内存 × 60% | 流畅，有余量扩展 context |
| ✅ 推荐运行 | 模型 Q4 占用 ≤ 可用内存 × 85% | 可正常运行，context 适中 |
| ⚠️ 勉强可用 | 模型 Q4 占用 ≤ 可用内存 × 100% | 能加载，长 context 易 OOM |
| ❌ 不推荐 | 超出可用内存 | 需量化降级或无法运行 |

#### 4.1.4 输出示例

```
$ ollamallm

检测到本机配置
──────────────────────────────────────
设备    : MacBook Pro 14" (2023)
CPU 架构: Apple Silicon
芯片    : Apple M3 Pro (11-core GPU)
内存    : 18 GB 统一内存
带宽    : 150 GB/s
可用推理: ~11.5 GB（已扣除系统与 KV 预留）

推荐 Ollama 模型
──────────────────────────────────────
⭐ llama3.2:3b          ~1.9 GB   ~45 tok/s   ollama pull llama3.2:3b
⭐ qwen2.5:7b           ~4.4 GB   ~28 tok/s   ollama pull qwen2.5:7b
✅ llama3.1:8b          ~4.9 GB   ~22 tok/s   ollama pull llama3.1:8b
✅ mistral:7b           ~4.0 GB   ~25 tok/s   ollama pull mistral:7b
⚠️ qwen2.5:14b          ~8.7 GB   ~12 tok/s   ollama pull qwen2.5:14b
❌ qwen2.5:32b          ~18.8 GB  —           内存不足

提示: 复制 ollama pull 命令即可安装
```

**Intel Mac 本机检测输出示例：**

```
$ ollamallm

检测到本机配置
──────────────────────────────────────
设备    : MacBook Pro 15" (2019)
CPU 架构: Intel
芯片    : Intel Core i7-9750H (6 核)
内存    : 16 GB
GPU     : AMD Radeon Pro 5300M 4 GB（独显，Ollama 支持有限）
可用推理: ~9 GB（CPU 推理为主，速度显著低于 Apple Silicon）

⚠️  Intel Mac 说明: Ollama 主要使用 CPU 推理，大模型速度较慢，建议 7B 以下模型

推荐 Ollama 模型
──────────────────────────────────────
⭐ llama3.2:1b          ~0.8 GB   ~8 tok/s    ollama pull llama3.2:1b
⭐ qwen2.5:1.5b         ~1.0 GB   ~6 tok/s    ollama pull qwen2.5:1.5b
✅ llama3.2:3b          ~1.9 GB   ~4 tok/s    ollama pull llama3.2:3b
⚠️ llama3.1:8b          ~4.9 GB   ~1 tok/s    可用但极慢
❌ qwen2.5:14b          ~8.7 GB   —           内存/速度均不推荐
```

---

### 4.2 功能二：指定设备型号查询（`ollamallm <device>`）

#### 4.2.1 描述

用户输入 Mac 机型或显卡型号，工具解析为标准化硬件规格，**识别 CPU 架构（Apple Silicon / Intel）**，输出与该配置匹配的模型推荐。

> **核心原则**：Mac 推荐必须基于 CPU 架构分支处理。输出中**必须展示**判定到的 CPU 架构；无法唯一判定时，**暂停推荐并引导用户选择**。

#### 4.2.2 Mac CPU 架构识别

**A. 架构类型**

| CPU 架构 | 标识 | Ollama 推理特点 | 推荐策略 |
|----------|------|----------------|----------|
| **Apple Silicon** | M1 / M2 / M3 / M4 及 Pro/Max/Ultra | 统一内存 + Metal GPU 加速，性能优秀 | 以内存容量为主，可推荐 7B–70B |
| **Intel** | Core i5 / i7 / i9 等 | 以 CPU 推理为主，Metal 对 Intel 集显/老 AMD 独显加速有限 | 仅推荐 ≤7B，标注速度警告 |

**B. 自动判定规则（优先级从高到低）**

```
1. 输入含 M 系列 / Intel / Apple 关键词     → 直接判定
2. 输入含 Apple Model Identifier           → 查 model_id 映射表
3. 输入含「产品线 + 年份/代际」              → 查产品线年份映射表
4. 输入仅含产品线名称（无年份、无芯片）       → 弹出 1/2 菜单让用户选择
```

> **不用 `--cpu` 参数。** 用户通过在型号里加 `Intel`、`M1` 等词即可消歧，例如 `MacBook Pro 2020 Intel`、`MacBook Pro M1 2020`。

**C. 产品线 × 年份 → CPU 架构映射（核心规则）**

| 产品线 | Apple Silicon 起始 | Intel 末代 | 重叠/模糊期 |
|--------|-------------------|-----------|------------|
| MacBook Air | 2020 秋（M1） | 2019 及更早 | 2020 年需确认（Intel 2020 初 / M1 2020 末） |
| MacBook Pro 13" | 2020 秋（M1） | 2020 初（Intel） | **2020 年必须让用户选择** |
| MacBook Pro 14"/16" | 2021 秋（M1 Pro/Max） | — | 仅 Apple Silicon |
| Mac mini | 2020 秋（M1） | 2018（Intel） | 2020 年需确认 |
| iMac 24" | 2021 春（M1） | — | 仅 Apple Silicon |
| iMac 27" | — | 2020（Intel） | 2020 及更早为 Intel |
| Mac Studio | 2022（M1 Max/Ultra） | — | 仅 Apple Silicon |
| Mac Pro | 2023（M2 Ultra） | 2019（Intel） | 2019 Intel / 2023 Apple，需区分 |

**D. Model Identifier 自动映射（示例）**

内置 `mac_model_ids.json`，将 Apple 硬件标识映射到 CPU 架构与默认规格：

| Model ID | 产品 | CPU 架构 | 默认芯片 |
|----------|------|----------|----------|
| MacBookAir8,1 | MacBook Air 2018 | Intel | i5-8210Y |
| MacBookAir9,1 | MacBook Air 2019 | Intel | i5-8210Y |
| MacBookAir10,1 | MacBook Air 2020 | **Apple** | M1 |
| MacBookPro16,1 | MacBook Pro 16" 2019 | Intel | i7-9750H |
| MacBookPro16,2 | MacBook Pro 13" 2020 | Intel | i5-1038NG7 |
| MacBookPro17,1 | MacBook Pro 13" 2020 | **Apple** | M1 |
| MacBookPro18,1 | MacBook Pro 16" 2021 | **Apple** | M1 Pro |
| Macmini8,1 | Mac mini 2018 | Intel | i3/i5/i7 |
| Macmini9,1 | Mac mini 2020 | **Apple** | M1 |
| iMac20,1 | iMac 27" 2020 | Intel | i5/i7/i9 |
| iMac24,1 | iMac 24" 2021 | **Apple** | M1 |

用户输入 `MacBookAir10,1` 或本机检测到该 ID 时，自动判定为 Apple Silicon M1，无需用户选择。

**E. 不确定时的用户选择流程**

当输入无法唯一确定 CPU 架构时（如 `MacBook Pro 2020`、`MacBook Air`），工具**不直接输出推荐**，而是：

```
$ ollamallm MacBook Pro 2020

无法唯一确定 CPU，请选一项：
  1  Apple 芯片 (M1)
  2  Intel 芯片

> 1

（继续输出推荐…）

也可一次说清，例如：
  ollamallm MacBook Pro 2020 Intel
  ollamallm MacBook Pro M1 2020
```

**交互规则：**

| 场景 | 行为 |
|------|------|
| 终端 | 显示 1/2 菜单，按数字继续 |
| 非交互（脚本） | 提示补全型号后重试，例如 `ollamallm MacBook Pro 2020 Intel` |

#### 4.2.3 输入类型与解析策略

**A. Mac 相关输入**

| 输入示例 | CPU 判定 | 解析结果 |
|----------|----------|----------|
| `M2 Pro 16GB` | Apple（显式） | M2 Pro，16GB 统一内存 |
| `MacBook Pro M3 18GB` | Apple（显式） | M3 Pro，18GB |
| `MacBook Air M1 8GB` | Apple（显式） | M1，8GB |
| `MacBook Pro 2019` | Intel（年份规则） | i7/i9，需补充内存 |
| `MacBook Pro 2020` | **不确定** | 触发用户选择 |
| `MacBook Pro 2020 Intel` | Intel（显式） | i5/i7，13" |
| `MacBook Pro 2021 14"` | Apple（产品线规则） | M1 Pro/Max |
| `Mac mini 2018` | Intel（年份规则） | i3/i5/i7 |
| `Mac mini M4 16GB` | Apple（显式） | M4，16GB |
| `MacBookAir10,1` | Apple（Model ID） | M1 MacBook Air |

解析流程：

```
用户输入 → 文本规范化
         → CPU 架构判定（4.2.2 规则链）
         → 若不确定：终端按 1/2 选择；或在型号中加 Intel / M1
         → 芯片识别（Apple: M 系列；Intel: Core 代数）
         → 内存容量提取（正则: \d+\s*GB）
         → 规格库查表补全带宽/GPU/独显信息
         → 若内存缺失：使用该配置最常见容量或提示用户补充
         → 输出时首行展示 CPU 架构
```

**B. 显卡相关输入**

| 输入示例 | 解析结果 |
|----------|----------|
| `RTX 4090` | 24GB VRAM，CUDA |
| `RTX 3060 12GB` | 12GB VRAM（区分 8GB/12GB 变体） |
| `RTX 4060 Ti 16GB` | 16GB VRAM |
| `RX 7900 XTX` | 24GB VRAM，ROCm |
| `GTX 1660 Super` | 6GB VRAM |

**C. 模糊匹配**

- 大小写不敏感
- 支持别名：`5090` → `RTX 5090`，`MBP M2` → `MacBook Pro M2`，`MBA 2020` → `MacBook Air 2020`
- 无法唯一确定 CPU 时：触发 4.2.2 用户选择流程
- 无法唯一确定内存时：列出候选并标注「请指定内存容量」

#### 4.2.4 Mac 规格库（核心数据）

**Apple Silicon 芯片 × 内存：**

| 芯片 | 典型内存选项 | 带宽 (GB/s) | 适合模型规模 (Q4) |
|------|-------------|-------------|-------------------|
| M1 | 8, 16 GB | 68 | 8GB→3B，16GB→7B |
| M1 Pro | 16, 32 GB | 200 | 16GB→7-8B，32GB→14B |
| M1 Max | 32, 64 GB | 400 | 32GB→14-32B，64GB→32-70B |
| M1 Ultra | 64, 128 GB | 800 | 64GB→32-70B，128GB→70B+ |
| M2 | 8, 16, 24 GB | 100 | 同 M1 略优 |
| M2 Pro | 16, 32 GB | 200 | 16GB→7-8B，32GB→14-32B |
| M2 Max | 32, 96 GB | 400 | 96GB→70B |
| M3 | 8, 16, 24 GB | 100 | 同 M2 |
| M3 Pro | 18, 36 GB | 150 | 18GB→8B，36GB→27-32B |
| M3 Max | 36, 128 GB | 300-400 | 128GB→70B |
| M4 | 16, 32 GB | 120 | 16GB→8B，32GB→14B |
| M4 Pro | 24, 48, 64 GB | 273 | 48GB→32B |
| M4 Max | 36, 128 GB | 546 | 128GB→70B+ |

**Intel Mac 芯片 × 内存（节选）：**

| 芯片 | 典型内存 | GPU | 适合模型 (Q4, CPU 推理) | 速度预期 |
|------|----------|-----|------------------------|----------|
| i5-8210Y (Air 2018/19) | 8, 16 GB | Intel UHD 617 | 8GB→1B，16GB→3B | 极慢 |
| i5-8257U (Air 2020 Intel) | 8, 16 GB | Intel Iris Plus | 8GB→1.5B，16GB→3B | 极慢 |
| i7-9750H (MBP 2019) | 16, 32 GB | 集显 + 可选 AMD 4GB | 16GB→3-7B | 慢 |
| i9-9980HK (MBP 2019) | 16, 32, 64 GB | 集显 + 可选 AMD 4-8GB | 32GB→7B | 慢 |
| i5/i7/i9 (iMac 27" 2020) | 8–128 GB | Radeon Pro 5300–5700 XT | 依内存，CPU 为主 | 慢 |

> Intel Mac 即使配备 AMD 独显，Ollama 对 macOS 上 AMD GPU 加速支持有限，**推荐逻辑仍以 CPU + 系统内存为准**，独显信息仅作输出展示。

#### 4.2.5 输出规范（含 CPU 架构）

**所有 Mac 推荐输出必须包含 `CPU 架构` 字段**，位置在「设备」之后、「芯片」之前：

```
设备    : ...
CPU 架构: Apple Silicon | Intel          ← 必填
芯片    : ...
```

若 CPU 架构由 Model ID / 年份规则**推断**而非用户显式指定，附加置信度提示：

```
CPU 架构: Intel（根据「MacBook Pro 2019」自动判定；若不对，请在型号中加 Intel 或 M1 重试）
```

#### 4.2.6 输出示例

```
$ ollamallm "MacBook Air M1 8GB"

设备规格（来自型号库）
──────────────────────────────────────
设备    : MacBook Air (M1, 2020)
CPU 架构: Apple Silicon
芯片    : Apple M1 (7-core GPU)
内存    : 8 GB 统一内存
带宽    : 68 GB/s
可用推理: ~1.5 GB

推荐 Ollama 模型
──────────────────────────────────────
⭐ llama3.2:1b          ~0.8 GB   ~80 tok/s
⭐ qwen2.5:1.5b         ~1.0 GB   ~70 tok/s
⭐ gemma2:2b            ~1.5 GB   ~55 tok/s
✅ llama3.2:3b          ~1.9 GB   ~35 tok/s
❌ llama3.1:8b          ~4.9 GB   内存不足

$ ollamallm "MacBook Pro 2019 16GB"

设备规格（来自型号库）
──────────────────────────────────────
设备    : MacBook Pro 15"/16" (2019)
CPU 架构: Intel（根据「MacBook Pro 2019」自动判定；若不对，请在型号中加 Intel 或 M1 重试）
芯片    : Intel Core i7-9750H
内存    : 16 GB
GPU     : Intel UHD 630 + AMD Radeon Pro 555X 4 GB
可用推理: ~9 GB（CPU 推理为主）

⚠️  Intel Mac 说明: 推荐使用 7B 以下模型，推理速度显著低于 Apple Silicon

推荐 Ollama 模型
──────────────────────────────────────
⭐ llama3.2:1b          ~0.8 GB   ~8 tok/s
⭐ qwen2.5:1.5b         ~1.0 GB   ~6 tok/s
✅ llama3.2:3b          ~1.9 GB   ~4 tok/s
⚠️ llama3.1:8b          ~4.9 GB   ~1 tok/s
❌ qwen2.5:14b          ~8.7 GB   不推荐
```

$ ollamallm "RTX 4090 24GB"

设备规格（来自型号库）
──────────────────────────────────────
显卡    : NVIDIA GeForce RTX 4090
显存    : 24 GB GDDR6X
可用推理: ~19.5 GB

推荐 Ollama 模型
──────────────────────────────────────
⭐ llama3.1:8b          ~4.9 GB   ~95 tok/s
⭐ qwen2.5:14b          ~8.7 GB   ~55 tok/s
✅ qwen2.5:32b          ~18.8 GB  ~28 tok/s
✅ codellama:34b        ~20 GB    ~25 tok/s
⚠️ llama3.1:70b         ~40 GB    需 CPU offload / 多卡
```

---

## 5. 功能对比与关系

```
                    ┌─────────────────────┐
                    │   ollamallm CLI     │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     ┌────────▼────────┐              ┌─────────▼─────────┐
     │  功能 1: 无参数   │              │ 功能 2: 设备参数   │
     │  本机硬件检测     │              │ 型号解析           │
     └────────┬────────┘              └─────────┬─────────┘
              │                                 │
              └────────────────┬────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Mac CPU 架构判定    │
                    │  (Apple / Intel)     │
                    │  不确定 → 用户选择   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  硬件规格标准化      │
                    │  (HardwareProfile)   │
                    │  含 cpu_family 字段  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  模型匹配引擎        │
                    │  (ModelMatcher)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  分级推荐 + 输出     │
                    └─────────────────────┘
```

| 维度 | 功能 1（本机检测） | 功能 2（型号查询） |
|------|-------------------|-------------------|
| 输入 | 无 | 设备型号字符串 |
| 数据来源 | 系统 API 实时采集 | 内置规格库 |
| CPU 判定 | `brand_string` / Model ID 自动识别 | 年份规则 + Model ID + 用户选择 |
| 典型场景 | 「我这台电脑能跑什么？」 | 「买之前/帮别人选型」 |
| 精确度 | 高（真实硬件） | 依赖规格库；CPU 不确定时需用户确认 |
| 优先级 | P0 MVP | P0 MVP |

---

## 6. 模型匹配引擎设计

### 6.1 模型 Catalog 结构

内置 JSON/YAML 模型库，每条记录：

```yaml
- name: llama3.1
  tag: "8b"
  params_b: 8.03
  size_q4_gb: 4.9
  size_q8_gb: 8.5
  size_fp16_gb: 16.1
  type: dense          # dense | moe
  active_params_b: 8.03  # MoE 填 active params
  min_memory_gb: 6.0   # 官方/实测最低
  tags: [general, chat]
  speed_profile:
    m1_8gb: 15
    m4_max_48gb: 62
    rtx4090: 95
```

### 6.2 匹配规则

1. **CPU 架构分支**（Mac 优先）：
   - **Apple Silicon**：按统一内存匹配，速度参考带宽 × GPU 核心
   - **Intel**：按系统内存匹配，**上限封顶 7B**（⭐/✅ 仅 ≤3B），速度参考 CPU 核心数，整体 ×0.1–0.2 系数
2. **默认量化**：Q4_K_M（与 Ollama 默认一致）
3. **MoE 模型**：以实际加载显存（非总参数量）为准；Intel Mac 默认不推荐 MoE
4. **Vision 模型**：额外 +1GB 视觉编码器开销
5. **排序**：先按推荐等级，再按参数量，同等级按预估速度降序
6. **默认展示**：仅显示 ⭐/✅/⚠️ 模型，❌ 折叠或最多列 3 条（保持输出简洁）

### 6.3 速度预估

速度不做精确承诺，采用 **区间档位**：

| 档位 | tok/s 范围 | 标签 |
|------|-----------|------|
| 极快 | ≥ 60 | 适合实时对话 |
| 快 | 30-60 | 流畅 |
| 中等 | 15-30 | 可用 |
| 慢 | 5-15 | 大模型/内存紧张 |
| 很慢 | < 5 | 可用但不建议交互 |

预估公式（简化）：

```
tokens_per_sec ≈ memory_bandwidth_GBs × utilization / bytes_per_token
utilization: Apple Silicon ~0.3-0.5, NVIDIA ~0.5-0.8（随模型大小下降）
Intel Mac CPU: ~1-10 tok/s（1-3B），~0.5-2 tok/s（7-8B），标注「CPU 推理」
```

---

## 7. 命令行接口设计

> **设计原则：命令一定要简单。** 90% 用户只用 `ollamallm` 和 `ollamallm <型号>`，其余能力默认隐藏或自动处理。

### 7.1 日常用法（全部）

```bash
ollamallm                         # 查本机
ollamallm M2 Pro 16GB             # 查指定型号
ollamallm MacBook Pro 2019        # 查 Intel Mac（自动识别）
ollamallm MacBook Pro 2020        # CPU 不确定 → 按 1 或 2
ollamallm MacBook Pro 2020 Intel  # 一次说清，跳过选择
ollamallm RTX 4090                # 查显卡
ollamallm help                    # 查看示例（不是子命令树）
```

**输入约定：**

- 型号直接跟在命令后面，**空格分隔**，多数情况**不需要引号**
- 需要引号的情况：shell 含 `$`、`*` 等特殊字符时
- CPU 消歧：在型号中加 `Intel`、`M1`、`Apple` 等词，**不用记参数**
- 内存：在型号中加 `16GB`、`8G` 即可

### 7.2 不做的事（刻意简化）

| 不做 | 原因 | 替代方案 |
|------|------|----------|
| 子命令（`list-devices`、`explain` 等） | 增加记忆负担 | 错误时输出示例；硬件信息已在结果里展示 |
| 日常暴露 `--cpu`、`--quant`、`--tier` | 参数过多 | 型号自然语言；默认 Q4 量化 |
| 安装时要求配置 | 开箱即用 | 内置 catalog，随版本更新 |
| 复杂 help 树 | 像 git 一样难学 | `ollamallm help` 一页示例搞定 |

### 7.3 高级用法（Phase 2，普通用户可忽略）

仅脚本/CI 场景需要，**不出现在主 help 首页**：

```bash
ollamallm M2 --json               # JSON 输出
OLLAMALLM_JSON=1 ollamallm        # 环境变量等价方式
```

### 7.4 JSON 输出结构

```json
{
  "hardware": {
    "source": "local",
    "platform": "darwin",
    "device": "MacBook Pro 15\" (2019)",
    "cpu_family": "intel",
    "cpu_family_label": "Intel",
    "cpu_confidence": "inferred",
    "cpu_inference_note": "根据「MacBook Pro 2019」自动判定",
    "chip": "Intel Core i7-9750H",
    "memory_gb": 16,
    "memory_type": "system",
    "gpu": "AMD Radeon Pro 555X 4 GB",
    "available_inference_gb": 9.0
  },
  "recommendations": [
    {
      "model": "llama3.2:3b",
      "size_gb": 1.9,
      "quant": "q4_K_M",
      "tier": "ok",
      "speed_tok_s": 4,
      "speed_label": "慢（CPU 推理）",
      "pull_command": "ollama pull llama3.2:3b"
    }
  ]
}
```

**CPU 架构不确定时的 JSON 响应：**

```json
{
  "error": "cpu_ambiguous",
  "message": "无法唯一确定 CPU 架构",
  "input": "MacBook Pro 2020",
  "candidates": [
    { "id": 1, "cpu_family": "apple", "label": "Apple Silicon (M1, 2020 末)" },
    { "id": 2, "cpu_family": "intel", "label": "Intel (i5/i7, 2020 初)" }
  ],
  "hint": "请补全型号，例如: ollamallm MacBook Pro 2020 Intel"
}
```

### 7.5 help 输出示例

```
$ ollamallm help

ollamallm — 根据硬件推荐可安装的 Ollama 模型

用法:
  ollamallm                  查本机
  ollamallm <型号>           查指定设备

示例:
  ollamallm
  ollamallm M2 Pro 16GB
  ollamallm MacBook Air M1 8GB
  ollamallm MacBook Pro 2019
  ollamallm MacBook Pro 2020 Intel
  ollamallm RTX 4090

型号里加上 Intel 或 M1 可指定 CPU 类型。
```

---

## 8. 技术方案建议

### 8.1 技术栈（推荐）

| 层级 | 选型 | 理由 |
|------|------|------|
| 语言 | Go 或 Python | Go：单二进制分发；Python：Mac 检测库成熟 |
| CLI 框架 | Cobra (Go) / Typer (Python) | 标准 CLI 体验 |
| 数据 | 内嵌 JSON catalog | 离线可用 |
| 打包 | 单文件二进制 + Homebrew | Mac 用户友好 |

### 8.2 模块划分

```
ollamallm/
├── cmd/                 # CLI 入口
├── detector/
│   ├── darwin.go        # macOS 本机检测
│   ├── linux.go         # Linux GPU 检测
│   └── windows.go       # Windows GPU 检测
├── resolver/
│   ├── mac_resolver.go      # Mac 型号解析
│   ├── cpu_resolver.go      # CPU 架构判定（Apple / Intel）
│   └── gpu_resolver.go      # 显卡型号解析
├── matcher/
│   └── engine.go            # 模型匹配与分级（含 CPU 分支）
├── catalog/
│   ├── models.json          # Ollama 模型库
│   ├── mac_specs.json       # Apple Silicon 规格库
│   ├── mac_intel_specs.json # Intel Mac 规格库
│   ├── mac_model_ids.json   # Model Identifier → CPU 映射
│   └── gpu_specs.json       # 显卡规格库
└── output/
    ├── table.go         # 终端表格
    └── json.go          # JSON 输出
```

### 8.3 关键依赖

- **本机检测（macOS）**：仅使用系统命令（`sysctl`、`system_profiler`），不引入第三方
- **不依赖 Ollama 运行时**：纯推荐工具，不调用 Ollama API
- **可选**：检测 Ollama 是否已安装及已拉取模型（`ollama list`），标注「已安装 ✓」

---

## 9. 数据维护策略

### 9.1 模型 Catalog 更新

| 方式 | 频率 | 说明 |
|------|------|------|
| 内置基线 | 随版本发布 | 覆盖 Top 50 常用模型；**用户无需手动更新** |
| 社区贡献 | PR 更新 | 新模型提交 size 数据 |

### 9.2 规格库维护

- **Apple Silicon**：随 Apple 新品发布更新（M5 等）
- **Intel Mac**：覆盖 2018–2020 主流型号（Air / Pro / mini / iMac），不再新增
- **Model Identifier 映射**：随 macOS 新硬件更新；Intel 机型固化
- **GPU**：覆盖 NVIDIA RTX 30/40/50 系主流型号；AMD RX 6000/7000 次之

---

## 10. 非功能需求

| 类别 | 要求 |
|------|------|
| 性能 | 冷启动 < 500ms，检测 < 200ms |
| 离线 | 核心功能完全离线 |
| 隐私 | 不上传硬件信息 |
| 兼容性 | macOS 11+（Apple Silicon + Intel Mac）；Linux/Windows Phase 2 |
| 国际化 | MVP 中文输出；架构预留 i18n |
| 可测试性 | 规格库与匹配引擎单元测试覆盖率 ≥ 80% |

---

## 11. 边界与已知限制

1. **速度为估算值**：实际 tok/s 受散热、后台负载、Ollama 版本影响
2. **内存占用为典型值**：同一 `8b` 标签不同版本可能有 ±10% 差异
3. **MoE / 多模态模型**：加载逻辑复杂，MVP 标注「实验性支持」
4. **CPU-only 模式**：Intel Mac 以 CPU 推理为主，推荐上限 7B，速度标注「慢」
5. **多 GPU**：MVP 仅简单求和，不做 NVLink/负载均衡建模
6. **Mac 内存不可升级**：推荐时可提示「此配置无法通过升级改善」
7. **Intel Mac 独显**：AMD Radeon 信息仅展示，不纳入 Ollama GPU 加速计算
8. **CPU 判定置信度**：仅产品线名称无年份时无法自动判定，必须用户选择

---

## 12. 版本规划

### Phase 1 — MVP（4 周）

- [x] PRD 与数据模型设计
- [ ] macOS 本机检测（含 Apple Silicon / Intel 自动识别）
- [ ] Mac CPU 架构判定（Model ID + 产品线年份 + 用户选择）
- [ ] Apple Silicon 芯片 + 内存型号解析（M1-M4 全系）
- [ ] Intel Mac 基础规格库（2018–2020 主流机型）
- [ ] 内置 30+ 主流 Ollama 模型 catalog
- [ ] 终端表格输出 + 推荐等级 + **CPU 架构字段**
- [ ] `ollamallm` / `ollamallm <型号>` 两条命令（零参数日常用法）
- [ ] CPU 不确定时 1/2 交互选择；型号中加 Intel/M1 可消歧

### Phase 2 — 扩展（+3 周）

- [ ] NVIDIA / AMD 显卡型号库
- [ ] `--json` / `OLLAMALLM_JSON`（脚本集成，不进主 help）
- [ ] Linux / Windows 本机检测
- [ ] `ollama list` 已安装模型标注
- [ ] Homebrew 分发

### Phase 3 — 增强（+4 周）

- [ ] 在线 catalog 更新
- [ ] 交互式 TUI（选择模型一键 pull）
- [ ] 与 Ollama Modelfile 集成（自动推荐 context/quant 参数）
- [ ] Web 版（可选，输入型号在线查询）

---

## 13. 风险分析

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模型大小数据过时 | 推荐不准 | 版本化 catalog + 更新命令 |
| Mac 型号歧义（同芯片不同内存） | 解析错误 | 强制提取 GB，歧义时交互确认 |
| **CPU 架构误判（Intel/Apple 混淆）** | **推荐严重失真** | **重叠年份 1/2 交互；输出展示判定依据；型号中加 Intel/M1 重试** |
| 用户期望精确 tok/s | 信任度下降 | 明确标注「预估值区间」 |
| Apple 新芯片发布 | 规格库滞后 | 芯片代际通用估算 fallback |
| Ollama 更改默认量化 | 占用偏差 | catalog 记录 quant 版本 |

---

## 14. 验收标准（MVP）

### 功能 1

- [ ] 在 M 系列 Mac 上正确识别芯片型号、**CPU 架构（Apple Silicon）**与内存容量
- [ ] 在 Intel Mac 上正确识别 **CPU 架构（Intel）**、芯片型号与内存容量
- [ ] 输出**必须包含 CPU 架构字段**
- [ ] 输出至少 5 个模型，含 ⭐/✅/⚠️/❌ 分级
- [ ] 每条推荐包含 `ollama pull` 命令
- [ ] 8GB Mac 不推荐 8B 以上模型为 ⭐/✅
- [ ] Intel Mac 不推荐 14B 以上模型为 ⭐/✅

### 功能 2

- [ ] 支持 `M1`/`M2 Pro 16GB`/`Mac Studio M2 Ultra 64GB` 等 Apple 输入
- [ ] 支持 `MacBook Pro 2019`/`Mac mini 2018` 等 Intel 输入并自动判定
- [ ] `MacBook Pro 2020` 弹出 1/2 选择；`MacBook Pro 2020 Intel` 直接出结果
- [ ] 无需任何参数即可完成上述流程
- [ ] 支持 `RTX 4090`/`RTX 3060 12GB` 输入（Phase 2 可降级为 MVP 仅 Mac）
- [ ] 无法识别时给出示例型号（非子命令列表）
- [ ] 同硬件本机检测与型号查询结果一致

---

## 15. 附录

### A. 内存估算速查（Q4_K_M）

| 参数量 | 约占用 | 最低建议内存 |
|--------|--------|-------------|
| 1-3B | 0.8-2 GB | 4 GB |
| 7-8B | 4-5 GB | 8 GB |
| 13-14B | 8-9 GB | 12 GB |
| 32-34B | 18-20 GB | 24 GB |
| 70-72B | 40-43 GB | 48 GB |

### B. 参考数据源

- [Ollama Library](https://ollama.com/library)
- [Ollama RAM & VRAM Calculator](https://localaimaster.com/blog/ollama-model-ram-vram-table)
- [Apple Silicon LLM Guide (InsiderLLM)](https://insiderllm.com/guides/running-llms-mac-m-series/)
- Apple 官方 Tech Specs（M 系列带宽/GPU 核心）

### C. 竞品参考

| 工具 | 差异 |
|------|------|
| 在线 VRAM Calculator | ollamallm 专注 Ollama + CLI + Mac 本机检测 |
| `ollama run` 试错 | ollamallm 事前推荐，避免反复 pull/OOM |
| ChatGPT 咨询 | ollamallm 离线、可脚本化、数据可更新 |

### D. Mac 产品线 CPU 切换时间线

```
MacBook Air     ████████████ Intel ──|── Apple (2020 秋 M1)
MacBook Pro 13" ████████████ Intel ──|── Apple (2020 秋 M1)   ← 2020 重叠
MacBook Pro 14"                      └── Apple only (2021+)
MacBook Pro 16" ████████ Intel (–2019) └── Apple (2021+)
Mac mini        ████████ Intel (–2018) ──|── Apple (2020 秋 M1)
iMac 27"        ████████████ Intel (–2020)
iMac 24"                             └── Apple only (2021+)
Mac Studio                           └── Apple only (2022+)
Mac Pro         ████ Intel (2019) ──────── Apple (2023 M2 Ultra)
```

### E. HardwareProfile 数据模型（含 CPU）

```yaml
HardwareProfile:
  device_name: string          # "MacBook Pro 15\" (2019)"
  cpu_family: apple | intel    # 必填
  cpu_confidence: explicit | inferred | user_selected
  chip: string                 # "Apple M3 Pro" / "Intel Core i7-9750H"
  memory_gb: number
  memory_type: unified | system
  gpu: string | null           # Intel 独显/集显描述
  bandwidth_gbs: number | null # Apple Silicon 专用
  available_inference_gb: number
  inference_mode: metal_gpu | cpu_only
```

---

*文档结束 v0.3*
