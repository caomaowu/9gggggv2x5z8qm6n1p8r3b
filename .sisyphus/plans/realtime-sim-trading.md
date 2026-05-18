# 实时模拟交易系统 — 工作规划

## TL;DR

> **Quick Summary**: 为 QuantAgent 系统新增独立的实时模拟交易模块，Polymarket 二元赌注模式，全自动定时轮询 + 可配置策略 + 多会话并发 + 断点恢复 + 完整数据记录。
>
> **Deliverables**:
> - 后端 `backend/app/simulation/` 模块（7 个文件）
> - 前端 `frontend/src/simulation/` 模块（12+ 文件）
> - SQLite 数据库 5 张表
> - REST API 12 个端点 + SSE 实时推送
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 4 Waves
> **Critical Path**: 数据层 → 引擎 → API → 前端面板 → 集成测试

---

## Context

### Original Request
用户希望在现有 QuantAgent 多智能体分析系统上，开发实时模拟交易功能。不需要真实下单，仅模拟 Polymarket 风格的二元预测赌注（方向对了赢赌注、方向错了输赌注）。要求独立前端、可配置策略、多任务并发、断点恢复、完整数据记录和历史回溯查看。

### Interview Summary
**Key Discussions**:
- **数据获取**: 定时轮询（APScheduler），每根 K 线收盘触发，不用 WebSocket
- **触发模式**: 全自动 + 可暂停/查看/重启，支持多会话并发
- **结算方式**: 固定 K 线收盘结算（入场价 vs N 根后收盘价判定方向对错）
- **资金模拟**: 完整模式（固定金额/百分比/凯利公式三种下注方式可选）
- **配置存储**: SQLite + SQLAlchemy async + 前端可视化配置面板
- **实时推送**: SSE 单向推送状态变更
- **图表**: Lightweight Charts (TradingView)
- **断点恢复**: 每根 K 线处理后存 checkpoint，重启自动恢复
- **历史查看**: 点击 analysis_records 列表项可展示完整分析结果
- **测试**: 引擎核心逻辑单元测试，前端手动验证

**Research Findings**:
- 现有分析管道（compress → 3 agents → fusion）可直接复用，零改动
- `market_data.py` OKX v5 REST API 可直接复用
- 现有回测系统（batch_backtest）的 CSV 字段设计可参考
- 前端 AnalysisResult 组件可复用于历史记录查看
- 项目无现有 WebSocket 基础设施，SSE 更轻量合适

---

## Work Objectives

### Core Objective
在现有 QuantAgent 系统中新增独立的实时模拟交易模块，复用分析管道能力，实现 Polymarket 风格的自动模拟交易。

### Concrete Deliverables
- `backend/app/simulation/` — 完整后端模块（models, schemas, repository, engine, manager, scheduler, sse, routes）
- `frontend/src/simulation/` — 完整前端模块（策略管理、会话控制、实时看板、历史查看）
- `backend/app/simulation.db` — SQLite 数据库自动创建
- REST API: `/api/v1/sim/*` 12 个端点 + 1 个 SSE 流
- 引擎单元测试覆盖开仓/平仓/结算/资金计算

### Definition of Done
- [ ] 创建策略 → 启动会话 → K 线收盘自动分析 → 满足条件自动开仓 → 到期自动结算 → 前端实时看到资金变化
- [ ] 暂停会话 → 可选平仓/保留持仓 → 恢复后正常运行
- [ ] 杀掉进程 → 重启 → 会话自动从 checkpoint 恢复
- [ ] 3 个会话同时跑不同币种/周期，互不干扰
- [ ] 点击历史分析记录 → 展示完整 AnalysisResult
- [ ] `pytest backend/tests/test_simulation_engine.py -q` → PASS

### Must Have
- 完整分析数据记录（analysis_records 表：原始数据→压缩→Agent→Fusion→决策）
- 断点恢复（checkpoint 机制）
- 多会话并发（独立 asyncio Task）
- 策略 JSON 可配置（入场/下注/结算/风控四大类）
- SSE 实时推送
- Polymarket 二元盈亏计算

### Must NOT Have (Guardrails)
- 不修改现有分析管道代码（agents/、core/graph_setup.py、services/market_data.py）
- 不修改现有前端分析页面（AnalysisForm、AnalysisResult）
- 不接入真实交易所下单
- 不接入 Polymarket API
- 不做 WebSocket（用 SSE）
- 不做分布式/微服务（单进程 FastAPI + APScheduler）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES（pytest + FastAPI TestClient）
- **Automated tests**: 核心引擎单元测试
- **Framework**: pytest + pytest-asyncio
- **QA**: 每任务含 Agent-Executed QA Scenarios（curl + 前端 Playwright）

### QA Policy
- **API**: Bash (curl) — 发送请求，断言状态码和响应字段
- **前端/UI**: Playwright — 导航、填写表单、点击按钮、断言 DOM
- **引擎**: pytest — 单元测试覆盖开仓/平仓/结算/资金/风控逻辑
- 证据保存到 `.sisyphus/evidence/`

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — 数据层 + 基础定义, 7 tasks):
├── T1: SQLAlchemy 数据模型 (models.py)
├── T2: Pydantic Schema + 策略校验 (schemas.py)
├── T3: Repository 数据访问层 (repository.py)
├── T4: TypeScript 类型定义 (types/simulation.ts)
├── T5: 前端 API 客户端 (api/simulation.ts)
├── T6: SSE 事件管理器 (sse.py)
└── T7: 策略配置表单 (StrategyForm.tsx)

Wave 2 (After Wave 1 — 核心引擎 + API, 6 tasks):
├── T8: 模拟交易引擎 (engine.py) — 核心
├── T9: 会话管理器 (manager.py)
├── T10: APScheduler 调度器 (scheduler.py)
├── T11: REST API 路由 (routes.py)
├── T12: Zustand 状态管理 (simulationStore.ts)
└── T13: SSE 前端 Hook (useSSE.ts)

Wave 3 (After Wave 2 — 前端面板 + 集成, 6 tasks):
├── T14: 策略管理面板 (StrategyPanel.tsx)
├── T15: 会话控制面板 (SessionPanel.tsx)
├── T16: 实时看板 (LiveDashboard.tsx)
├── T17: 资金曲线图 (CapitalChart.tsx)
├── T18: 持仓+交易历史+信号日志+分析记录查看
└── T19: 主入口 + 路由注册 (SimulationApp + main.py)

Wave 4 (After Wave 3 — 测试 + 验证, 3 tasks):
├── T20: 引擎单元测试
├── T21: API 集成测试
└── T22: 前端 E2E 冒烟测试

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: 规划合规审计 (oracle)
├── F2: 代码质量审查 (unspecified-high)
├── F3: 手工 QA 执行 (unspecified-high + playwright)
└── F4: 范围一致性检查 (deep)

