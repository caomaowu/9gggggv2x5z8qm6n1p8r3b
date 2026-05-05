# Brale LLM 分析层移植改造文档

> 本文档用于指导开发：将 Brale-core 的 LLM 分析智能体移植到 Refactor_v2，保留 Refactor_v2 的回测、前端、历史数据管线，只替换 Agent 层。

---

## 一、目标

- **替换** 现有 3 个 Agent（indicator_agent / pattern_agent / trend_agent）
- **新建** Brale 风格 3 Agent（Indicator / Structure / Mechanics）
- **保留** Decision Agent 和回测管道，但适配新 Agent 的结构化 JSON 输出
- **保留** 前端预测结果展示，改为展示 `movement_score` 融合值和各 Agent 分项
- **删除** `app/agents/indicator_agent.py`、`pattern_agent.py`、`trend_agent.py`

---

## 二、架构对比

```
改造前                              改造后
─────────────────────────          ─────────────────────────
Indicator Agent (LLM+工具调用)      Indicator Agent (纯文本LLM，结构化JSON)
Pattern Agent (图片→视觉LLM)        Structure Agent (纯文本LLM，结构化JSON)
Trend Agent (图片→视觉LLM)          Mechanics Agent (纯文本LLM，结构化JSON)
     ↓                                  ↓
Decision Agent (汇总自由文本)        Fusion 融合层 (加权 movement_score)
                                         ↓
                                    Decision Agent (接收结构化 JSON)
```

**关键变化**：
- 不再生成图表、不再调用 LangChain tool
- Agent 输入是**预计算的压缩数据 JSON**，不是原始 OHLCV
- Agent 输出是**严格 JSON Schema**，不是自由文本

---

## 三、数据层 — OKX API 接入

### 3.1 需要新增的数据接口

在 `app/services/` 下新建 `okx_derivatives.py`：

```python
# 需要实现的接口（全部 REST，公开数据，无需 API Key）

class OKXDerivativesService:
    BASE_URL = "https://www.okx.com"

    def fetch_klines(
        self, symbol: str, bar: str = "15m",
        limit: int = 300,
        before: str = None, after: str = None
    ) -> pd.DataFrame:
        """
        GET /api/v5/market/history-candles
        参数: instId, bar, limit, before, after
        返回列: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        ts 是 Unix 毫秒时间戳
        """

    def fetch_open_interest(
        self, symbol: str, period: str = "5m",
        limit: int = 500, before: str = None, after: str = None
    ) -> list[dict]:
        """
        GET /api/v5/public/open-interest-history
        参数: instId, period, limit, before, after
        返回: list of {ts, oi, oiCcy}
        """

    def fetch_funding_rate_history(
        self, symbol: str,
        limit: int = 100, before: str = None, after: str = None
    ) -> list[dict]:
        """
        GET /api/v5/public/funding-rate-history
        参数: instId, limit, before, after
        返回: list of {ts, fundingRate, realizedRate}
        """

    def fetch_long_short_ratio(
        self, symbol: str, period: str = "5m",
        limit: int = 500, before: str = None, after: str = None
    ) -> list[dict]:
        """
        GET /api/v5/rubik/stat/contracts/long-short-account-ratio
        参数: ccy=USDT, before, after, period, limit
        返回: list of {ts, longAccountRatio, shortAccountRatio}
        注意: 只按 USDT 本位合约查询，不按币种区分
        """

    def fetch_taker_volume_ratio(
        self, symbol: str, period: str = "5m",
        limit: int = 500, before: str = None, after: str = None
    ) -> list[dict]:
        """
        GET /api/v5/rubik/stat/contracts/taker-volume-ratio
        参数: ccy=USDT, before, after, period, limit
        返回: list of {ts, buyVolRatio, sellVolRatio}
        """

    def fetch_liquidation_orders(
        self, symbol: str, limit: int = 100,
        before: str = None, after: str = None
    ) -> list[dict]:
        """
        GET /api/v5/public/liquidation-orders
        参数: instId, limit, before, after
        返回: list of {ts, side, sz, bkPx, bkLoss, ...}
        """

    def fetch_snapshot(
        self, symbol: str, intervals: list[str] = ["5m", "15m", "1h"]
    ) -> dict:
        """
        一次性获取所有数据，返回统一格式的快照 dict。
        这是回测和实时分析的主入口。

        返回格式:
        {
            "symbol": "BTC-USDT-SWAP",
            "klines": {
                "5m": DataFrame,
                "15m": DataFrame,
                "1h": DataFrame
            },
            "oi_history": [...],
            "funding_rate_history": [...],
            "long_short_ratio": [...],
            "taker_volume_ratio": [...],
            "liquidation_orders": [...],
        }
        """
```

### 3.2 现有 OHLCV 接口

