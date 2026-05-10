# QuantAgent — brale-core 多智能体市场分析系统

基于 brale-core 架构的加密货币技术分析系统，支持多时间框架的指标压缩、结构分析、衍生品机制分析和 Fusion 共识决策。
我这个项目只是为了预测下1-2根k线的方向！！！
## 项目结构

```
Refactor_v2/
├── backend/                        # Python FastAPI 后端
│   ├── app/
│   │   ├── agents/
│   │   │   ├── preprocessing/      # 压缩 + 状态分类（纯规则计算，无 LLM）
│   │   │   │   ├── indicator_compress.py   # 10 指标压缩快照
│   │   │   │   ├── indicator_state.py      # 指标确定性状态分类
│   │   │   │   ├── structure_compress.py   # 结构压缩 (fractal/SuperTrend/SMC)
│   │   │   │   ├── mechanics_compress.py   # 衍生品数据压缩
│   │   │   │   ├── mechanics_state.py      # 机制确定性状态分类
│   │   │   │   ├── fusion.py               # 加权共识
│   │   │   │   └── pattern/                # 形态检测 (18 种)
│   │   │   │       ├── geometry.py         # 10 种几何形态
│   │   │   │       ├── cdl.py              # 8 种蜡烛图形态
│   │   │   │       └── evidence.py         # 合并过滤引擎
│   │   │   ├── brale_indicator_agent.py    # Indicator Agent LLM
│   │   │   ├── brale_structure_agent.py    # Structure Agent LLM
│   │   │   ├── brale_mechanics_agent.py    # Mechanics Agent LLM
│   │   │   ├── agent_state.py              # LangGraph 状态定义
│   │   │   └── decision/                   # 旧版决策智能体（弃用，保留兼容）
│   │   ├── api/v1/endpoints/analyze.py     # 分析 API 端点
│   │   ├── core/
│   │   │   ├── graph_setup.py              # LangGraph 工作流定义
│   │   │   └── config.py                   # 配置管理
│   │   ├── services/
│   │   │   ├── market_data.py              # OKX v5 市场数据 + 衍生品数据
│   │   │   └── trading_engine.py           # 交易引擎编排
│   │   ├── main.py                         # FastAPI 入口
│   │   └── utils/                          # 工具函数
│   ├── tests/
│   │   └── test_brale_modules.py           # 41 个 brale 模块测试
│   └── .env.example                        # 环境变量模板
├── frontend/                               # React + Vite 前端
│   └── src/
│       ├── components/
│       │   ├── SummaryPanel.tsx             # 摘要 + Fusion 共识
│       │   ├── DecisionPanel.tsx            # Fusion 共识详情
│       │   ├── IndicatorPanel.tsx           # 指标分析结果
│       │   ├── PatternPanel.tsx             # 结构分析结果
│       │   ├── TrendPanel.tsx               # 机制分析结果
│       │   ├── ConfigPanel.tsx              # LLM 配置面板
│       │   └── AnalysisForm.tsx             # 分析请求表单
│       ├── types/index.ts                   # 类型定义
│       ├── api/system.ts                    # API 调用
│       └── store/useAppStore.ts             # 状态管理
└── launch.py                                # 一键启动 (backend + frontend)
```

## 架构数据流

```
┌─────────────────────────────────────────────────────────┐
│                    OKX v5 Market Data                    │
│  OHLCV K线 │ OI │ 资金费率 │ 多空比 │ Taker量 │ 清算数据   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  [compress] LangGraph 压缩节点（纯规则计算）                │
│                                                          │
│  ┌─────────────────┐  ┌──────────────────┐               │
│  │ compress_indicator │  │ compress_structure │            │
│  │  10 指标快照       │  │ fractal/candidates │            │
│  │  ↓ enrich          │  │ SuperTrend/SMC     │            │
│  │  indicator_state   │  │ key_levels/breaks  │            │
│  │  trend/moment/vol  │  │ pattern/evidence   │            │
│  └────────┬──────────┘  └─────────┬─────────┘            │
│           │                       │                      │
│  ┌────────┴──────────┐            │                      │
│  │ compress_mechanics │            │                      │
│  │  OI/费率/多空比     │            │                      │
│  │  ↓ enrich          │            │                      │
│  │  mechanics_state   │            │                      │
│  │  funding/crowding  │            │                      │
│  └────────┬───────────┘            │                      │
└───────────┼────────────────────────┼──────────────────────┘
            ▼                        ▼
┌──────────────────────────────────────────────────────────┐
│  [agents] 并行 LLM 分析                                   │
│  ┌────────────┐  ┌───────────┐  ┌──────────────┐         │
│  │ Indicator  │  │ Structure │  │  Mechanics   │         │
│  │   Agent    │  │   Agent   │  │    Agent     │         │
│  └─────┬──────┘  └─────┬─────┘  └──────┬───────┘         │
└────────┼───────────────┼───────────────┼─────────────────┘
         ▼               ▼               ▼
┌──────────────────────────────────────────────────────────┐
│  [fusion] 加权共识                                        │
│  Structure(1.0) + Indicator(0.7) + Mechanics(0.5)        │
│  → direction / score / confidence / resonance             │
└──────────────────────────────────────────────────────────┘
```