Critical Path: T1 → T8 → T11 → T15 → T16 → T19 → T20 → F1-F4
Max Concurrent: 7 (Wave 1)
```

---

## TODOs

- [ ] 1. SQLAlchemy 数据模型 (models.py)

  **What to do**:
  - 创建 `backend/app/simulation/models.py`
  - 定义 5 张表的 SQLAlchemy ORM 模型：`Strategy`, `SimulationSession`, `Trade`, `AnalysisRecord`, `CapitalSnapshot`
  - Strategy 表：`entry_config`, `bet_config`, `settle_config`, `risk_config` 四个 JSON 列
  - SimulationSession 表：`checkpoint_data` JSON 列用于断点恢复
  - AnalysisRecord 表：完整分析快照，JSON 列存 `ohlcv_json`, `derivatives_json`, `indicator_compress`, `indicator_state`, `structure_compress`, `mechanics_compress`, `mechanics_state`, `patterns_json`, `agent_directions`；TEXT 列存 `indicator_summary`, `structure_summary`, `mechanics_summary`
  - Trade 表：关联 `analysis_record_id` (FK) 和 `session_id` (FK)
  - CapitalSnapshot 表：关联 `session_id` (FK)，记录每个 K 线收盘时的资金和回撤
  - 所有表含 `created_at`, `updated_at` 时间戳
  - 添加 `Base.metadata.create_all` 初始化函数

  **Must NOT do**:
  - 不要创建 alembic 迁移（直接 create_all 即可，SQLite 无需迁移）
  - 不要定义外键约束（SQLite 默认不强制，用应用层保证）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯数据模型定义，无复杂业务逻辑
  - **Skills**: []
  - **Skills Evaluated but Omitted**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2, T3, T4, T5, T6, T7)
  - **Blocks**: T8, T9, T11
  - **Blocked By**: None

  **References**:
  - `backend/app/agents/agent_state.py` — 参考现有 TypedDict 状态定义的数据结构
  - `tools/batch_backtest_app/core.py:OUTPUT_FIELDNAMES` — 参考已有回测 CSV 的字段命名和含义

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/models.py` 文件存在，含 5 个 ORM 类
  - [ ] `python -c "from backend.app.simulation.models import Base, Strategy, SimulationSession, Trade, AnalysisRecord, CapitalSnapshot"` 无 ImportError
  - [ ] `Base.metadata.create_all` 能成功创建 simulation.db

  **QA Scenarios**:
  ```
  Scenario: 数据库初始化成功
    Tool: Bash
    Steps:
      1. cd backend && python -c "from app.simulation.models import init_db; import asyncio; asyncio.run(init_db('sqlite+aiosqlite:///./app/simulation.db'))"
      2. python -c "import sqlite3; conn = sqlite3.connect('backend/app/simulation.db'); cursor = conn.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); print(cursor.fetchall())"
    Expected Result: 打印出 strategies, simulation_sessions, trades, analysis_records, capital_snapshots 五张表
    Evidence: .sisyphus/evidence/task-1-db-init.txt

  Scenario: JSON 列存储和读取
    Tool: Bash
    Steps:
      1. 创建一条 Strategy 记录，entry_config = {"min_fusion_score": 0.35}
      2. 读回并断言 entry_config["min_fusion_score"] == 0.35
    Expected Result: JSON 列正确序列化/反序列化
    Evidence: .sisyphus/evidence/task-1-json-col.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add SQLAlchemy models for simulation module`
  - Files: `backend/app/simulation/__init__.py`, `backend/app/simulation/models.py`

- [ ] 2. Pydantic Schema + 策略校验 (schemas.py)

  **What to do**:
  - 创建 `backend/app/simulation/schemas.py`
  - 定义策略配置的 Pydantic v2 模型：
    - `EntryConfig`: min_fusion_score(0.0-1.0), min_confidence(0.0-1.0), required_agent_agree(1-3), exclude_hold(bool), allowed_sessions(list[str]), min_pattern_score(int)
    - `BetConfig`: method(literal["fixed","percent","kelly"]), fixed_amount(float>0), percent(float 0-100), max_kelly_fraction(float 0-1), max_concurrent(int>=1), fee_rate(float>=0), slippage(float>=0)
    - `SettleConfig`: hold_klines(int 1-10), settlement_price(literal["close"])
    - `RiskConfig`: max_drawdown_pct(float 0-100), max_consecutive_loss(int>=1), min_capital(float>=0)
    - `StrategyCreate/Update/Response`: 包裹以上四个 + name, description, is_active
  - 定义 API 请求/响应 Schema：`SessionCreate`, `SessionResponse`, `TradeResponse`, `AnalysisRecordResponse`, `CapitalSnapshotResponse`, `SSEEvent`
  - 所有 Schema 用 `model_config = {"from_attributes": True}` 支持 ORM 转换

  **Must NOT do**:
  - 不要在前端校验逻辑写在后端 schema 里（schema 只管后端校验）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Schema 定义，无复杂逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T3, T4, T5, T6, T7)
  - **Blocks**: T8, T11
  - **Blocked By**: None

  **References**:
  - `backend/app/api/v1/endpoints/analyze.py` — 参考现有 AnalyzeRequest/Response 的 Pydantic 写法
  - `tools/batch_backtest_app/core.py:OUTPUT_FIELDNAMES` — 参考已有字段名和含义

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/schemas.py` 存在，含所有 Pydantic 模型
  - [ ] `StrategyCreate(entry_config={"min_fusion_score": 1.5})` 抛出 ValidationError（分数超范围）
  - [ ] `StrategyCreate(entry_config={"min_fusion_score": 0.35}).model_dump()` 成功

  **QA Scenarios**:
  ```
  Scenario: 策略配置校验 — 合法输入
    Tool: Bash (python -c)
    Steps:
      1. from app.simulation.schemas import StrategyCreate, EntryConfig, BetConfig, SettleConfig, RiskConfig
      2. s = StrategyCreate(name="test", entry_config=EntryConfig(min_fusion_score=0.4), bet_config=BetConfig(method="fixed", fixed_amount=100), settle_config=SettleConfig(hold_klines=1), risk_config=RiskConfig())
      3. print(s.model_dump())
    Expected Result: 正常序列化，无异常
    Evidence: .sisyphus/evidence/task-2-valid.txt

  Scenario: 策略配置校验 — 非法输入
    Tool: Bash (python -c)
    Steps:
      1. s = StrategyCreate(name="test", entry_config=EntryConfig(min_fusion_score=9.9), ...)
      2. 断言抛出 pydantic.ValidationError
    Expected Result: ValidationError，提示 min_fusion_score 超出范围
    Evidence: .sisyphus/evidence/task-2-invalid.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add Pydantic schemas with strategy config validation`
  - Files: `backend/app/simulation/schemas.py`

- [ ] 3. Repository 数据访问层 (repository.py)

  **What to do**:
  - 创建 `backend/app/simulation/repository.py`
  - 封装所有数据库 CRUD 操作为 async 函数
  - 使用 SQLAlchemy 2.0 async session（`AsyncSession`）
  - 提供函数：`create_strategy`, `get_strategies`, `get_strategy`, `update_strategy`, `delete_strategy`
  - 提供函数：`create_session`, `get_sessions`, `get_session`, `update_session`, `save_checkpoint`
  - 提供函数：`create_trade`, `get_trades_by_session`, `update_trade_settlement`
  - 提供函数：`create_analysis_record`, `get_analysis_records_by_session`, `get_analysis_record`
  - 提供函数：`create_capital_snapshot`, `get_capital_snapshots`
  - 所有查询支持分页（offset/limit）
  - 导出 `get_db` 依赖注入函数供 FastAPI 使用

  **Must NOT do**:
  - 不要在 repository 里写业务逻辑（只做数据存取）
  - 不要使用同步 sqlite3（统一用 aiosqlite 异步）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准 CRUD 封装，无复杂逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T4, T5, T6, T7)
  - **Blocks**: T8, T9, T11
  - **Blocked By**: T1, T2

  **References**:
  - `backend/app/services/market_data.py` — 参考现有 async 函数模式
  - SQLAlchemy 2.0 async docs: `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html`

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/repository.py` 存在，含所有 CRUD 函数
  - [ ] 每个函数都能独立调用，传入 mock session 返回正确类型

  **QA Scenarios**:
  ```
  Scenario: CRUD 完整流程
    Tool: Bash (pytest)
    Steps:
      1. 创建内存 SQLite + async session
      2. create_strategy → 断言返回的 Strategy.id 不为空
      3. get_strategies → 断言列表长度为 1
      4. update_strategy → 断言 name 已更新
      5. delete_strategy → 断言 get_strategies 返回空列表
    Expected Result: 全部断言通过
    Evidence: .sisyphus/evidence/task-3-crud.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add async repository layer`
  - Files: `backend/app/simulation/repository.py`

