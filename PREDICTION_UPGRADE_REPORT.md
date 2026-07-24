# 预测系统优化报告：制度识别 + 决策路由 + 规则化弃权

## 一、背景与问题

本系统用于预测下 1-2 根 K 线走向，四个智能体（Indicator / Pattern / Trend / Decision）协同工作。大量回测后发现**准确率仅约 50%，等同随机**，且表现出三个症状：

1. 无论换什么模型（GPT / Claude 等），准确率都上不去；
2. 连续分析模式下（如 4h）经常连续预测同一方向，导致连续亏损；
3. 引入置信度过滤后，可交易机会骤减，但正确率并未提高。

## 二、根因诊断（基于代码证据）

| 症状 | 根因 |
| :--- | :--- |
| 换模型无效 | 决策端只吃三段**自然语言报告**，从未见过任何数值；指标算出来又被写成散文丢弃。信息严重衰减，模型能力无从发挥。 |
| 连续同向亏损 | 原 Prompt 规定"震荡/信号混乱时默认跟随趋势线斜率"→ 系统在震荡市**永远顺势**，而震荡市是均值回归的，必然被反复打脸。相邻窗口特征高度自相关，进一步放大连亏。 |
| 置信度过滤无效 | LLM 自报的高/中/低置信度**从未被校准**，只是语气自信，与真实方向优势无关。 |

> 结论：50% 是**结构性**问题（预测目标近随机 + 永远顺势 + 决策端无数字 + 无校准弃权），不是靠换模型或调 Prompt 措辞能解决的。

## 三、优化方案

主线：**从"每根 K 线都被迫赌方向"改成"先识别市场状态 → 只在有优势的状态下、按状态选打法下注"。**

- **L1 制度识别路由** —— 治「连续同向亏损」
- **L2 决策端喂数字** —— 治「换模型都没用」
- **L4 规则化弃权** —— 治「置信度过滤无效」
- **L3 状态记忆（已砍）** —— 与"随时分析、每次独立"的核心理念冲突，且连亏问题由 L1 已从根上解决，无需记忆。

关键设计：整套方案**只修改 Decision 一个智能体**。L1 用一个确定性节点把制度判定 + 全部结构化数字 + edge 打分算好写入 state，Decision 消费它即可。全程**单次、无状态**。

## 四、具体实现

### L1：确定性制度识别（不含任何 LLM）

- **新增** `backend/app/utils/regime.py`
  - 输入 OHLCV，计算：ADX、EMA20 斜率、ATR 及其分位、布林带宽、收益一阶自相关、支撑/阻力与区间位置、RSI、MACD 柱值及斜率。
  - 输出：
    - `regime`：`TREND_UP / TREND_DOWN / RANGE / HIGH_VOL / UNKNOWN`
    - `recommended_bias`：`FOLLOW_UP / FOLLOW_DOWN / FADE / ABSTAIN`
    - `suggested_direction`：`LONG / SHORT / NONE`
    - `edge_score`：0~1 优势打分（供 L4 弃权）
    - `features`：结构化数值字典（供 L2）
    - `report`：LLM 可读的结构化文本
  - 兼容单周期（list[dict] / DataFrame）与多周期（dict[tf→data]）；数据不足或异常时安全降级为 `UNKNOWN`。
  - 分类逻辑：ADX≥25 且有明确斜率 → 趋势；ATR 占价过高且非趋势 → 高波动无结构（观望）；其余非趋势非混沌 → **区间（默认反手 FADE）**。

- **修改** `backend/app/agents/agent_state.py`
  - 新增 state 键：`regime / regime_bias / regime_direction / edge_score / regime_features / regime_report`。

- **修改** `backend/app/core/graph_setup.py`
  - 新增确定性节点 **Regime Analyzer**，位于 `Sequential Coordinator` 之后、`Decision Maker` 之前。
  - 流程变为：`START → Sequential Coordinator → Regime Analyzer → Decision Maker → END`。
  - 该节点只向 state 注入制度信息；计算失败时降级为 UNKNOWN，不影响主流程。

