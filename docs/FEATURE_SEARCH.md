# 模型关键词搜索 — 功能规格（v0.2 Draft）

| 字段 | 内容 |
|------|------|
| 功能名称 | 模型关键词搜索 |
| 版本 | v0.2 Draft |
| 日期 | 2026-05-30 |
| 依赖 | 硬件检测 / 模型匹配引擎（已有） |

---

## 1. 功能一句话

在本机（或指定设备）上，**按关键词筛选**可安装的 Ollama 模型——输入 `qwen`，只列出名称包含 `qwen` 且当前硬件能跑的模型。

---

## 2. 用户故事

| 角色 | 场景 | 期望 |
|------|------|------|
| 开发者 | 只想用 Qwen 系列，不想在 78 个模型里翻 | `ollamallm qwen` 列出全部 qwen 可安装项 |
| 购机用户 | 关心某品牌模型在 M2 上能不能跑 | `ollamallm llama M2 16GB` 在 M2 上搜 llama |
| 新手 | 记得模型名片段，不记得完整 tag | 输入 `deepseek` 能模糊匹配 `deepseek-r1:7b` |

---

## 3. 设计原则（与 PRD 一致）

1. **命令仍然简单** — 不新增子命令，关键词直接写在命令后面
2. **智能识别意图** — 自动区分「设备查询」与「模型搜索」，用户无需记模式切换参数
3. **默认本机** — 无设备后缀时，基于本机硬件过滤
4. **只展示有意义的** — 默认列出匹配项并标注是否可安装；可安装项优先展示

---

## 4. 命令设计

### 4.1 基本用法

```bash
ollamallm qwen                 # 本机 + 搜 qwen
ollamallm llama                # 本机 + 搜 llama
ollamallm deepseek             # 本机 + 搜 deepseek
ollamallm qwen M2 Pro 16GB     # 指定设备 + 搜 qwen
ollamallm codellama RTX 4090   # 指定显卡 + 搜 codellama
```

**规则：最后一个「设备段」之前的词为搜索关键词，之后为设备型号。**

解析示例：

| 输入 | 关键词 | 设备 |
|------|--------|------|
| `qwen` | qwen | 本机 |
| `qwen2.5` | qwen2.5 | 本机 |
| `qwen M2 16GB` | qwen | M2 16GB |
| `llama MacBook Air M1 8GB` | llama | MacBook Air M1 8GB |
| `M2 Pro 16GB` | — | M2 Pro 16GB（设备查询，无搜索词） |
| `RTX 4090` | — | RTX 4090（设备查询） |

### 4.2 意图识别优先级

```
输入 argv
  │
  ├─ help / -h / --help          → 帮助
  ├─ 空                           → 本机全量推荐
  │
  └─ 分词后路由
       │
       ├─ 整句匹配设备型号？        → 设备查询（现有逻辑）
       │   （MacBook / RTX / M2 Pro 16GB / Mac mini 等）
       │
       ├─ 首词是已知模型族关键词？   → 模型搜索
       │   （qwen / llama / mistral / deepseek / gemma / phi / codellama …）
       │
       ├─ 首词非设备、非模型族       → 仍尝试模型搜索（模糊）
       │   无匹配时提示「是否为设备型号？」
       │
       └─ 歧义（如 m2 单独出现）     → 优先设备；可加提示
```

### 4.3 模型族关键词表（内置）

用于快速识别「这是搜索，不是设备」：

```
qwen, llama, mistral, mixtral, deepseek, gemma, phi, codellama,
starcoder, yi, solar, command-r, internlm, falcon, vicuna,
llava, moondream, minicpm, granite, smollm, gpt-oss, glm,
ministral, nemotron, devstral, dolphin
```

> 不在表内的词（如 `rnj`）仍走子串搜索，只是不会单独触发「明确搜索模式」。

### 4.4 不做的事

| 不做 | 原因 |
|------|------|
| `ollamallm search qwen` | 增加子命令，违背极简原则 |
| `--grep qwen` | 暴露参数 |
| 正则 / 通配符 | 复杂度高，MVP 仅子串匹配 |
| 联网搜索 ollama.com | 离线优先，搜本地 catalog |