- [ ] 4. TypeScript 类型定义 (types/simulation.ts)

  **What to do**:
  - 创建 `frontend/src/simulation/types/simulation.ts`
  - 定义与后端 Pydantic Schema 对齐的 TypeScript 类型
  - `Strategy`, `EntryConfig`, `BetConfig`, `SettleConfig`, `RiskConfig`
  - `SimulationSession`, `Trade`, `AnalysisRecord`, `CapitalSnapshot`
  - `SSEEvent` 联合类型：`capital_update | trade_opened | trade_closed | signal_log | status_change | risk_breach`
  - `SessionStatus`: `"running" | "paused" | "stopped" | "crashed"`
  - `BetMethod`: `"fixed" | "percent" | "kelly"`
  - `Direction`: `"long" | "short"`

  **Must NOT do**:
  - 不要定义与后端不一致的字段名

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T3, T5-T7)
  - **Blocks**: T5, T12, T13
  - **Blocked By**: None

  **References**:
  - `frontend/src/types/index.ts` — 参考现有类型定义风格
  - T2 的 schemas.py 产出

  **Acceptance Criteria**:
  - [ ] `frontend/src/simulation/types/simulation.ts` 存在
  - [ ] `npx tsc --noEmit` 无类型错误

  **QA Scenarios**:
  ```
  Scenario: 类型编译检查
    Tool: Bash
    Steps:
      1. cd frontend && npx tsc --noEmit
    Expected Result: 无类型错误
    Evidence: .sisyphus/evidence/task-4-tsc.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add TypeScript types`
  - Files: `frontend/src/simulation/types/simulation.ts`

- [ ] 5. 前端 API 客户端 (api/simulation.ts)

  **What to do**:
  - 创建 `frontend/src/simulation/api/simulation.ts`
  - 封装所有 `/api/v1/sim/*` 的 fetch 调用
  - `fetchStrategies()`, `createStrategy(data)`, `updateStrategy(id, data)`, `deleteStrategy(id)`
  - `fetchSessions()`, `createSession(data)`, `startSession(id)`, `pauseSession(id, closePositions)`, `resumeSession(id)`, `stopSession(id)`
  - `fetchTrades(sessionId, offset, limit)`, `fetchAnalysisRecords(sessionId, offset, limit)`, `fetchAnalysisRecord(id)`
  - `fetchCapitalSnapshots(sessionId)`, `fetchSignals(sessionId, offset, limit)`
  - 统一错误处理（非 2xx 抛异常，含后端错误信息）
  - 使用 TypeScript 泛型标注返回类型

  **Must NOT do**:
  - 不要在 API 层做状态管理（交给 Zustand store）
  - 不要硬编码 base URL（从环境变量或默认 `/api/v1/sim`）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准 fetch 封装
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T4, T6, T7)
  - **Blocks**: T12, T14-T19
  - **Blocked By**: T4

  **References**:
  - `frontend/src/api/system.ts` — 参考现有 API 调用的封装风格和错误处理

  **Acceptance Criteria**:
  - [ ] `frontend/src/simulation/api/simulation.ts` 存在，含所有函数
  - [ ] 每个函数返回正确的 TypeScript 类型

  **QA Scenarios**:
  ```
  Scenario: API 函数类型检查
    Tool: Bash
    Steps:
      1. cd frontend && npx tsc --noEmit
    Expected Result: 无类型错误
    Evidence: .sisyphus/evidence/task-5-tsc.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add frontend API client`
  - Files: `frontend/src/simulation/api/simulation.ts`