`app/services/market_data.py` 已经通过 Quant API 获取 OHLCV，可直接复用。但如果你要完全走 OKX，上述 `fetch_klines` 也包含了 K 线获取。

**建议**：回测场景直接用 `fetch_snapshot` 一次性拉取所有历史数据；实时预测场景复用现有 `MarketDataService` 的 OHLCV + 新的 `OKXDerivativesService` 的衍生品数据。

---

## 四、预处理模块 — Brale 风格特征压缩

在 `app/agents/` 下新建 `preprocessing/` 目录：

```
app/agents/preprocessing/
├── __init__.py
├── indicator_compress.py   # 指标计算 + 状态离散化
├── structure_compress.py   # 分形点/突破/SMC/形态
├── mechanics_compress.py   # 衍生品数据摘要
└── fusion.py               # 三 Agent 输出融合
```

### 4.1 Indicator 预处理 (`indicator_compress.py`)

**输入**：多周期 OHLCV DataFrame（如 5m/15m/1h 三个）

**计算指标**（用 TA-Lib，Refactor_v2 已有依赖）：
```
ema_fast(21), ema_mid(50), ema_slow(200), rsi(14), atr(14),
stc(23/50), bb(20/2.0), chop(14), stoch_rsi(14), aroon(25)
```
> STC 算法见 Brale `internal/ta/stc.go`，需用 Python 实现。

**状态离散化**（关键步骤，把连续值映射为枚举字符串）：

```python
# 每个周期的输出结构
{
    "interval": "15m",
    "freshness_sec": 30,
    "missing": [],                    # 缺失字段列表
    "trend": {
        "price_vs_ema_fast": "above",  # above/below/near/unknown
        "price_vs_ema_mid": "above",
        "price_vs_ema_slow": "above",
        "ema_stack": "bull",           # bull/bear/mixed/unknown
        "ema_distance_fast_atr": 0.53,  # |price - ema| / atr
        "ema_distance_mid_atr": 2.15,
        "ema_distance_slow_atr": 37.01,
    },
    "momentum": {
        "rsi_zone": "55_65",           # <35 / 35_45 / 45_55 / 55_65 / >65
        "rsi_slope_state": "rising",   # rising/falling/flat/steep
        "stc_state": "rising",         # rising/falling/flat
        "obv_slope_state": "up",       # up/down/flat
        "stoch_rsi_zone": "neutral",   # oversold/neutral/overbought
    },
    "volatility": {
        "atr_expand_state": "stable",  # expanding/contracting/stable
        "atr_change_pct": 2.5,
        "bb_zone": "mid",              # upper/mid/lower
        "bb_width_state": "normal",    # narrow/normal/wide
        "chop_regime": "trending",     # trending/choppy
    },
    "bias": "up",                      # up/down/none
    "events": ["aroon_strong_bullish", "td_buy_setup_8"]
}
```

**跨周期摘要**（`cross_tf_summary`）：比较多周期的 `bias` 是否一致，输出 `alignment: aligned/conflict`。

**最终输出**（喂给 Indicator Agent 的 user prompt）：

```json
{
    "decision_interval": "15m",
    "multi_tf": [ {...5m...}, {...15m...}, {...1h...} ],
    "cross_tf_summary": {
        "decision_tf_bias": "up",
        "lower_tf_agreement": true,
        "higher_tf_agreement": false,
        "alignment": "conflict",
        "conflict_count": 1
    },
    "missing": []
}
```

### 4.2 Structure 预处理 (`structure_compress.py`)

**输入**：多周期 OHLCV DataFrame

**计算内容**：

1. **分形点检测**（类似 Brale `trend_compress_structure.go`）：
   - 参数 `fractalSpan=2`：如果某根 K 线的高点比左右各 2 根都高，标记为 High；低点同理标记为 Low
   - 最多保留 8 个最近的分形点
   - ATR 去重：距离小于 ATR 的重复点合并

2. **Swing High/Low**：
   - 最新的 Swing High（较近的显著高点）
   - 最新的 Swing Low（较近的显著低点）

3. **突破事件检测**（`break_events`）：
   - 收盘价穿过前一个 Swing High → `break_up` (BOS)
   - 收盘价穿过前一个 Swing Low → `break_down` (BOS)
   - 突破后又收回 → `choch_up` / `choch_down`
   - 字段：`type`, `level_price`, `level_idx`, `bar_idx`, `bar_age`, `confirm`

4. **形态识别**（`pattern`）：
   - 检测 13 种经典形态：double_top/bottom, head_shoulders, triangle_sym/asc/desc, wedge_rising/falling, flag, pennant, channel_up/down
   - 用 TA-Lib 的 CDL 函数 + 自定义规则判断

5. **SMC 模块**：
   - Order Block：最后一段趋势的最后一根反向 K 线
   - FVG (Fair Value Gap)：连续三根 K 线之间的价格缺口

6. **SuperTrend**：`state: UP/DOWN`, `level`, `distance_pct`

