# Agents 模块 — brale-core 多智能体分析系统

## 模块职责

基于 brale-core 架构的多智能体协作系统，负责技术指标压缩、市场结构分析、衍生品机制分析、形态检测和 Fusion 共识决策。

## 架构

```
agents/
├── agent_state.py              # LangGraph 状态定义
├── preprocessing/              # 压缩 + 状态分类（规则计算，无 LLM）
│   ├── indicator_compress.py   # 10 个指标的压缩快照 (EMA/RSI/ATR/OBV/STC/BB/CHOP/StochRSI/Aroon/TD)
│   ├── indicator_state.py      # 指标确定性状态分类 (trend/momentum/vol/bias/events/cross-TF)
│   ├── structure_compress.py   # 结构压缩 (fractal/candidates/SuperTrend/SMC/recent_candles/break_events)
│   ├── mechanics_compress.py   # 衍生品数据压缩 (OI/费率/多空比/CVD/清算)
│   ├── mechanics_state.py      # 机制确定性状态分类 (OI/funding/crowding/liquidation/sentiment/conflicts)
│   ├── fusion.py               # 加权共识 (Structure=1.0 Indicator=0.7 Mechanics=0.5 阈值0.35/0.52)
│   └── pattern/                # 形态检测（规则计算，无 LLM）
│       ├── geometry.py         # 10 种几何形态 (头肩/双顶底/三角/楔形/通道)
│       ├── cdl.py              # 8 种蜡烛图形态 (十字星/吞没/穿刺/三兵/黄昏星)
│       └── evidence.py         # 合并过滤引擎 (MinScore=100 Top3)
├── brale_indicator_agent.py    # Indicator Agent LLM — 技术指标分析
├── brale_structure_agent.py    # Structure Agent LLM — 市场结构分析
├── brale_mechanics_agent.py    # Mechanics Agent LLM — 衍生品机制分析
└── decision/                   # 旧版决策智能体（已弃用，保留兼容）
    ├── core_decision.py
    ├── decision_agent_original.py
    ├── decision_agent_factory.py
    └── decision_configs.py
```

## 数据流

```
MarketDataService
  ├── get_ohlcv_data()         → OHLCV K线
  └── fetch_*_derivatives()    → 衍生品数据 (OI/费率/多空比/清算)

graph_setup.py (LangGraph)
  │
  ├── [compress] ────────────────────────────────────────
  │   ├── compress_indicator()    → indicator_compressed
  │   │   └── indicator_state.enrich() → +trend/momentum/vol/bias/events
  │   ├── compress_structure()    → structure_compressed
  │   │   └── +SuperTrend +SMC +recent_candles +key_levels +break_events +pattern
  │   └── compress_mechanics()    → mechanics_compressed
  │       └── mechanics_state.enrich() → +oi_state/funding_state/crowding/liquidation/conflicts
  │
  ├── [agents] (并行) ────────────────────────────────────
  │   ├── brale_indicator_agent   → IndicatorSummary
  │   ├── brale_structure_agent   → StructureSummary
  │   └── brale_mechanics_agent   → MechanicsSummary
  │
  └── [fusion] ─────────────────────────────────────────
      └── compute_consensus()     → {direction, score, confidence, agreement, resonance}
```

## 关键参数

| 参数 | 值 |
|------|-----|
| EMA Fast/Mid/Slow | 21/50/200 |
| RSIPeriod/ATRPeriod | 14/14 |
| STC Fast/Slow | 23/50 |
| BB Period/Mult | 20/2.0 |
| CHOP/StochRSI/Aroon | 14/14/25 |
| FractalSpan | 2 |
| SuperTrend Period/Mult | 14/2.5 |
| Fusion Weights | Structure=1.0 Indicator=0.7 Mechanics=0.5 |
| Score/Confidence 阈值 | 0.35/0.52 |
| ResonanceBonusCap | 0.12 |
| Pattern MinScore/MaxDetected | 100/3 |

## 运行命令

```bash
# 后端测试
cd backend && python -m pytest tests/ -x -q

# 启动
python launch.py
```

## 与 brale-core 对齐状态

| 层 | 状态 |
|----|------|
| 压缩 (indicator/structure/mechanics) | ✅ 对齐 |
| 状态分类 (indicator_state/mechanics_state) | ✅ 对齐 |
| Agent LLM (3 个 summary) | ✅ 对齐 |
| Fusion 共识 | ✅ 对齐 |
| Pattern 形态检测 (18 种) | ✅ 对齐 |
| SuperTrend + SMC + BreakEvents | ✅ 对齐 |
| Provider 复核层 | ❌ 不需要（仅预测方向） |
| Risk/Gate/HardGuard | ❌ 不需要（仅预测方向） |