- [ ] 6. SSE 事件管理器 (sse.py)

  **What to do**:
  - 创建 `backend/app/simulation/sse.py`
  - 实现 `SSEManager` 类：
    - `register(session_id) -> asyncio.Queue`：注册订阅者，返回事件队列
    - `unregister(session_id)`：移除订阅者
    - `publish(session_id, event: SSEEvent)`：向该会话所有订阅者推送事件
    - `broadcast(event: SSEEvent)`：向所有订阅者推送
  - 内部用 `dict[str, list[asyncio.Queue]]` 管理订阅
  - SSE 事件格式：`data: {json}\n\n`（标准 SSE 协议）
  - 支持的事件类型：`capital_update`, `trade_opened`, `trade_closed`, `signal_log`, `status_change`, `risk_breach`
  - 导出单例 `sse_manager = SSEManager()`

  **Must NOT do**:
  - 不要使用 WebSocket（仅 SSE）
  - 不要引入 Redis 或其他外部消息队列

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的发布-订阅模式实现
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T5, T7)
  - **Blocks**: T11
  - **Blocked By**: None

  **References**:
  - FastAPI SSE 示例: `https://fastapi.tiangolo.com/advanced/events/#server-sent-events`
  - asyncio.Queue 文档

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/sse.py` 存在，含 `SSEManager` 类
  - [ ] `publish` → 订阅者的 `asyncio.Queue.get()` 能收到事件

  **QA Scenarios**:
  ```
  Scenario: SSE 发布-订阅
    Tool: Bash (python -c)
    Steps:
      1. from app.simulation.sse import sse_manager
      2. queue = sse_manager.register("test_session")
      3. sse_manager.publish("test_session", {"type": "status_change", "data": {"status": "running"}})
      4. event = asyncio.run(queue.get())
      5. assert event["type"] == "status_change"
    Expected Result: 订阅者收到正确事件
    Evidence: .sisyphus/evidence/task-6-sse.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add SSE event manager`
  - Files: `backend/app/simulation/sse.py`

- [ ] 7. 策略配置表单 (StrategyForm.tsx)

  **What to do**:
  - 创建 `frontend/src/simulation/components/StrategyForm.tsx`
  - 表单分 4 个 Section：入场条件、下注参数、结算条件、风控参数
  - 入场条件：min_fusion_score(滑块 0-1, 步长 0.05), min_confidence(滑块 0-1, 步长 0.01), required_agent_agree(单选 1/2/3), exclude_hold(开关), allowed_sessions(多选 checkboxes), min_pattern_score(数字输入)
  - 下注参数：bet_method(下拉选择), fixed_amount(数字输入, 选 fixed 时显示), bet_percent(滑块 1-100, 选 percent 时显示), max_kelly_fraction(滑块 0-1, 选 kelly 时显示), max_concurrent(数字), fee_rate(百分比输入), slippage(百分比输入)
  - 结算条件：hold_klines(单选 1/2)
  - 风控参数：max_drawdown_pct(滑块 0-100), max_consecutive_loss(数字), min_capital(数字)
  - 底部按钮：[保存策略] [取消]
  - 用 Zod 做前端校验（和后端 Pydantic 规则一致）
  - 表单值受控（useState），编辑模式回填已有值

  **Must NOT do**:
  - 不要在后端未就绪时就真正调 API（先做纯前端表单，API 调用留桩）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 表单 UI 组件，需要视觉设计
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: 表单布局和交互体验

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1-T6)
  - **Blocks**: T14
  - **Blocked By**: T4

  **References**:
  - `frontend/src/components/ConfigPanel.tsx` — 参考现有配置面板的 UI 风格和表单控件
  - `frontend/src/components/AnalysisForm.tsx` — 参考表单交互模式

  **Acceptance Criteria**:
  - [ ] `StrategyForm.tsx` 存在，渲染 4 个 Section
  - [ ] bet_method 切换时，对应输入框显示/隐藏
  - [ ] 必填字段为空时 [保存策略] 按钮 disabled

  **QA Scenarios**:
  ```
  Scenario: 策略表单填写和切换
    Tool: Playwright
    Steps:
      1. 打开模拟交易页面
      2. 点击"新建策略"
      3. 填写策略名称 "Test Strategy"
      4. min_fusion_score 滑块拖到 0.4
      5. bet_method 选择 "fixed" → 断言 fixed_amount 输入框可见
      6. bet_method 切换到 "percent" → 断言 fixed_amount 隐藏, bet_percent 滑块可见
      7. 点击"保存策略" → 断言表单提交
    Expected Result: 表单正确渲染，条件显示正常
    Evidence: .sisyphus/evidence/task-7-strategy-form.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add strategy configuration form`
  - Files: `frontend/src/simulation/components/StrategyForm.tsx`

- [ ] 8. 模拟交易引擎 (engine.py) — 🔥核心

  **What to do**:
  - 创建 `backend/app/simulation/engine.py`
  - 实现 `SimulationEngine` 类，负责每根 K 线收盘后的完整处理流程
  - **入场判定** (`evaluate_entry`)：
    - 从 AnalysisRecord 中提取 fusion_direction, fusion_score, fusion_confidence, agent_directions
    - 对照策略 EntryConfig 逐条校验：分数阈值、置信度阈值、Agent 同向数、是否 hold、时段过滤
    - 检查当前 open trades 数 < max_concurrent
    - 返回 `(should_enter: bool, reject_reason: str | None)`
  - **开仓** (`open_position`)：
    - 根据 BetConfig 计算 bet_amount（fixed/percent/kelly）
    - percent: `bet_amount = current_capital * bet_percent / 100`
    - kelly: `f* = win_rate - (1-win_rate)/(avg_win/avg_loss)`，乘以 max_kelly_fraction 限制
    - 扣除手续费 `fee = bet_amount * fee_rate`
    - 创建 Trade 记录（status=open）
  - **持仓结算** (`settle_positions`)：
    - 遍历所有 open trades，检查 `current_kline_index - entry_kline_index >= hold_klines`
    - 用当前收盘价 vs entry_price 判定方向对错
    - Polymarket 二元计算：对了 `pnl = bet_amount * (1 - fee_rate)`，错了 `pnl = -bet_amount`
    - 更新 Trade 为 settled
  - **资金更新**：累计 current_capital、track running_peak、计算 drawdown
  - **风控检查** (`check_risk`)：
    - max_drawdown_pct 超标 → 自动暂停
    - max_consecutive_loss 超标 → 自动暂停
    - min_capital 低于阈值 → 自动停止
  - 导出单例或工厂函数

  **Must NOT do**:
  - 不要调用外部 API（引擎不直接调 market_data 或 agent pipeline）
  - 不要在引擎里操作 SSE 推送（由调用方 manager 负责）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 核心业务逻辑，涉及多种下注算法、风控逻辑，需要仔细设计和正确实现
  - **Skills**: []
  - **Skills Evaluated but Omitted**: 无

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential dependency)
  - **Blocks**: T9, T11, T20
  - **Blocked By**: T1, T2, T3

  **References**:
  - `tools/backtest_analyzer_app/tabs_simulation_custom.py` — 参考现有资金曲线、最大回撤、夏普比率的计算方式
  - `tools/batch_backtest_app/core.py:OUTPUT_FIELDNAMES` — 参考回测字段含义（资金_当前、本次盈亏百分比等）
  - Kelly Criterion 公式: `f* = p - q/b` 其中 p=胜率, q=1-p, b=平均赢/平均输

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/engine.py` 存在，含 `SimulationEngine` 类
  - [ ] `evaluate_entry` 在所有条件满足时返回 `(True, None)`
  - [ ] `evaluate_entry` 在 score 不够时返回 `(False, "fusion_score below threshold")`
  - [ ] `open_position` 固定金额模式计算正确
  - [ ] `settle_positions` 方向对时 pnl 为正，错时 pnl 为负
  - [ ] `check_risk` 回撤超标时返回 `"pause"`

  **QA Scenarios**:
  ```
  Scenario: 入场条件 — 全部满足
    Tool: Bash (python -c)
    Steps:
      1. 构造 AnalysisRecord: direction=bullish, score=0.5, confidence=0.6, agent_agree=3
      2. 构造 EntryConfig: min_score=0.35, min_confidence=0.52, required_agree=2
      3. engine.evaluate_entry(record, config) → (True, None)
    Expected Result: 返回 (True, None)
    Evidence: .sisyphus/evidence/task-8-entry-pass.txt

  Scenario: 入场条件 — score 不够
    Tool: Bash (python -c)
    Steps:
      1. 同上但 score=0.2, min_score=0.35
      2. engine.evaluate_entry(...) → (False, "fusion_score below threshold 0.35")
    Expected Result: 返回 False + 拒绝原因
    Evidence: .sisyphus/evidence/task-8-entry-fail.txt

  Scenario: Polymarket 盈亏计算 — 方向对
    Tool: Bash (python -c)
    Steps:
      1. 方向 long, entry_price=90000, exit_price=91000, bet=100, fee=0.02
      2. settle → pnl = 100 * (1-0.02) = 98
    Expected Result: pnl = 98
    Evidence: .sisyphus/evidence/task-8-pnl-win.txt

  Scenario: Polymarket 盈亏计算 — 方向错
    Tool: Bash (python -c)
    Steps:
      1. 方向 long, entry_price=90000, exit_price=89000, bet=100
      2. settle → pnl = -100
    Expected Result: pnl = -100
    Evidence: .sisyphus/evidence/task-8-pnl-loss.txt

  Scenario: 风控 — 回撤超标
    Tool: Bash (python -c)
    Steps:
      1. current_capital=7000, peak=10000, drawdown=30%
      2. max_drawdown_pct=30
      3. check_risk → "pause"
    Expected Result: 返回 "pause"
    Evidence: .sisyphus/evidence/task-8-risk.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add simulation engine with entry/settle/risk logic`
  - Files: `backend/app/simulation/engine.py`