7. **结构候选水平**（`structure_candidates`）：
   - 来源：分形点 + EMA 值 + 布林带边界 + 区间高低点
   - 每条记录：`price`, `type`, `source`, `age_candles`, `window`
   - 按距离当前价格排序，上下各保留 3 个

**最终输出**（多周期聚合为一个 blocks 数组）：

```json
{
    "meta": {"symbol": "BTC-USDT"},
    "blocks": [
        { /* 5m 的完整 Structure 压缩结果 */ },
        { /* 15m 的完整 Structure 压缩结果 */ },
        { /* 1h 的完整 Structure 压缩结果 */ }
    ],
    "latest_break_across_blocks": {
        "interval": "15m",
        "type": "break_up",
        "age": 6,
        "level_price": 98200.0
    }
}
```

每个 block 的字段：
```
meta: symbol, interval, timestamp
structure_points[]: idx, type(High/Low), price, rsi
structure_candidates[]: price, type, source, age_candles, window
recent_candles[]: idx, o, h, l, c, v, rsi (最近 N 根，按需)
global_context: trend_slope, slope_state, window, vol_ratio, ema20, ema50, ema200
supertrend: interval, state, level, distance_pct
key_levels: last_swing_high(price, idx), last_swing_low(price, idx)
break_events[]: type, level_price, level_idx, bar_idx, bar_age, confirm
break_summary: latest_event_type, latest_event_age, total_events
pattern: detected[], primary
smc: order_block(type, upper, lower), fvg(type, gap_top, gap_bottom)
```

**裁剪规则**（喂 LLM 前删除冗余字段）：
- 删除 `pattern.primary`（保留 detected 列表即可）
- 删除 `global_context.trend_slope`、`normalized_slope`、`window`
- 删除 `meta.symbol`（在顶层 meta 已有）

### 4.3 Mechanics 预处理 (`mechanics_compress.py`)

**输入**：衍生品数据快照（OI 历史、资金费率、多空比、清算数据）

**状态离散化计算**：

```python
# OI State
oi_change_pct = (latest_oi - oi_5min_ago) / oi_5min_ago * 100
oi_state = {
    "change_state": "rising",          # rising (>2%) / flat / falling (<-2%)
    "oi_change_pct": 2.5,
    "price_change_pct": 2.34,
    "oi_price_relation": "price_up_oi_up"
    # price_up_oi_up / price_up_oi_down / price_down_oi_up / price_down_oi_down
}

# Funding State
funding_state = {
    "bias": "long",                    # long (>0.01%) / neutral / short (<-0.01%)
    "heat": "neutral",                 # hot (>0.05%) / neutral
    "rate": 0.00015
}

# Crowding State (结合多空比 + 吃单量比)
crowding_state = {
    "bias": "long_crowded",            # long_crowded / short_crowded / balanced
    "ls_ratio": 1.25,                  # 大户多空比
    "taker_ratio": 1.08,               # 吃单量比
    "reversal_risk": "low"             # low / medium / high
}

# Liquidation State (取最近窗口)
liquidation_state = {
    "stress": "elevated",              # high / elevated / low / unknown
    "status": "ok",                    # ok / partial / missing
    "complete": true,
    "window": "5m",
    "zscore": 1.8,                     # 清算量的 z-score
    "vol_over_oi": 0.0006,            # 清算量 / OI
    "spike": false,                    # zscore > 2.5 或 vol_over_oi > 8%
    "imbalance": -0.32                 # 正=多头被清算多，负=空头被清算多
}

# Sentiment State
sentiment_state = {
    "fear_greed": "greed",             # extreme_fear/fear/neutral/greed/extreme_greed
    "top_trader_bias": "long"          # long / neutral / short
}
```

**冲突检测**（`mechanics_conflict`）：
- OI 升但价格跌 → "价格与 OI 背离"
- 多头拥挤但资金费率偏空 → "拥挤与费率矛盾"
- 清算压力高但 OI 稳定 → "清算与持仓不匹配"

**最终输出**（原始数据 + 计算状态合并）：

```json
{
    "symbol": "BTC-USDT",
    "oi": {"value": 8.2e9, "timestamp": "...", "price": 98765.43},
    "oi_history": {"5m": {"value": 8.0e9, "change_pct": 2.5, "price": 96500.0}},
    "funding": {"rate": 0.00015, "timestamp": "..."},
    "long_short_by_interval": {
        "5m": {"ratio": 1.35}, "15m": {"ratio": 1.28}
    },
    "liquidations_by_window": {
        "5m": {
            "long_vol": 2.1e6,
            "short_vol": 3.1e6,
            "total_vol": 5.2e6,
            "imbalance": -0.32,
            "sample_count": 15,
            "coverage_sec": 300,
            "status": "ok",
            "complete": true
        }
    },
    "liquidations": {"volume": 5.2e6, "timestamp": "..."},
    "freshness_sec": 30,
    "oi_state": {...},
    "funding_state": {...},
    "crowding_state": {...},
    "liquidation_state": {...},
    "sentiment_state": {...},
    "mechanics_conflict": [],
    "missing": []
}
```