---

## 5. 搜索逻辑

### 5.1 匹配规则

```python
keyword = 用户输入.lower()
匹配条件: keyword in model.full_name.lower()
          或 keyword in model.name.lower()
```

| 输入 | 命中示例 |
|------|----------|
| `qwen` | qwen2.5:7b, qwen3:8b, qwen2.5-coder:14b |
| `qwen2.5` | qwen2.5:7b, qwen2.5-coder:7b |
| `7b` | **MVP 不单独支持**（易误匹配，Phase 2 可选） |
| `llama3` | llama3.1:8b, llama3.2:3b, llama3.3:70b |

### 5.2 与硬件结合

1. 解析设备 → `HardwareProfile`（本机或指定型号）
2. 加载全量 catalog → `match_models(profile)` 得全部分级
3. 按关键词过滤 → `filter(keyword)`
4. 排序：可安装（⭐✅⚠️）在前，❌ 在后；同等级按参数量降序

### 5.3 展示策略

**默认模式（`--all` 未启用时）：**

- 展示全部匹配项，含 ❌ 不可安装项（最多 5 条 ❌）
- 顶部统计：`找到 12 个含「qwen」的模型，8 个可安装`

**可选紧凑模式（Phase 2）：**

- 仅展示 ⭐✅⚠️

---

## 6. 输出示例

### 6.1 本机搜索

```
$ ollamallm qwen

检测到本机配置
──────────────────────────────────────
设备    : MacBook Pro
CPU 架构: Apple Silicon
芯片    : Apple M3 (10-core GPU)
内存    : 16 GB 统一内存
可用推理: ~9.5 GB

搜索「qwen」— 找到 12 个模型，8 个可安装
──────────────────────────────────────
⭐ qwen2.5:7b           ~4.4 GB   ~32 tok/s   ollama pull qwen2.5:7b
⭐ qwen3:8b             ~5.0 GB   ~32 tok/s   ollama pull qwen3:8b
✅ qwen2.5:14b          ~8.7 GB   ~30 tok/s   ollama pull qwen2.5:14b
✅ qwen2.5-coder:7b     ~4.4 GB   ~32 tok/s   ollama pull qwen2.5-coder:7b
⚠️ qwen2.5:32b          ~18.8 GB  —           内存不足
❌ qwen2.5:72b          ~42.0 GB  —           内存不足

提示: 复制 ollama pull 命令即可安装
```

### 6.2 指定设备 + 搜索

```
$ ollamallm qwen MacBook Air M1 8GB

设备规格（来自型号库）
──────────────────────────────────────
设备    : MacBook Air (M1)
CPU 架构: Apple Silicon
内存    : 8 GB 统一内存
可用推理: ~1.5 GB

搜索「qwen」— 找到 12 个模型，3 个可安装
──────────────────────────────────────
⭐ qwen2.5:1.5b         ~1.0 GB   ~70 tok/s   ollama pull qwen2.5:1.5b
⭐ qwen2.5:0.5b         ~0.4 GB   ~80 tok/s   ollama pull qwen2.5:0.5b
✅ qwen2.5:3b           ~1.9 GB   ~35 tok/s   ollama pull qwen2.5:3b
❌ qwen2.5:7b           ~4.4 GB   —           内存不足
...
```

### 6.3 无匹配

```
$ ollamallm foo123

未找到包含「foo123」的模型。

你是否想查询设备型号？例如:
  ollamallm M2 Pro 16GB
  ollamallm RTX 4090

常用模型关键词: qwen, llama, mistral, deepseek, gemma
```

---

## 7. 输入解析算法（伪代码）