- [ ] 9. 会话管理器 (manager.py)

  **What to do**:
  - 创建 `backend/app/simulation/manager.py`
  - 实现 `SessionManager` 类，管理单个会话的完整生命周期
  - `create_session(strategy_id, asset, timeframe, initial_capital)` → 创建会话
  - `start(session_id)` → 状态设为 running，触发首次分析，注册定时任务
  - `pause(session_id, close_positions: bool)` → 暂停调度
    - close_positions=True: 立即结算所有 open trades
    - close_positions=False: 保留持仓但不开新仓
  - `resume(session_id)` → 重新注册定时任务
  - `stop(session_id)` → 结算所有持仓，状态设为 stopped
  - `process_kline(session_id)` → 核心循环（被 scheduler 调用）：
    1. 调 market_data 拉最新 K 线
    2. 调分析管道得到 AnalysisResult
    3. 创建 AnalysisRecord 并存入 DB
    4. 调 engine.evaluate_entry
    5. 满足 → engine.open_position → SSE 推送 trade_opened
    6. 调 engine.settle_positions → SSE 推送 trade_closed + capital_update
    7. 记录 capital_snapshot
    8. 调 engine.check_risk → 触发则自动暂停/停止 + SSE 推送 risk_breach
    9. 保存 checkpoint_data 到 session
  - **断点恢复** (`recover_sessions`)：启动时扫描 status=running 的会话，读 checkpoint，恢复 scheduler 任务

  **Must NOT do**:
  - 不要在 manager 里写具体的交易计算逻辑（交给 engine）
  - 不要在 manager 里操作数据库（交给 repository）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 协调多个模块的生命周期和状态管理
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: T10, T11
  - **Blocked By**: T3, T6, T8

  **References**:
  - `backend/app/core/graph_setup.py` — 参考现有 LangGraph 工作流的编排模式
  - `backend/app/services/market_data.py` — 调用 fetch_klines 函数签名

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/manager.py` 存在，含 `SessionManager` 类
  - [ ] `create_session` → `start` → session.status = "running"
  - [ ] `pause(close=True)` → 所有 open trades 已结算
  - [ ] `recover_sessions` 从 checkpoint 恢复

  **QA Scenarios**:
  ```
  Scenario: 会话启动和暂停
    Tool: Bash (python -c + pytest)
    Steps:
      1. 创建 session → assert status = "created"
      2. manager.start(session_id) → assert status = "running"
      3. manager.pause(session_id, close_positions=True) → assert status = "paused"
      4. 检查 trades 全部已结算
    Expected Result: 状态正确流转
    Evidence: .sisyphus/evidence/task-9-lifecycle.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add session lifecycle manager`
  - Files: `backend/app/simulation/manager.py`

- [ ] 10. APScheduler 调度器 (scheduler.py)

  **What to do**:
  - 创建 `backend/app/simulation/scheduler.py`
  - 封装 APScheduler 的 `AsyncIOScheduler`
  - `schedule_session(session_id, timeframe, callback)` → 计算下一个 K 线收盘时刻，注册 interval 任务
    - 15m: 每小时 :00 :15 :30 :45
    - 1h: 每小时 :00
    - 5m: 每 5 分钟
    - 动态计算首次触发时间（对齐到下一个整点边界）
  - `pause_session(session_id)` → pause_job
  - `resume_session(session_id)` → resume_job
  - `remove_session(session_id)` → remove_job
  - `start_scheduler()` → 启动调度器（在 FastAPI lifespan 中调用）
  - `shutdown_scheduler()` → 优雅关闭
  - 导出单例 `scheduler = SimulationScheduler()`

  **Must NOT do**:
  - 不要把调度逻辑写死在 scheduler 里（不关心具体做什么，只负责定时触发）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: APScheduler 标准封装，逻辑简单
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T11, T12, T13 after T8/T9)
  - **Blocks**: T19
  - **Blocked By**: T9

  **References**:
  - APScheduler 4.x 文档: `https://apscheduler.readthedocs.io/en/stable/`

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/scheduler.py` 存在
  - [ ] 15m timeframe → 下一个触发时间是对齐到 :00/:15/:30/:45 的时刻
  - [ ] pause_job 后任务不再触发，resume_job 后恢复

  **QA Scenarios**:
  ```
  Scenario: 15分钟K线调度时间计算
    Tool: Bash (python -c)
    Steps:
      1. 当前时间 08:07 → 计算下一个 15m 收盘时刻
      2. 应为 08:15
    Expected Result: 返回 08:15
    Evidence: .sisyphus/evidence/task-10-schedule.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add APScheduler wrapper`
  - Files: `backend/app/simulation/scheduler.py`

- [ ] 11. REST API 路由 (routes.py)

  **What to do**:
  - 创建 `backend/app/simulation/routes.py`
  - 创建 FastAPI `APIRouter(prefix="/api/v1/sim")`
  - 策略 CRUD：`POST /strategies`, `GET /strategies`, `GET /strategies/{id}`, `PUT /strategies/{id}`, `DELETE /strategies/{id}`
  - 会话控制：`POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/start`, `POST /sessions/{id}/pause`, `POST /sessions/{id}/resume`, `POST /sessions/{id}/stop`
  - pause 端点接受 query param `close_positions: bool = True`
  - 数据查询：`GET /sessions/{id}/trades`, `GET /sessions/{id}/analysis-records`, `GET /sessions/{id}/analysis-records/{rid}`, `GET /sessions/{id}/capital`
  - SSE 端点：`GET /sessions/{id}/stream` → `StreamingResponse`，content-type `text/event-stream`
    - 从 sse_manager 获取队列，循环 `await queue.get()` → `yield f"data: {json}\n\n"`
    - 客户端断开时自动清理
  - 所有端点使用 `Depends(get_db)` 注入数据库 session
  - 用 Pydantic Schema 做请求校验和响应序列化

  **Must NOT do**:
  - 不要在路由里写业务逻辑（调 manager/engine/repository）
  - SSE 端点不要用 WebSocket

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: FastAPI 标准路由定义
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T10, T12, T13 after T8/T9)
  - **Blocks**: T15, T19, T21
  - **Blocked By**: T2, T3, T6, T9

  **References**:
  - `backend/app/api/v1/endpoints/analyze.py` — 参考现有路由结构和 FastAPI 模式

  **Acceptance Criteria**:
  - [ ] `backend/app/simulation/routes.py` 存在，含 `sim_router`
  - [ ] `POST /api/v1/sim/strategies` 返回 201 + StrategyResponse
  - [ ] `GET /api/v1/sim/sessions/{id}/stream` 返回 `text/event-stream`

  **QA Scenarios**:
  ```
  Scenario: 策略 CRUD API
    Tool: Bash (curl)
    Steps:
      1. curl -X POST /api/v1/sim/strategies -H "Content-Type: application/json" -d '{"name":"test","entry_config":{"min_fusion_score":0.4},"bet_config":{"method":"fixed","fixed_amount":100},"settle_config":{"hold_klines":1},"risk_config":{}}'
      2. 断言 status=201, response.body.id 不为空
      3. curl GET /api/v1/sim/strategies → 断言列表含刚创建的策略
    Expected Result: CRUD 全部 2xx
    Evidence: .sisyphus/evidence/task-11-api.txt

  Scenario: SSE 流推送
    Tool: Bash (curl)
    Steps:
      1. curl -N GET /api/v1/sim/sessions/{id}/stream → 后台运行，监听事件
      2. 触发一次状态变更 → 断言收到 "data: {"type":"status_change"...}"
    Expected Result: 收到 SSE 事件
    Evidence: .sisyphus/evidence/task-11-sse.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add REST API routes with SSE stream`
  - Files: `backend/app/simulation/routes.py`

- [ ] 12. Zustand 状态管理 (simulationStore.ts)

  **What to do**:
  - 创建 `frontend/src/simulation/store/simulationStore.ts`
  - Zustand store 管理以下状态：
    - `strategies: Strategy[]` — 策略列表
    - `sessions: SimulationSession[]` — 会话列表
    - `selectedSession: SimulationSession | null` — 当前选中的会话
    - `trades: Trade[]` — 当前会话的交易
    - `capitalSnapshots: CapitalSnapshot[]` — 资金曲线数据
    - `analysisRecords: AnalysisRecord[]` — 分析记录列表
    - `selectedAnalysisRecord: AnalysisRecord | null` — 查看的分析记录
  - Actions：
    - `loadStrategies()`, `createStrategy()`, `updateStrategy()`, `deleteStrategy()`
    - `loadSessions()`, `createSession()`, `startSession()`, `pauseSession()`, `resumeSession()`, `stopSession()`
    - `selectSession(id)` — 选中会话，自动加载其 trades/capital/records
    - `applySSEEvent(event: SSEEvent)` — 处理 SSE 推送，局部更新状态
      - `capital_update` → 更新 currentCapital + 追加 capitalSnapshot
      - `trade_opened` → 追加 trades
      - `trade_closed` → 更新对应 trade
      - `status_change` → 更新 session.status

  **Must NOT do**:
  - 不要在 store 里直接调 fetch（通过 api 层）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Zustand store 标准模式
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T10, T11, T13)
  - **Blocks**: T14-T18
  - **Blocked By**: T4, T5

  **References**:
  - `frontend/src/store/useAppStore.ts` — 参考现有 Zustand store 的写法和模式

  **Acceptance Criteria**:
  - [ ] `simulationStore.ts` 存在，含完整状态和 actions
  - [ ] `applySSEEvent` 正确处理所有 6 种事件类型

  **QA Scenarios**:
  ```
  Scenario: SSE 事件更新 store
    Tool: Bash (npx vitest 或 tsc)
    Steps:
      1. 初始化 store
      2. applySSEEvent({type: "trade_opened", data: {id: 1, direction: "long", bet_amount: 100}})
      3. 断言 store.trades 长度为 1
      4. applySSEEvent({type: "capital_update", data: {capital: 10100}})
      5. 断言 selectedSession.current_capital = 10100
    Expected Result: 状态正确更新
    Evidence: .sisyphus/evidence/task-12-store.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add Zustand store for simulation state`
  - Files: `frontend/src/simulation/store/simulationStore.ts`

- [ ] 13. SSE 前端 Hook (useSSE.ts)

  **What to do**:
  - 创建 `frontend/src/simulation/hooks/useSSE.ts`
  - 实现 `useSSE(sessionId: string | null)` hook
  - 使用 `EventSource` API 连接 `/api/v1/sim/sessions/{sessionId}/stream`
  - `onmessage` 解析 JSON → 调用 `simulationStore.applySSEEvent()`
  - `onerror` → 自动重连（指数退避：1s, 2s, 4s, max 30s）
  - sessionId 为 null 时关闭连接
  - 组件卸载时自动 `close()`
  - 导出连接状态：`"connecting" | "connected" | "disconnected"`

  **Must NOT do**:
  - 不要用 WebSocket
  - 不要用第三方 SSE 库（原生 EventSource 够用）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准 EventSource hook
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T10, T11, T12)
  - **Blocks**: T16
  - **Blocked By**: T4

  **References**:
  - MDN EventSource: `https://developer.mozilla.org/en-US/docs/Web/API/EventSource`

  **Acceptance Criteria**:
  - [ ] `useSSE.ts` 存在
  - [ ] sessionId 变化时自动断开旧连接、建立新连接
  - [ ] 连接断开后自动重连

  **QA Scenarios**:
  ```
  Scenario: SSE 连接生命周期
    Tool: Playwright (浏览器环境验证)
    Steps:
      1. 选中会话 A → EventSource 连接到 /sessions/A/stream
      2. 切换到会话 B → A 的连接断开，B 的连接建立
      3. 关闭页面 → 连接关闭
    Expected Result: 连接正确管理
    Evidence: .sisyphus/evidence/task-13-sse-hook.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add SSE hook with auto-reconnect`
  - Files: `frontend/src/simulation/hooks/useSSE.ts`

