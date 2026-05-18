# Draft: 实时模拟交易功能

## 用户需求
- 开发实时模拟交易功能
- 不需要真实下单，仅模拟
- 基于现有 QuantAgent 多智能体分析系统

## 待确认事项
- 模拟交易的粒度？（逐根K线 / 实时tick / 固定时间间隔）
- 资金管理策略？（固定仓位 / 凯利公式 / 自定义）
- 需要哪些模拟指标？（胜率、盈亏比、最大回撤、夏普比率等）
- 前端展示需求？
- 是否需要与回测结果对比？

## 技术决策
（待讨论）

## 范围边界
- INCLUDE: 定时轮询、全自动模拟、可配置策略、Polymarket二元结算、断点恢复、数据持久化、独立前端、独立后端模块
- EXCLUDE: 真实下单执行、接通Polymarket API

## 已确认决策
- **数据获取**: 定时轮询（每根K线收盘触发）
- **触发模式**: 全自动 + 可暂停/查看/重启
- **结算机制**: 固定K线收盘结算（入场价 vs N根K线后收盘价，判断方向）
- **资金模拟**: 完整模式（杠杆、滑点、手续费等）
- **Polymarket模式**: 二元结果（对=赢赌注，错=输赌注），不是按涨跌幅比例
- **配置存储**: SQLite + 前端可视化配置面板
- **暂停行为**: 可选模式（暂停时选择：平仓 / 保留持仓）
- **独立文件夹**: 后端 `backend/app/simulation/`，前端独立目录
- **断点恢复**: 状态持久化，重启后从断点继续

## 技术栈确认
- **定时调度**: APScheduler (AsyncIOScheduler)，和 FastAPI 同进程
- **数据库**: SQLite + SQLAlchemy 2.0 + aiosqlite（异步驱动）
- **实时推送**: SSE (Server-Sent Events)，后端 → 前端单向状态推送
- **前端图表**: Lightweight Charts (TradingView)，金融图表专用
- **配置校验**: 后端 Pydantic v2 + 前端 Zod（前后端各一份）
- **前端状态**: Zustand（复用现有模式）
- **前端框架**: React + Vite + TypeScript（复用现有）
- **并发支持**: 多会话独立 asyncio Task 并行，SQLite WAL 模式
- **分析数据**: 新增 analysis_records 表，完整记录每次分析的原始数据、压缩输出、Agent LLM 全文、Fusion 结果
- **数据关联**: analysis_record → trade (1:0..1)，完整可追溯

## 探索发现（代码分析）

### 1. 现有回测架构
- **批量回测**：`tools/batch_backtest_app/` — daemon 读取任务队列 → 调用 /analyze API → 写入 CSV
- **CSV 字段**：`OUTPUT_FIELDNAMES` 包含 67 个字段（ai_decision, is_correct_1/2, profit_pct, 资金_当前, 下单金额, 合约倍数, 滑点, 名义金额, 各Agent分数等）
- **分析工具**：Streamlit app (`backtest_analyzer.py`) 10 个 Tab，Tab 9 是"交易模拟"（事后可视化）
- **交易模拟 Tab**：`tabs_simulation_custom.py` — 读取 CSV 资金曲线，计算总收益率、最大回撤、夏普比率、盈亏比

### 2. API 架构
- **唯一分析端点**：`POST /api/v1/analyze/` — 支持 data_method: "latest"（最新数据）和 "date_range"（回测模式）
- **AnalyzeRequest**：asset, timeframe, data_method, kline_count, future_kline_count, date_range, llm_config
- **AnalyzeResponse**：包含 indicator/structure/mechanics/fusion 四块结果 + metadata
- **LangGraph 工作流**：compress_indicators → compress_structure → compress_mechanics → parallel LLM agents → fusion → 产出 analysis result

### 3. 市场数据
- **数据源**：OKX v5 REST API（market_data.py）
- **OHLCV**：支持多时间框架、历史 after 翻页
- **衍生品**：OI、资金费率、多空比、Taker量（部分固定窗口限制）
- **无 WebSocket / 实时流**

### 4. 前端架构
- **入口**：App.tsx — 条件渲染 AnalysisForm（输入） / AnalysisResult（结果）
- **表单**：AnalysisForm → AssetAndTimeframePanel + ConfigPanel + "开始分析"按钮
- **结果**：AnalysisResult → SummaryPanel + DecisionPanel + IndicatorPanel + PatternPanel + TrendPanel
- **状态管理**：Zustand store (useAppStore) — analysisResult, history, config, llmConfig
- **API 调用**：fetch 直接调 backend，无 WebSocket