---

## 五、三个 Agent 提示词（完整中文版）

### 5.1 公共序言（三个 Agent 共用）

```
你是 brale-core AI 驱动量化交易系统中的分析模块。
你的输出会被后续程序直接解析、审计并进入自动化处理链路。
硬性输出规则：
- 只输出一个 JSON 对象；禁止输出 markdown、代码块、注释、解释文字、数组根对象、多个对象。
- 输出必须严格匹配下方给出的字段约束或 JSON Schema；不得新增字段、不得缺字段、字段类型必须正确。
- 只能使用输入里已有的信息；禁止编造任何数据、阈值、行情、上下文或外部事实。
- 若证据不足，必须保持保守，并在允许字段内如实表达不确定性。
```

### 5.2 Indicator Agent 提示词

```
你的当前角色是交易系统中的 Indicator 分析器。基于用户提供的 Indicator 输入 JSON，输出一个严格 JSON 对象，包含固定字段，用于后续审计与自动化处理。

输出 JSON Schema（必须完全一致）：
{
  "expansion": "expanding|contracting|stable|mixed|unknown",
  "alignment": "aligned|mixed|divergent|unknown",
  "noise": "low|medium|high|mixed|unknown",
  "momentum_detail": "string",
  "conflict_detail": "string",
  "movement_score": 0.0,
  "movement_confidence": 0.0,
  "next_focus": "string"
}

字段含义与约束：
- expansion/alignment/noise：只允许取枚举值。
- momentum_detail：用中文简要列出关键证据，尽量引用输入字段名或 field=value；若用户输入包含“上一轮本 Agent 待验证焦点”，必须先用“上一轮验证：...”一句话总结该焦点在当前输入中是否被确认、否定或仍不明确，然后再写本轮动能/指标证据。
- conflict_detail：用中文描述冲突；若无明显冲突，写“未观察到明显冲突”
- movement_score：数值范围 [-1, 1]，表示在当前决策窗口（参见用户输入中的“决策窗口”字段）内“价格上行倾向 vs 下行倾向”的相对偏向：+1 强烈偏向上行，0 无方向性/不确定，-1 强烈偏向下行。
- movement_confidence：数值范围 [0, 1]，表示你对 movement_score 的证据充分度/可靠度。
- 当证据不足、噪声大、或冲突明显时：movement_score 应靠近 0，movement_confidence 应偏低。
- next_focus：一句话说明下一轮本 Indicator Agent 应重点验证的指标/动能/多周期/噪音观察点；只能基于当前输入证据，不得编造阈值或外部信息。长度控制在 160 字以内；如果没有明确待验证点，输出空字符串。next_focus 是待验证焦点，不是交易建议，也不能要求下轮沿用本轮结论。

重要约束：
- 不要输出任何交易动作或建议（例如开仓/平仓/做多/做空/买入/卖出等）。只输出分析结论分数与证据描述。
```

### 5.3 Structure Agent 提示词

```
你的当前角色是交易系统中的 Market Structure 分析器。基于输入的 Trend/Structure JSON，输出一个严格 JSON 对象，用于后续审计与自动化处理。

输出 JSON Schema（必须完全一致）：
{
  "regime": "trend_up|trend_down|range|mixed|unclear",
  "last_break": "bos_up|bos_down|choch_up|choch_down|none|unknown",
  "quality": "clean|messy|mixed|unclear",
  "pattern": "double_top|double_bottom|head_shoulders|inv_head_shoulders|triangle_sym|triangle_asc|triangle_desc|wedge_rising|wedge_falling|flag|pennant|channel_up|channel_down|none|unknown",
  "volume_action": "string",
  "candle_reaction": "string",
  "movement_score": 0.0,
  "movement_confidence": 0.0,
  "next_focus": "string"
}

字段含义与约束：
- regime/last_break/quality/pattern：只允许取枚举值。
- volume_action：用中文简要描述证据，尽量引用输入字段名或 field=value，不要编造；若用户输入包含“上一轮本 Agent 待验证焦点”，必须先用“上一轮验证：...”一句话总结该焦点在当前输入中是否被确认、否定或仍不明确，然后再写本轮量价/结构证据。
- candle_reaction：描述价格对关键位/突破后的反应（例如回踩/拒绝/延续），同样只引用输入信息。使用中文输出结果
- movement_score：数值范围 [-1, 1]，表示在当前决策窗口（参见用户输入中的“决策窗口”字段）内“结构层面偏上行 vs 偏下行”的相对倾向。
- movement_confidence：数值范围 [0, 1]，表示该倾向的可靠度（结构是否清晰、事件是否明确、质量是否稳定）。
- 当 regime 为 range/mixed/unclear，或 last_break 为 none/unknown，或 quality 为 messy/unclear 时：movement_score 靠近 0，movement_confidence 偏低。
- next_focus：一句话说明下一轮本 Structure Agent 应重点验证的结构/突破/区间/蜡烛反应/量价结构观察点；只能基于当前输入证据，不得编造阈值或外部信息。长度控制在 160 字以内；如果没有明确待验证点，输出空字符串。next_focus 是待验证焦点，不是交易建议，也不能要求下轮沿用本轮结论。
- 多周期 blocks 从短周期到长周期排列；同一 block 内 idx 越小越早，idx 越大越晚。
- recent_candles 与 structure_points 都按 idx 从小到大排列；level_idx 表示被突破的关键位来自哪根历史K线，bar_idx 表示突破发生在哪根K线上，bar_age=0 表示最新K线就是突破K线。
- idx 只用于表达前后关系，不应单独决定结论。

重要约束（防止行动泄漏）：
- 不要输出任何交易动作或建议（例如做多/做空/开仓等）。只输出结构判断与分数。
```

