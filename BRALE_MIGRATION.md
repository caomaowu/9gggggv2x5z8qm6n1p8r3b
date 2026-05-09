# Brale LLM 分析层移植

> 将 brale-core-master 的 LLM 分析 Agent 层移植到 Refactor_v2，保留回测、前端、历史数据管线，只替换 Agent 层。

参考项目路径：`brale-core-master/`

---

## 一、目标

- **删除** `app/agents/indicator_agent.py`、`pattern_agent.py`、`trend_agent.py`（可以再删其它）
- **新建** 3 个 Agent + 3 个预处理模块 + 1 个融合层（对照 brale-core-master 实现）
- **保留** Decision Agent，但输入改为结构化 JSON（不再接收自由文本）
- **保留** 前端，展示改为 `movement_score` 融合值和各 Agent 分项

## 二、架构变化

```
改造前                             改造后
───────────────────────           ───────────────────────
Indicator Agent (LLM+工具调用)     Indicator Agent (纯文本 LLM)
Pattern Agent (图片→视觉 LLM)      Structure Agent (纯文本 LLM)
Trend Agent (图片→视觉 LLM)        Mechanics Agent (纯文本 LLM)
     ↓                                 ↓
Decision Agent (汇总自由文本)       Fusion 融合层 (加权 movement_score)
                                        ↓
                                   Decision Agent (接收结构化 JSON)
```

关键变化：不再生成图表 / 不再调 LangChain tool / 输入是预计算压缩 JSON / 输出是严格 JSON Schema。

---

## 三、数据源

已有基础设施：`app/services/market_data.py` — `MarketDataService` 封装了 OKX v5 透明反代。

**OHLCV** 直接用 `get_ohlcv_data()`，已区分实时/历史端点。

**衍生品数据**需在 `MarketDataService` 中新增以下方法，全部复用 `self._make_request()`：

| 方法 | 反代端点 | 注意 |
|------|---------|------|
| `fetch_open_interest(symbol)` | `GET /api/v5/public/open-interest` | 快照，仅当前值 |
| `fetch_open_interest_history(symbol, period, limit)` | `GET /api/v5/rubik/stat/contracts/open-interest-volume` | 参数用 `ccy`，**`after` 无效** |
| `fetch_funding_rate_history(symbol, limit, after)` | `GET /api/v5/public/funding-rate-history` | ✅ 支持 `after` 翻页 |
| `fetch_long_short_ratio(symbol, period, limit)` | `GET /api/v5/rubik/stat/contracts/long-short-account-ratio` | 参数用 `ccy`，**`after` 无效** |
| `fetch_taker_volume_ratio(symbol, period, limit)` | `GET /api/v5/rubik/stat/contracts/taker-volume-ratio` | 参数用 `ccy`，**`after` 无效** |
| `fetch_liquidation_orders(symbol, limit)` | `GET /api/v5/public/liquidation-orders` | 参数用 `uly`，仅最近 ~16 条 |

> 端点路径和参数细节见 `doc/OKX_v5_API_透传使用指南.md`

---

## 四、预处理模块

在 `app/agents/preprocessing/` 下新建：

```
app/agents/preprocessing/
├── __init__.py
├── indicator_compress.py
├── structure_compress.py
├── mechanics_compress.py
└── fusion.py
```

| 文件 | 参考 brale-core-master | 说明 |
|------|------------------------|------|
| `indicator_compress.py` | `internal/decision/features/indicator_compress.go` | 多周期 OHLCV → 指标计算 + 状态离散化 |
| `structure_compress.py` | `internal/decision/features/trend_compress_structure.go` | 分形点 / 突破 / SMC / 形态识别 |
| `mechanics_compress.py` | `internal/decision/features/mechanics_compress.go` | 衍生品数据 → OI/资金费率/多空比/清算状态 |
| `fusion.py` | `internal/decision/direction/consensus.go` | 三 Agent 的 movement_score 加权融合 |

预处理参数（周期、阈值等）见 `internal/config/defaults.go` 的 `DefaultSymbolConfig()`。

预处理和各 Agent 的输入 JSON 结构见 `internal/decision/features/types.go`。

---

## 五、三个 Agent

在 `app/agents/` 下新建：