## 智能体说明

| Agent | 输入 | 输出 |
|-------|------|------|
| **Indicator Agent** | 10 个指标压缩 + trend/momentum/vol/bias/events 状态标签 | `expansion` `alignment` `noise` `movement_score` |
| **Structure Agent** | fractal/candidates/SuperTrend/SMC/key_levels/break_events/recent_candles/pattern | `regime` `last_break` `quality` `pattern` `volume_action` |
| **Mechanics Agent** | OI/费率/多空比/CVD/清算 + oi/funding/crowding/liquidation/sentiment/conflicts 状态标签 | `leverage_state` `crowding` `risk_level` |
| **Fusion（非LLM）** | 3 个 Agent 的 summary | `direction` `score` `confidence` |

## 关键技术参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| EMA Fast/Mid/Slow | 21 / 50 / 200 | 趋势判断 |
| RSI Period | 14 | 动量 |
| ATR Period | 14 | 波动率 |
| STC Fast/Slow | 23 / 50 | 趋势周期 |
| BB Period/Mult | 20 / 2.0 | 布林带 |
| FractalSpan | 2 | 分形检测跨度 |
| SuperTrend P/M | 14 / 2.5 | 趋势跟踪 |
| Fusion 权重 | S=1.0 I=0.7 M=0.5 | 加权共识 |
| Score 阈值 | 0.35 | 方向信号阈值 |
| Confidence 阈值 | 0.52 | 置信度阈值 |
| ResonanceBonusCap | 0.12 | 共振奖励上限 |

## 形态检测

18 种形态，纯规则计算，不调用 LLM：

| 来源 | 形态 | 分数 |
|------|------|------|
| geometry | head_shoulders / inv_head_shoulders | ±150 |
| geometry | double_top / double_bottom | ±120 |
| geometry | wedge_rising / wedge_falling | ±120 |
| geometry | triangle_asc / triangle_desc / channel_up / channel_down | ±100 |
| candle | doji / doji_star / piercing / three_inside / three_outside | ±100 |
| candle | three_black_crows / three_white_soldiers / evening_star | ±100 |

合并后按 MinScore=100 过滤、按强度排序、取 Top 3。

## 运行

```bash
# 启动（需要 Node.js + Python 环境）
python launch.py

# 后端测试
cd backend && python -m pytest tests/ -x -q

# 前端构建
cd frontend && npm run build
```

## 环境变量 (.env)

```bash
# LLM 配置
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-xxx
LLM_TIMEOUT=60

# 3 个 Agent 独立配置
BRALE_INDICATOR_PROVIDER=deepseek
BRALE_INDICATOR_MODEL=deepseek-chat
BRALE_INDICATOR_TEMPERATURE=0.2

BRALE_STRUCTURE_PROVIDER=deepseek
BRALE_STRUCTURE_MODEL=deepseek-chat
BRALE_STRUCTURE_TEMPERATURE=0.1

BRALE_MECHANICS_PROVIDER=deepseek
BRALE_MECHANICS_MODEL=deepseek-chat
BRALE_MECHANICS_TEMPERATURE=0.2

# 市场数据代理
MARKET_DATA_API_URL=https://webui.caomaowu.lol
MARKET_DATA_API_TOKEN=xxx
MARKET_DATA_API_VERSION=v5
OKX_INSTRUMENT_TYPE=SWAP
```

## 与 brale-core 对齐状态

| 层 | 状态 |
|----|------|
| 压缩 (indicator/structure/mechanics) | ✅ |
| 状态分类 (indicator_state/mechanics_state) | ✅ |
| Agent LLM (3 个 summary) | ✅ |
| Fusion 共识 | ✅ |
| Pattern 形态检测 (18 种) | ✅ |
| SuperTrend + SMC + BreakEvents | ✅ |
| Provider 复核层 | ❌ 不需要（仅预测方向） |
| Risk/Gate/HardGuard | ❌ 不需要（仅预测方向） |

## 回测衍生品数据对齐策略

OKX rubik 衍生品端点仅返回固定窗口数据（不支持 after 翻页）：

| 衍生品 | 回溯窗口 | 说明 |
|--------|:--------:|------|
| OI 历史 | 30 天 | 1H 粒度 720 条 |
| 多空比 | 30 天 | 1H 粒度 720 条 |
| Taker 量 | ~4 天 | 1H 粒度 100 条 |
| 资金费率 | ~3 个月 | ✅ 唯一支持 after 翻页 |

回测时系统自动处理：
- **衍生品数据能覆盖回测日期** → 用 K 线时间窗切片对齐
- **不能覆盖** → 标 `missing=True`，LLM 知情
- 无需手动配置，无需建数据库