- [ ] 14. 策略管理面板 (StrategyPanel.tsx)

  **What to do**:
  - 创建 `frontend/src/simulation/components/StrategyPanel.tsx`
  - 策略列表（表格）：名称、下注方式、状态（active/inactive）、创建时间
  - 操作按钮：新建、编辑（打开 StrategyForm）、删除（确认弹窗）、启用/禁用
  - 新建/编辑以 Modal 或侧边抽屉展示 StrategyForm
  - 从 simulationStore 读 strategies，操作后刷新列表

  **Must NOT do**:
  - 不要重复实现 StrategyForm 的表单逻辑（复用 T7）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI 面板布局和交互
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T15, T16, T17, T18)
  - **Blocks**: T19
  - **Blocked By**: T7, T12

  **References**:
  - `frontend/src/components/ConfigPanel.tsx` — 参考配置面板 UI 风格

  **Acceptance Criteria**:
  - [ ] `StrategyPanel.tsx` 存在
  - [ ] 策略列表渲染，新建/编辑/删除功能可用

  **QA Scenarios**:
  ```
  Scenario: 策略 CRUD 流程
    Tool: Playwright
    Steps:
      1. 打开模拟交易页面 → 策略列表为空
      2. 点击"新建策略" → Modal 弹出，填写表单
      3. 保存 → Modal 关闭，列表新增一条
      4. 点击编辑 → Modal 打开，表单回填已有值
      5. 点击删除 → 确认弹窗 → 删除成功
    Expected Result: 完整 CRUD 流程无报错
    Evidence: .sisyphus/evidence/task-14-strategy-panel.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add strategy management panel`
  - Files: `frontend/src/simulation/components/StrategyPanel.tsx`

- [ ] 15. 会话控制面板 (SessionPanel.tsx)

  **What to do**:
  - 创建 `frontend/src/simulation/components/SessionPanel.tsx`
  - 新建会话：选择策略（下拉）、币种（下拉）、周期（下拉 5m/15m/1h/4h）、初始资金
  - 会话列表（表格）：币种、周期、状态标签（颜色区分）、当前资金、胜率、运行时长
  - 操作按钮（根据状态显示）：
    - created → [启动]
    - running → [暂停]
    - paused → [恢复] [停止]
  - 暂停按钮点击弹出选择：[平仓并暂停] / [保留持仓暂停]
  - 点击会话行 → 选中该会话 → 右侧面板展示详情
  - 从 simulationStore 读写

  **Must NOT do**:
  - 不要硬编码币种列表（从现有配置或常量导入）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI 面板 + 状态机交互
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T14, T16, T17, T18)
  - **Blocks**: T19
  - **Blocked By**: T12

  **References**:
  - `frontend/src/components/AnalysisForm.tsx` — 参考资产和周期选择 UI

  **Acceptance Criteria**:
  - [ ] `SessionPanel.tsx` 存在
  - [ ] 新建会话 → 列表出现 → 启动 → 状态变 running（绿色标签）
  - [ ] 暂停时弹出选择框

  **QA Scenarios**:
  ```
  Scenario: 会话完整生命周期
    Tool: Playwright
    Steps:
      1. 新建会话：选策略A, BTC, 15m → 列表出现 status=created
      2. 点击"启动" → status 变 running
      3. 点击"暂停" → 弹窗出现，选择"保留持仓暂停"
      4. status 变 paused（黄色标签）
      5. 点击"恢复" → status 变 running
      6. 点击"停止" → status 变 stopped
    Expected Result: 状态流转正确
    Evidence: .sisyphus/evidence/task-15-session-panel.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add session control panel`
  - Files: `frontend/src/simulation/components/SessionPanel.tsx`