### L2 + L4：Decision 智能体（唯一被修改的 AI 智能体）

- **修改** `backend/app/agents/decision/decision_agent_original.py`
  - 重写 Prompt 模板：
    - 注入制度上下文（`regime / regime_direction / edge_score / regime_report`，含全部数字）。
    - **制度路由规则**：`TREND_UP/DOWN` → 顺势；`RANGE` → 按区间位置反手（近阻力空、近支撑多，明确禁止追随最近一波）；`HIGH_VOL / UNKNOWN` → 观望。
    - **解除"禁止 HOLD"**，改为按 edge 弃权。
    - 输出 JSON 扩展：新增 `market_environment / volatility_assessment / confidence_level / stop_loss / take_profit`，兼容前端展示。

- **修改** `backend/app/agents/decision/core_decision.py`
  - 从 state 读取 regime 字段并传入 Prompt 渲染。
  - 新增 **确定性 edge 硬门槛** `_apply_edge_gate()`：当 `edge_score < EDGE_ABSTAIN_THRESHOLD`（默认 0.25）或制度为 `HIGH_VOL / UNKNOWN` 时，将方向性决策**强制改为 HOLD**（只降级、绝不凭空造交易）。这是 L4 的真正执行点——规则化、不依赖 LLM 自觉。

## 五、验证情况

- ✅ `py_compile` 编译全部通过；`trading_engine` 导入链正常。
- ✅ `regime.py` 单测：趋势 / 震荡 / 高波动 / 多周期 / None / 空 / 小写字段 —— 分类正确、`edge_score ∈ [0,1]`、不崩。
- ✅ edge 门槛单测：低 edge→HOLD、高 edge→不变、HIGH_VOL→HOLD、已 HOLD 不重复、解析失败安全降级。
- ✅ Prompt 模板渲染无占位符残留，JSON 花括号正确还原。
- ✅ 前端 `DecisionPanel` 与 `trading_engine` 解析层已兼容 HOLD 及新增字段。
- ⚠️ 端到端实跑需要实盘 LLM Key，未在离线环境执行。

## 六、可调参数（均已集中为常量）

| 参数 | 位置 | 默认值 | 作用 |
| :--- | :--- | :--- | :--- |
| `EDGE_ABSTAIN_THRESHOLD` | `core_decision.py` | `0.25` | 弃权松紧；HOLD 太多可下调到 0.15~0.20 |
| `ADX_TREND` / `ADX_RANGE` | `regime.py` | `25 / 20` | 趋势 vs 区间的判定边界 |
| `ATR_HIGH_PCT` | `regime.py` | `3.0` | 高波动无结构（观望）阈值 |
| `RANGE_NEAR_BOUNDARY` | `regime.py` | `0.30` | 区间反手的边界邻近度 |
| `EMA_SLOPE_MIN_PCT` | `regime.py` | `0.03` | 趋势方向的最小斜率 |

## 七、下一步

1. 启动后跑一批 4h 回测，重点观察：**区间样本的连亏是否消失**、HOLD 占比是否合理。
2. 若 HOLD 过多，下调 `EDGE_ABSTAIN_THRESHOLD`；若趋势/区间误判，微调 ADX 阈值。
3. 后续可在验证集上按**扣费后期望值**系统性标定各阈值。

## 八、注意事项

- 本次**未改动** `tools/prompt_tuning/auto_optimizer.py`（该工具存在过拟合与 HOLD 刷分等设计问题，按约定不动）。它使用旧模板、无 regime，回测时 Prompt 中会残留一个字面量 `{regime_report}`（不会崩，仅为无效文本）。
- `decision_agent_lite.py` 未改；由于 edge 门槛位于共用的 `core_decision.py`，lite 版本也会继承该弃权逻辑（行为一致）。