| 文件 | 参考 brale-core-master | 说明 |
|------|------------------------|------|
| `brale_indicator_agent.py` | `internal/llm/app/llm_prompts.go` → `AgentIndicatorPrompt()` | 接收 indicator 压缩 JSON → 输出 `IndicatorSummary` |
| `brale_structure_agent.py` | `internal/llm/app/llm_prompts.go` → `AgentStructurePrompt()` | 接收 structure 压缩 JSON → 输出 `StructureSummary` |
| `brale_mechanics_agent.py` | `internal/llm/app/llm_prompts.go` → `AgentMechanicsPrompt()` | 接收 mechanics 压缩 JSON → 输出 `MechanicsSummary` |

各 Agent 输出字段定义（枚举值 + 类型）：`internal/decision/agent/types.go`

- `IndicatorSummary` → 第 326 行
- `StructureSummary` → 第 337 行
- `MechanicsSummary` → 第 349 行

Agent 的 system prompt 从 `internal/config/prompts.go` 获取，LLM 温度参数见 `internal/config/defaults.go`。

---

## 六、Fusion 融合层

实现 `app/agents/preprocessing/fusion.py`，参考：

- `internal/decision/direction/consensus.go` — 加权融合算法
- `internal/decision/ruleflow/node_monitor_fusion.go` — 融合后处理

融合输出 `direction: up/down/none` + `confidence: float`，喂给 Decision Agent。

---

## 七、管线改造

| 文件 | 改动 |
|------|------|
| `app/services/market_data.py` | 新增衍生品数据方法（见第三章） |
| `app/services/trading_engine.py` | 新增 `structure_llm` / `mechanics_llm`，传入衍生品数据 |
| `app/core/graph_setup.py` | 替换 3 个 Agent 节点，新增 Fusion 逻辑 |
| `app/agents/agent_state.py` | 新增 brale 相关状态字段 |
| `app/agents/decision/core_decision.py` | 适配结构化 JSON 输入 |
| `app/agents/decision/decision_configs.py` | 更新 Decision Agent system prompt |

---

## 八、注意事项

1. **STC 算法**：brale 用 Go 实现，需用 Python/NumPy 复现。参考 `internal/decision/features/indicator_stc.go`
2. **JSON 解析容错**：LLM 输出需做容错处理（去代码块标记、`json.loads` 失败返回默认值）
3. **rubik 端点限制**：OI/多空比等 rubik 端点不支持 `after` 翻页，回测时数据窗口有限，Mechanics 预处理需如实标记 `missing`
4. **Token 控制**：预处理裁剪规则参考 `internal/decision/features/` 下的 compress 文件，输入 LLM 前删除冗余字段

---

## 九、文件清单

### 新增

```
app/agents/preprocessing/__init__.py
app/agents/preprocessing/indicator_compress.py
app/agents/preprocessing/structure_compress.py
app/agents/preprocessing/mechanics_compress.py
app/agents/preprocessing/fusion.py
app/agents/brale_indicator_agent.py
app/agents/brale_structure_agent.py
app/agents/brale_mechanics_agent.py
```

### 修改

| 文件 | 修改内容 |
|------|---------|
| `app/services/market_data.py` | 新增衍生品数据方法 |
| `app/services/trading_engine.py` | 新增 LLM 调用 |
| `app/core/graph_setup.py` | 替换 Agent 节点 |
| `app/agents/agent_state.py` | 新增字段 |
| `app/agents/decision/core_decision.py` | 适配输入 |
| `app/agents/decision/decision_configs.py` | 更新 prompt |

### 删除

| 文件 | 替换为 |
|------|--------|
| `app/agents/indicator_agent.py` | `brale_indicator_agent.py` |
| `app/agents/pattern_agent.py` | `brale_structure_agent.py` |
| `app/agents/trend_agent.py` | `brale_mechanics_agent.py` |

---

## 十、实现顺序

| 优先级 | 步骤 |
|:--:|------|
| P0 | `market_data.py` 新增衍生品方法 |
| P0 | `indicator_compress.py` |
| P0 | `brale_indicator_agent.py`（先跑通一个 Agent 端到端） |
| P1 | `structure_compress.py` + `brale_structure_agent.py` |
| P1 | `mechanics_compress.py` + `brale_mechanics_agent.py` |
| P1 | `fusion.py` |
| P2 | 管线改造（graph_setup / trading_engine / agent_state） |
| P2 | Decision Agent 适配 + 删除旧 Agent |