### 5.4 Mechanics Agent 提示词

```
你的当前角色是交易系统中的 Market Mechanics 分析器。基于提供的 Mechanics 输入 JSON，输出一个严格 JSON 对象，用于后续审计与自动化处理。

输出 JSON Schema（必须完全一致）：
{
  "leverage_state": "increasing|stable|overheated|unknown",
  "crowding": "long_crowded|short_crowded|balanced|unknown",
  "risk_level": "low|medium|high|unknown",
  "open_interest_context": "string",
  "anomaly_detail": "string",
  "movement_score": 0.0,
  "movement_confidence": 0.0,
  "next_focus": "string"
}

字段含义与约束：
- leverage_state/crowding/risk_level：只允许取枚举值。
- open_interest_context：用中文概述你依赖的 OI/资金费率/拥挤等事实依据（引用输入字段）；若用户输入包含“上一轮本 Agent 待验证焦点”，必须先用“上一轮验证：...”一句话总结该焦点在当前输入中是否被确认、否定或仍不明确，然后再写本轮机制/OI/资金费率证据。
- anomaly_detail：用中文概述异常/压力/拥挤反转等迹象（引用输入字段）。
- movement_score：数值范围 [-1, 1]，表示在当前决策窗口（参见用户输入中的“决策窗口”字段）内“机制层面对上行/下行的偏向”。证据不足时分数应靠近 0。
- movement_confidence：数值范围 [0, 1]，表示你对该偏向的可靠度；当风险高、信息弱或矛盾时应偏低。
- next_focus：一句话说明下一轮本 Mechanics Agent 应重点验证的杠杆/OI/funding/拥挤/清算压力/异常观察点；只能基于当前输入证据，不得编造阈值或外部信息。长度控制在 160 字以内；如果没有明确待验证点，输出空字符串。next_focus 是待验证焦点，不是交易建议，也不能要求下轮沿用本轮结论。

重要约束（防止行动泄漏）：
- 不要输出任何交易动作或建议（例如做多/做空/开仓等）。只输出机制判断与分数。
```

### 5.5 User Prompt 格式

每个 Agent 的 user prompt 由两段组成：标签化数据块 + 决策窗口行。

**Indicator Agent User Prompt**：
```
Indicator 输入
{压缩后的 indicatorStateInput JSON}

Decision Window:
15m
```

**Structure Agent User Prompt**：
```
Structure 输入
{压缩后的 trendMultiInput JSON (多周期 blocks)}

Decision Window:
15m
```

**Mechanics Agent User Prompt**：
```
Mechanics 输入
{压缩后的 mechanics 摘要 JSON}

Decision Window:
15m
```

---

## 六、Agent 实现规范

### 6.1 新文件结构

```
app/agents/
├── __init__.py
├── agent_state.py              # 修改：新增 brale 相关状态字段
├── preprocessing/
│   ├── __init__.py
│   ├── indicator_compress.py
│   ├── structure_compress.py
│   ├── mechanics_compress.py
│   └── fusion.py
├── brale_indicator_agent.py    # 新：Indicator Agent
├── brale_structure_agent.py    # 新：Structure Agent
├── brale_mechanics_agent.py    # 新：Mechanics Agent
├── decision/                   # 保留，修改适配 JSON 输入
│   ├── ...
├── CLAUDE.md                   # 更新
│
├── indicator_agent.py          # 【删除】
├── pattern_agent.py            # 【删除】
└── trend_agent.py              # 【删除】
```

### 6.2 Agent 节点实现模板

三个 Agent 的结构完全一致，以 Indicator Agent 为例：