- [ ] 16. 实时看板 (LiveDashboard.tsx)

  **What to do**:
  - 创建 `frontend/src/simulation/components/LiveDashboard.tsx`
  - 选中会话后展示实时看板，布局：
    - 顶行 4 个指标卡片：当前资金、总收益率%、胜率（K1/K2）、当前回撤%
    - 中部：资金曲线图（嵌入 CapitalChart 组件）
    - 下部：当前持仓列表（卡片式，每张显示：方向、入场价、当前价、已持K线数、预计盈亏）
  - 数据通过 SSE 实时更新（useSSE hook 已连接）
  - 未选中会话时显示空状态提示："请选择或创建一个模拟会话"

  **Must NOT do**:
  - 不要自己实现图表（用 CapitalChart 组件）
  - 不要自己管理数据获取（依赖 store + SSE）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 实时看板 UI 布局
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T14, T15, T17, T18)
  - **Blocks**: T19
  - **Blocked By**: T12, T13

  **References**:
  - `frontend/src/components/SummaryPanel.tsx` — 参考指标卡片布局

  **Acceptance Criteria**:
  - [ ] `LiveDashboard.tsx` 存在
  - [ ] 选中会话后展示实时数据
  - [ ] SSE 推送新交易时持仓列表自动更新

  **QA Scenarios**:
  ```
  Scenario: 实时看板展示
    Tool: Playwright
    Steps:
      1. 选中一个 running 状态的会话
      2. 断言：指标卡片显示当前资金、收益率、胜率
      3. 断言：资金曲线图渲染
      4. 等待 SSE 推送 trade_opened → 断言持仓列表新增一条
    Expected Result: 看板实时更新
    Evidence: .sisyphus/evidence/task-16-dashboard.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add live dashboard with real-time updates`
  - Files: `frontend/src/simulation/components/LiveDashboard.tsx`

- [ ] 17. 资金曲线图 (CapitalChart.tsx)

  **What to do**:
  - 创建 `frontend/src/simulation/components/CapitalChart.tsx`
  - 使用 `lightweight-charts` 库绘制资金曲线
  - 从 `simulationStore.capitalSnapshots` 读取数据
  - X 轴：时间，Y 轴：资金金额
  - 曲线下方填充半透明区域（绿色=盈利区间，红色=亏损区间）
  - 叠加初始资金水平线（虚线）
  - 响应式宽度，支持鼠标悬停显示数值
  - SSE 推送 `capital_update` 时实时追加新数据点

  **Must NOT do**:
  - 不要用其他图表库（如 recharts、echarts）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 金融图表，需要正确使用 lightweight-charts API
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T14-T16, T18)
  - **Blocks**: T16
  - **Blocked By**: T12

  **References**:
  - Lightweight Charts 文档: `https://tradingview.github.io/lightweight-charts/docs`
  - 安装: `npm install lightweight-charts`

  **Acceptance Criteria**:
  - [ ] `CapitalChart.tsx` 存在
  - [ ] 传入 `[{time: "2024-01-01", value: 10000}, ...]` 正确渲染折线图
  - [ ] 新数据追加时图表动态更新

  **QA Scenarios**:
  ```
  Scenario: 资金曲线渲染
    Tool: Playwright
    Steps:
      1. 选中一个有资金快照数据的会话
      2. 断言 canvas 元素存在（lightweight-charts 用 canvas 渲染）
      3. 鼠标悬停在曲线上 → 断言 tooltip 显示数值
    Expected Result: 图表正确渲染
    Evidence: .sisyphus/evidence/task-17-capital-chart.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add capital curve chart with lightweight-charts`
  - Files: `frontend/src/simulation/components/CapitalChart.tsx`

- [ ] 18. 持仓列表 + 交易历史 + 信号日志 + 分析记录查看

  **What to do**:
  - 创建 4 个独立组件文件：
    - `PositionList.tsx`：当前 open trades 卡片列表（方向、入场价、入场时间、已持K线、当前盈亏）
    - `TradeHistory.tsx`：已结算 trades 表格（时间、方向、盈亏、胜负），分页
    - `SignalLog.tsx`：信号日志表格（时间、方向、分数、置信度、是否入场、拒绝原因），分页
    - `AnalysisRecordViewer.tsx`：点击某条分析记录 → 复用现有 `SummaryPanel`, `DecisionPanel`, `IndicatorPanel`, `PatternPanel`, `TrendPanel` 展示完整分析结果（只读模式）。附加信息：是否触发了交易、如果触发了盈亏如何
  - 所有列表支持分页或虚拟滚动
  - 数据从 simulationStore 读取

  **Must NOT do**:
  - 不要修改现有 SummaryPanel 等组件（以只读模式复用）
  - 不要把所有逻辑写在一个组件里（4 个独立文件）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 4 个数据展示组件
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with T14-T17)
  - **Blocks**: T19
  - **Blocked By**: T12

  **References**:
  - `frontend/src/components/DecisionPanel.tsx` — 参考 Fusion 结果展示
  - `frontend/src/components/IndicatorPanel.tsx` — 参考 Agent 分析结果展示
  - `frontend/src/types/index.ts` — 现有 AnalysisResult 类型

  **Acceptance Criteria**:
  - [ ] 4 个组件文件全部存在
  - [ ] AnalysisRecordViewer 点击记录后正确渲染 AnalysisResult
  - [ ] 列表分页功能正常

  **QA Scenarios**:
  ```
  Scenario: 分析记录查看
    Tool: Playwright
    Steps:
      1. 在历史列表中点击一条分析记录
      2. 断言：弹出/展开详情页，显示 Fusion 方向、分数、各 Agent 摘要
      3. 如果该记录触发了交易 → 显示交易结果（盈亏、胜负）
    Expected Result: 完整展示分析详情
    Evidence: .sisyphus/evidence/task-18-analysis-viewer.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): add position list, trade history, signal log, analysis viewer`
  - Files: `frontend/src/simulation/components/PositionList.tsx`, `TradeHistory.tsx`, `SignalLog.tsx`, `AnalysisRecordViewer.tsx`

- [ ] 19. 主入口 + 路由注册 (SimulationApp.tsx + main.py)

  **What to do**:
  - 前端：
    - 创建 `frontend/src/simulation/SimulationApp.tsx` — 模块入口
    - 三栏布局：左侧 StrategyPanel + SessionPanel，右侧 LiveDashboard（包含图表和列表的 Tab 切换）
    - 或 Tab 布局：策略 | 会话 | 实时看板 | 历史
  - 后端：
    - 在 `backend/app/main.py` 中注册 `sim_router`
    - 在 FastAPI `lifespan` 中调用 `scheduler.start_scheduler()` 和 `manager.recover_sessions()`
    - 在 shutdown 中调用 `scheduler.shutdown_scheduler()`
  - 前端路由：在现有 Vite 路由中添加 `/simulation` 路径

  **Must NOT do**:
  - 不要修改现有 App.tsx 路由逻辑（新增路由入口不破坏现有）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 主布局和集成
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3（最后集成）
  - **Blocks**: T21, T22
  - **Blocked By**: T10, T11, T14-T18

  **References**:
  - `frontend/src/App.tsx` — 参考现有路由和布局
  - `backend/app/main.py` — 参考现有 lifespan 和 router 注册

  **Acceptance Criteria**:
  - [ ] `SimulationApp.tsx` 存在，可在浏览器访问 `/simulation`
  - [ ] 后端启动时 scheduler 和 recover_sessions 被调用
  - [ ] 访问 `/api/v1/sim/strategies` 返回 200

  **QA Scenarios**:
  ```
  Scenario: 完整前端流程
    Tool: Playwright
    Steps:
      1. 访问 /simulation
      2. 创建策略 → 保存成功
      3. 创建会话并启动
      4. 等待几秒 → 选中会话 → 实时看板展示数据
    Expected Result: 端到端流程可用
    Evidence: .sisyphus/evidence/task-19-e2e.png
  ```

  **Commit**: YES
  - Message: `feat(simulation): integrate simulation module into app`
  - Files: `frontend/src/simulation/SimulationApp.tsx`, `backend/app/main.py` (追加 router 注册)