```python
def parse_args(argv: list[str]) -> Query:
    text = " ".join(argv).strip()
    if not text:
        return Query(mode=LOCAL)

    # 从右向左尝试剥离设备段
    device = try_resolve_device(text)
    if device.matched_full_string:
        keyword = text.replace(device.matched_part, "").strip()
        if not keyword:
            return Query(mode=DEVICE, device=text)
        return Query(mode=SEARCH, keyword=keyword, device=device.part)

    # 无设备段：首词是模型族 or 尝试整句为关键词
    first, *rest = text.split(maxsplit=1)
    if is_model_family(first) or not looks_like_device(text):
        if rest and looks_like_device(rest[0]):
            return Query(mode=SEARCH, keyword=first, device=rest[0])
        return Query(mode=SEARCH, keyword=text, device=LOCAL)

    return Query(mode=DEVICE, device=text)
```

**设备段剥离启发式：**

- 从输入末尾匹配已知设备模式：`RTX \d+`, `M\d+ Pro \d+GB`, `MacBook.*`, `\d+GB$` 等
- 剩余前缀为关键词（允许含空格，如 `qwen2.5 coder` → 暂不 MVP，MVP 关键词无空格）

---

## 8. 歧义处理

| 输入 | 歧义 | 处理 |
|------|------|------|
| `m2` | M2 芯片 vs 无 | 无 GB/Pro → 视为 **M2 设备**（默认 8GB） |
| `m2 qwen` | 顺序 | 解析为搜索词 `m2`（无结果）→ 提示尝试 `qwen M2 16GB` |
| `qwen M2` | 设备不完整 | 按 M2 默认内存搜索 qwen |
| `mac qwen` | 顺序 | `mac` 非有效设备 → 整句搜索「mac qwen」无结果 → 提示 |
| `16GB` | 仅内存 | 视为设备查询（无效）→ 报错 + 示例 |

**推荐顺序约定（写入 help）：**

```
ollamallm <关键词> [设备]
```

示例：`ollamallm qwen M2 16GB` ✅  
反例：`ollamallm M2 qwen` ❌（M2 会被当成关键词）

---

## 9. help 更新

```
用法:
  ollamallm                  查本机，列出全部可安装模型
  ollamallm <型号>           查指定设备
  ollamallm <关键词>         搜模型（基于本机）
  ollamallm <关键词> <型号>  搜模型（基于指定设备）

示例:
  ollamallm
  ollamallm qwen
  ollamallm llama M2 Pro 16GB
  ollamallm deepseek RTX 4090
  ollamallm M2 Pro 16GB
```

---

## 10. 模块改动（实现参考）

```
ollamallm/
├── cli.py                    # 增加意图路由 parse_query()
├── query_parser.py           # 新增：关键词/设备拆分
├── matcher/
│   └── engine.py             # 新增 search_models(profile, keyword)
└── output/
    └── formatter.py          # 新增搜索标题行、无结果提示
```

---

## 11. 验收标准

- [ ] `ollamallm qwen` 在本机输出所有名称含 qwen 的模型，且标注可安装等级
- [ ] `ollamallm qwen M2 16GB` 按 M2 16GB 硬件过滤
- [ ] `ollamallm M2 Pro 16GB` 仍为设备全量推荐（无搜索）
- [ ] 无匹配时给出友好提示，不崩溃
- [ ] 大小写不敏感：`Qwen` = `qwen`
- [ ] 响应时间 < 500ms（与全量推荐同级）

---

## 12. 版本规划

| 阶段 | 内容 |
|------|------|
| **v0.1.2 MVP** | 本机搜索 + `关键词 设备` 顺序 + 子串匹配 |
| v0.1.3 | 多关键词 `qwen llama`（OR 匹配） |
| v0.2 | 按 tag 大小过滤 `qwen 7b`；已安装标注（`ollama list`） |

---

## 13. 与现有命令的关系

```
                    ┌─────────────┐
                    │  ollamallm  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         无参数        意图解析        help
              │            │            │
         本机全量    ┌──────┴──────┐
                    │             │
               设备查询        模型搜索
                    │             │
                    └──────┬──────┘
                           │
                    HardwareProfile
                           │
                    match + filter(keyword)
                           │
                         输出
```

---

*文档结束 — 确认后可进入 v0.1.2 开发*