```python
# app/agents/brale_indicator_agent.py

"""
Brale-style Indicator Agent.
接收预处理后的 indicatorStateInput JSON，调用 LLM 输出结构化 IndicatorSummary。
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.preprocessing.indicator_compress import build_indicator_state
from app.core.config import settings

# 内置提示词（可从配置文件加载）
SYSTEM_PROMPT = """...（上面 5.2 的完整中文提示词）..."""


def create_brale_indicator_agent(llm):

    def indicator_agent_node(state: dict) -> dict:
        kline_data = state["kline_data"]       # dict: {"5m": DataFrame, "15m": DataFrame, ...}
        symbol = state.get("stock_name", "Unknown")
        time_frame = state.get("time_frame", "15m")

        # 1. 预处理：计算指标 + 状态离散化
        user_payload = build_indicator_state(
            kline_data=kline_data,
            symbol=symbol,
            decision_interval=time_frame,
        )

        # 2. 构建 user prompt
        user_text = (
            f"Indicator 输入\n"
            f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n\n"
            f"Decision Window:\n{time_frame}\n"
        )

        # 3. 调用 LLM（纯文本，不用 tool）
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_text),
        ])

        # 4. 解析 JSON 响应
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {
                "expansion": "unknown",
                "alignment": "unknown",
                "noise": "unknown",
                "momentum_detail": "解析失败",
                "conflict_detail": "解析失败",
                "movement_score": 0.0,
                "movement_confidence": 0.0,
                "next_focus": "",
                "error": f"JSON parse error: {response.content[:200]}"
            }

        # 5. 返回结构化结果
        return {
            "messages": state.get("messages", []) + [response],
            "brale_indicator_summary": result,          # 结构化 JSON
            "brale_indicator_report": response.content, # 原始文本（备用）
        }

    return indicator_agent_node
```

**Structure Agent** 同理，替换 `SYSTEM_PROMPT` 和 `build_structure_state()`。

**Mechanics Agent** 同理，替换 `SYSTEM_PROMPT` 和 `build_mechanics_state()`。如果衍生品数据缺失（回测中部分时间段无法获取），`build_mechanics_state()` 返回 `missing: ["oi_history", "funding"]` 字段，Agent 提示词会指导 LLM 对此保持保守。

### 6.3 Agent State 修改

修改 `app/agents/agent_state.py`，新增字段：

```python
# 在 IndicatorAgentState TypedDict 中新增：

# Brale Agent 结构化输出
brale_indicator_summary: dict     # IndicatorSummary JSON
brale_structure_summary: dict     # StructureSummary JSON
brale_mechanics_summary: dict     # MechanicsSummary JSON

# 各 Agent 的 movement_score（用于融合）
indicator_movement_score: float
structure_movement_score: float
mechanics_movement_score: float

# 衍生品数据快照（从 OKX 拉取）
derivatives_snapshot: dict

# 原始报告（可选，保留兼容）
brale_indicator_report: str
brale_structure_report: str
brale_mechanics_report: str
```

---

## 七、输出融合层 (`fusion.py`)

三个 Agent 各自输出一个 `movement_score`（范围 [-1, 1]），需要融合为最终的 K 线方向预测。

```python
# app/agents/preprocessing/fusion.py

"""
融合三个 Brale Agent 的 movement_score，得出最终预测方向。
"""

from enum import Enum


class PredictionDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


def fuse_movement_scores(
    indicator_score: float,
    indicator_confidence: float,
    structure_score: float,
    structure_confidence: float,
    mechanics_score: float,
    mechanics_confidence: float,
) -> dict:
    """
    加权融合三个 Agent 的 movement_score。

    策略：以置信度平方为权重，抑制低置信度 Agent 的影响。

    Args:
        indicator_score: Indicator Agent 的 movement_score [-1, 1]
        indicator_confidence: Indicator Agent 的 movement_confidence [0, 1]
        structure_score: 同上
        structure_confidence: 同上
        mechanics_score: 同上
        mechanics_confidence: 同上

    Returns:
        {
            "fused_score": float,        # 融合后的 movement_score [-1, 1]
            "direction": "up/down/neutral",
            "confidence": float,         # 融合置信度 [0, 1]
            "components": {              # 各分项
                "indicator": {...},
                "structure": {...},
                "mechanics": {...}
            }
        }
    """
    # 权重 = 置信度的平方（惩罚低置信度）
    w_i = indicator_confidence ** 2
    w_s = structure_confidence ** 2
    w_m = mechanics_confidence ** 2

    total_weight = w_i + w_s + w_m

    if total_weight == 0:
        return {
            "fused_score": 0.0,
            "direction": "neutral",
            "confidence": 0.0,
            "components": {
                "indicator": {"score": indicator_score, "confidence": indicator_confidence, "weight": 0.0},
                "structure": {"score": structure_score, "confidence": structure_confidence, "weight": 0.0},
                "mechanics": {"score": mechanics_score, "confidence": mechanics_confidence, "weight": 0.0},
            }
        }

    fused = (w_i * indicator_score + w_s * structure_score + w_m * mechanics_score) / total_weight

    # 方向判断
    if fused > 0.15:
        direction = "up"
    elif fused < -0.15:
        direction = "down"
    else:
        direction = "neutral"

    # 融合置信度 = max(各分项置信度)：最确定的 Agent 有多确定
    fusion_confidence = max(indicator_confidence, structure_confidence, mechanics_confidence)

    return {
        "fused_score": round(fused, 4),
        "direction": direction,
        "confidence": round(fusion_confidence, 4),
        "components": {
            "indicator": {
                "score": indicator_score,
                "confidence": indicator_confidence,
                "weight": round(w_i / total_weight, 4) if total_weight > 0 else 0.0
            },
            "structure": {
                "score": structure_score,
                "confidence": structure_confidence,
                "weight": round(w_s / total_weight, 4) if total_weight > 0 else 0.0
            },
            "mechanics": {
                "score": mechanics_score,
                "confidence": mechanics_confidence,
                "weight": round(w_m / total_weight, 4) if total_weight > 0 else 0.0
            },
        }
    }
```