- [ ] 20. 引擎单元测试 (test_simulation_engine.py)

  **What to do**:
  - 创建 `backend/tests/test_simulation_engine.py`
  - 使用 pytest + pytest-asyncio
  - 测试用例覆盖：
    - `test_evaluate_entry_all_pass` — 所有条件满足返回 True
    - `test_evaluate_entry_score_fail` — score 不够返回 False
    - `test_evaluate_entry_confidence_fail` — confidence 不够
    - `test_evaluate_entry_hold_excluded` — direction=hold 被排除
    - `test_evaluate_entry_max_concurrent` — 已达最大持仓数
    - `test_open_position_fixed` — 固定金额开仓正确
    - `test_open_position_percent` — 百分比开仓正确
    - `test_open_position_fee` — 手续费扣除正确
    - `test_settle_win` — 方向对，Polymarket 盈亏 = bet*(1-fee)
    - `test_settle_loss` — 方向错，盈亏 = -bet
    - `test_check_risk_drawdown` — 回撤超标返回 pause
    - `test_check_risk_consecutive_loss` — 连亏超标返回 pause
    - `test_check_risk_min_capital` — 低于最低资金返回 stop
  - 每个测试独立，用 fixture 创建 engine 实例和 mock 数据

  **Must NOT do**:
  - 不要测试数据库操作（mock repository）
  - 不要测试外部 API 调用（mock market_data）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要仔细设计测试用例覆盖所有边界条件
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: F3
  - **Blocked By**: T8

  **References**:
  - `backend/tests/test_brale_modules.py` — 参考现有 pytest 风格和 fixture 模式

  **Acceptance Criteria**:
  - [ ] `backend/tests/test_simulation_engine.py` 存在，含 13+ 测试用例
  - [ ] `cd backend && python -m pytest tests/test_simulation_engine.py -v` → 全部 PASS

  **QA Scenarios**:
  ```
  Scenario: 全部测试通过
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_simulation_engine.py -v
    Expected Result: 13+ passed, 0 failed
    Evidence: .sisyphus/evidence/task-20-tests.txt
  ```

  **Commit**: YES
  - Message: `test(simulation): add engine unit tests`
  - Files: `backend/tests/test_simulation_engine.py`

- [ ] 21. API 集成测试

  **What to do**:
  - 使用 FastAPI TestClient + 内存 SQLite 测试完整 API 流程
  - 测试场景：
    - 创建策略 → GET 列表包含它 → PUT 更新 → DELETE 删除
    - 创建会话 → POST start → GET 状态为 running → POST pause → GET 状态为 paused
    - GET trades/analysis-records/capital 返回正确数据结构
    - SSE 端点返回 text/event-stream content-type

  **Must NOT do**:
  - 不要真连 OKX API（mock market_data）
  - 不要真调 LLM（mock agent pipeline）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: FastAPI TestClient 标准集成测试
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T20, T22)
  - **Blocks**: F3
  - **Blocked By**: T11, T19

  **References**:
  - FastAPI Testing 文档: `https://fastapi.tiangolo.com/tutorial/testing/`

  **Acceptance Criteria**:
  - [ ] 集成测试文件存在
  - [ ] `pytest tests/test_simulation_api.py -v` → PASS

  **QA Scenarios**:
  ```
  Scenario: 集成测试全通过
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_simulation_api.py -v
    Expected Result: all passed
    Evidence: .sisyphus/evidence/task-21-integration.txt
  ```

  **Commit**: YES
  - Message: `test(simulation): add API integration tests`
  - Files: `backend/tests/test_simulation_api.py`

- [ ] 22. 前端冒烟测试

  **What to do**:
  - Playwright 脚本验证前端页面可访问、核心交互可用
  - 访问 `/simulation` → 页面加载无报错
  - 策略 CRUD 操作可用
  - 会话创建和启动可用
  - 实时看板区域渲染（即使无数据也显示空状态）

  **Must NOT do**:
  - 不需要测真实交易数据（mock 或检查空状态即可）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 前端 E2E 交互验证
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T20, T21)
  - **Blocks**: None
  - **Blocked By**: T19

  **References**:
  - Playwright 技能 (`/playwright`)

  **Acceptance Criteria**:
  - [ ] 冒烟测试通过：页面加载、策略创建、会话启动三个核心流程无阻断

  **QA Scenarios**:
  ```
  Scenario: 前端冒烟测试
    Tool: Playwright
    Steps:
      1. page.goto("/simulation")
      2. 断言页面标题/导航存在
      3. 点击"新建策略" → 表单打开 → 填写 → 保存
      4. 新建会话 → 启动 → 状态变 running
    Expected Result: 无 JS 报错，流程走通
    Evidence: .sisyphus/evidence/task-22-smoke.png
  ```

  **Commit**: YES
  - Message: `test(simulation): add frontend smoke tests`
  - Files: `frontend/e2e/simulation.spec.ts`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read files, curl endpoints). For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `npx tsc --noEmit` in frontend. Run `pytest` in backend. Review all new simulation files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state (delete simulation.db). Execute EVERY QA scenario from EVERY task. Test cross-task integration: create strategy → start session → SSE connection → wait for analysis → check trades created → verify capital curve. Test edge cases: empty state, invalid config, pause/resume, crash recovery.
  Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Wave | Tasks | Commit Message Pattern |
|------|-------|----------------------|
| 1 | T1-T3 | `feat(simulation): add database models, schemas, repository` |
| 1 | T4-T5 | `feat(simulation): add TypeScript types and API client` |
| 1 | T6-T7 | `feat(simulation): add SSE manager and strategy form` |
| 2 | T8 | `feat(simulation): add simulation engine` |
| 2 | T9-T11 | `feat(simulation): add manager, scheduler, REST API` |
| 2 | T12-T13 | `feat(simulation): add Zustand store and SSE hook` |
| 3 | T14-T18 | `feat(simulation): add frontend panels and components` |
| 3 | T19 | `feat(simulation): integrate simulation module` |
| 4 | T20-T22 | `test(simulation): add unit, integration, smoke tests` |

---

## Success Criteria

### Verification Commands
```bash
# 后端单元测试
cd backend && python -m pytest tests/test_simulation_engine.py -v
# Expected: 13+ passed

# 后端集成测试
cd backend && python -m pytest tests/test_simulation_api.py -v
# Expected: all passed

# 前端类型检查
cd frontend && npx tsc --noEmit
# Expected: no errors

# 完整启动
python launch.py
# Expected: FastAPI + Vite 正常启动，/simulation 页面可访问
```

### Final Checklist
- [ ] 策略 CRUD API 全部可用
- [ ] 会话可以创建、启动、暂停、恢复、停止
- [ ] K 线收盘时自动触发分析管道
- [ ] 满足条件自动开仓，到期自动结算
- [ ] Polynarket 二元盈亏计算正确
- [ ] SSE 实时推送状态变更到前端
- [ ] 资金曲线图实时更新
- [ ] 分析记录完整可回溯查看
- [ ] 杀掉进程重启后自动恢复
- [ ] 多会话并发互不干扰
- [ ] 风控触发自动暂停
- [ ] 引擎单元测试全部通过
- [ ] 不修改任何现有分析管道代码