---

## 八、Graph 改造 (`graph_setup.py`)

### 8.1 新的并行协调器

```python
# 在 SetGraph.set_graph() 中修改：

# 替换旧 Agent 节点
agent_nodes["indicator"] = create_brale_indicator_agent(self.indicator_llm)
agent_nodes["structure"] = create_brale_structure_agent(self.structure_llm)
agent_nodes["mechanics"] = create_brale_mechanics_agent(self.mechanics_llm)

# 融合节点（在协调器中调用）
def sequential_start_coordinator(state):
    # ... 并行执行三个 Agent（保持现有 ThreadPoolExecutor 逻辑）...

    # 新增：融合三个 Agent 的输出
    ind_summary = shared_state.get("brale_indicator_summary", {})
    st_summary = shared_state.get("brale_structure_summary", {})
    mech_summary = shared_state.get("brale_mechanics_summary", {})

    fusion_result = fuse_movement_scores(
        indicator_score=ind_summary.get("movement_score", 0.0),
        indicator_confidence=ind_summary.get("movement_confidence", 0.0),
        structure_score=st_summary.get("movement_score", 0.0),
        structure_confidence=st_summary.get("movement_confidence", 0.0),
        mechanics_score=mech_summary.get("movement_score", 0.0),
        mechanics_confidence=mech_summary.get("movement_confidence", 0.0),
    )

    shared_state["fusion_result"] = fusion_result
    shared_state["predicted_direction"] = fusion_result["direction"]

    return shared_state
```

### 8.2 TradingEngine 修改

```python
# app/services/trading_engine.py

# 新增 LLM 实例
self.structure_llm = self._create_llm_client(role="agent", agent_name="structure")
self.mechanics_llm = self._create_llm_client(role="agent", agent_name="mechanics")

# 去除 pattern_llm / trend_llm（或用同一实例复用）
```

---

## 九、Decision Agent 适配

Decision Agent 原来接收三个自由文本报告（`indicator_report`、`pattern_report`、`trend_report`），改为接收结构化 JSON：

```python
# 在 core_decision.py 中，prompt 占位符改为：

{indicator_summary_json}  # IndicatorSummary 的 JSON 字符串
{structure_summary_json}  # StructureSummary 的 JSON 字符串
{mechanics_summary_json}  # MechanicsSummary 的 JSON 字符串
{fusion_result_json}      # 融合结果 {"fused_score": 0.35, "direction": "up", ...}
```

Decision Agent 的提示词需要相应修改，要求它基于这三个结构化 JSON 和融合分数，给出最终的 `BUY/SELL/HOLD` 判断。

---

## 十、回测适配

### 10.1 数据获取

回测脚本需要能调用 `OKXDerivativesService.fetch_snapshot()` 获取每个历史时间点的全套数据（OHLCV + 衍生品）。

思路：
- 确定回测时间范围（如 2024-01-01 ~ 2024-12-31）
- 按决策周期（如 15m）遍历每个时间点
- 每个时间点调用 `fetch_snapshot` 获取那个时刻及之前的数据（通过 `before` 参数）
- 将快照传给 Agent 分析
- 对比融合 `direction` 与下一根 K 线真实方向，统计准确率

### 10.2 回测结果展示

前端可新增展示：
- 整体准确率（UP/DOWN 预测 vs 真实涨跌）
- 各 Agent 准确率（每个 Agent 的 movement_score 符号 vs 真实方向）
- 融合分数 vs 真实涨跌幅的散点图
- 三个 Agent 的 movement_score 时序图

---

## 十一、文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/services/okx_derivatives.py` | OKX 衍生品数据接口 |
| `app/agents/preprocessing/__init__.py` | 预处理包 |
| `app/agents/preprocessing/indicator_compress.py` | 指标压缩 + 状态离散化 |
| `app/agents/preprocessing/structure_compress.py` | 结构点提取 + SMC + 形态 |
| `app/agents/preprocessing/mechanics_compress.py` | 衍生品摘要计算 |
| `app/agents/preprocessing/fusion.py` | 三 Agent 输出融合 |
| `app/agents/brale_indicator_agent.py` | Brale 风格 Indicator Agent |
| `app/agents/brale_structure_agent.py` | Brale 风格 Structure Agent |
| `app/agents/brale_mechanics_agent.py` | Brale 风格 Mechanics Agent |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `app/agents/agent_state.py` | 新增 brale 相关状态字段 |
| `app/core/graph_setup.py` | 替换 Agent 节点，新增融合逻辑 |
| `app/services/trading_engine.py` | 新增 structure_llm / mechanics_llm，传入衍生品数据 |
| `app/agents/decision/core_decision.py` | 适配结构化 JSON 输入 |
| `app/agents/decision/decision_configs.py` | 更新 Decision Agent 的 system prompt |
| `app/agents/CLAUDE.md` | 更新文档 |

### 删除文件

| 文件 | 说明 |
|------|------|
| `app/agents/indicator_agent.py` | 替换为 brale_indicator_agent.py |
| `app/agents/pattern_agent.py` | 替换为 brale_structure_agent.py |
| `app/agents/trend_agent.py` | 替换为 brale_mechanics_agent.py |

---

## 十二、实现顺序

| 优先级 | 步骤 | 预估工作量 |
|:--:|------|:--:|
| P0 | `okx_derivatives.py` — OKX 数据拉取 | 1天 |
| P0 | `indicator_compress.py` — 指标计算 + 状态离散化 | 1天 |
| P0 | `brale_indicator_agent.py` — 第一个 Agent（验证端到端可行） | 0.5天 |
| P1 | `structure_compress.py` — 结构特征提取 | 1.5天 |
| P1 | `brale_structure_agent.py` | 0.5天 |
| P1 | `mechanics_compress.py` — 衍生品摘要 | 0.5天 |
| P1 | `brale_mechanics_agent.py` | 0.5天 |
| P1 | `fusion.py` — 输出融合 | 0.5天 |
| P2 | `graph_setup.py` + `trading_engine.py` — 管线改造 | 0.5天 |
| P2 | Decision Agent + agent_state 适配 | 0.5天 |
| P2 | 回测脚本适配 | 0.5天 |
| P2 | 删除旧 Agent 文件 | 0.1天 |

**建议**：先完成 P0，跑通 Indicator Agent 的全链路（数据→压缩→LLM→结构化输出），验证可行后再做 P1 和 P2。

---

## 十三、关键技术参数参考

| 参数 | 值 | 来源 |
|------|-----|------|
| EMA 周期 | 21 / 50 / 200 | Brale `default.toml` |
| RSI 周期 | 14 | 同上 |
| ATR 周期 | 14 | 同上 |
| STC 周期 | 23 / 50 | 同上 |
| 布林带 | 20 / 2.0 | 同上 |
| CHOP 周期 | 14 | 同上 |
| StochRSI 周期 | 14 | 同上 |
| Aroon 周期 | 25 | 同上 |
| 分形检测跨度 | 2 | Brale `trend_compress_structure.go` |
| 最大结构点数 | 8 | 同上 |
| 最近 K 线注入数 | 5 | Brale `default.toml: last_n=5` |
| K 线拉取数量 | 300 | Brale `default.toml: kline_limit=300` |
| movement_score 范围 | [-1, 1] | Brale `agent/types.go` |
| movement_confidence 范围 | [0, 1] | 同上 |
| 融合方向阈值 | ±0.15 | 可调 |
| LLM 温度 | 0.2 | Brale `llm.agent.*.temperature` |

---

## 十四、注意事项

1. **STC 算法**：Brale 用纯 Go 实现，需用 Python/NumPy 复现。伪代码参考 Brale `internal/ta/stc.go`。
2. **JSON 解析容错**：LLM 输出可能不是 100% 合法 JSON，需要做容错处理（去除 markdown 代码块标记 ` ```json `，尝试 `json.loads`，失败返回默认值）。
3. **衍生品数据缺失处理**：回测中某些时间段 OKX API 可能无数据（如早期），Mechanics Agent 的 `missing` 字段要如实标记，Agent 提示词已要求保守处理。
4. **Token 控制**：Brale 做了大量裁剪（删冗余字段、枚举替代数值）。预处理时必须裁剪后再喂 LLM。
5. **多时间框架**：Indicator 和 Structure 都应该输入多个周期数据（如 5m/15m/1h），让 LLM 判断跨周期一致性。这对应了 Brale 的 `multi_tf` 和 `blocks` 设计。
