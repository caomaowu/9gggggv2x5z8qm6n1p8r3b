# 实时模拟交易模块 — 架构设计文档

## 0. 概述

在现有 QuantAgent 分析系统基础上，新增**独立、解耦**的实时模拟交易模块。

- 复用：`POST /api/v1/analyze/` 分析管线（TradingEngine → 3 Agent → Fusion）
- 新建：回合制押注引擎 + 任务调度 + 资金统计 + 独立前端
- 场景：模拟 Polymarket UP/DOWN 二元预测市场，每根 K 线为一个独立回合
- 端口：后端 `18520`，前端 `18521`

---

## 1. 目录结构

```
Refactor_v2/
├── backend/                    # 现有（不动）
├── frontend/                   # 现有（不动）
├── tools/                      # 现有（不动）
│
└── simulation/                 # ★ 新建，完全独立
    ├── pyproject.toml
    ├── server.py               # FastAPI + WebSocket 入口
    ├── config.py               # 全局配置
    │
    ├── engine/
    │   ├── scheduler.py        # 精确K线调度器
    │   ├── round_executor.py   # 单回合执行（结算+分析+押注）
    │   ├── task_manager.py     # 多任务生命周期管理
    │   └── betting.py          # 押注金额计算
    │
    ├── models/
    │   ├── db.py               # SQLite 表结构 + 异步 CRUD
    │   └── schemas.py          # Pydantic 请求/响应模型
    │
    ├── api/
    │   ├── routes_tasks.py     # REST: 任务 CRUD + 启停删
    │   ├── routes_stats.py     # REST: 统计、资金曲线、交易日记
    │   └── ws_manager.py       # WebSocket: 实时广播
    │
    └── frontend/               # ★ 独立 React + Vite 前端
        ├── package.json
        ├── vite.config.ts
        └── src/
            ├── App.tsx
            ├── api/            # HTTP + WS 客户端
            ├── components/     # UI 组件
            ├── pages/          # 页面
            ├── store/          # Zustand 状态管理
            └── types/          # TypeScript 类型
```

---

## 2. 数据模型

### 2.1 SQLite 表结构

```sql
-- 任务配置表
CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,          -- UUID
    asset           TEXT NOT NULL,             -- "BTC" / "ETH" / ...
    timeframe       TEXT NOT NULL,             -- "15m" / "1h" / "4h" / "1d"
    status          TEXT NOT NULL DEFAULT 'STOPPED',  -- STOPPED | RUNNING
    bet_amount      REAL NOT NULL,             -- 固定金额模式：每次押注金额(USDT)
    bet_mode        TEXT NOT NULL DEFAULT 'fixed',     -- "fixed" | "percent"
    bet_percent     REAL DEFAULT NULL,         -- 百分比模式：每次下注资金比例 (0.01 = 1%)
    fee_rate        REAL NOT NULL DEFAULT 0.0, -- 手续费率 (0.002 = 0.2%)
    initial_capital REAL NOT NULL,             -- 初始资金
    current_capital REAL NOT NULL,             -- 当前资金
    total_rounds    INTEGER NOT NULL DEFAULT 0,-- 总回合数
    wins            INTEGER NOT NULL DEFAULT 0,-- 胜场数
    losses          INTEGER NOT NULL DEFAULT 0,-- 败场数
    skips           INTEGER NOT NULL DEFAULT 0,-- 跳过次数(direction=none)
    best_win_streak INTEGER NOT NULL DEFAULT 0,-- 最长连胜
    worst_lose_streak INTEGER NOT NULL DEFAULT 0, -- 最长连败
    current_streak  TEXT DEFAULT NULL,         -- "W3" / "L2" (当前连胜/连败)
    created_at      TEXT NOT NULL,             -- ISO 8601
    updated_at      TEXT NOT NULL              -- ISO 8601
);

-- 回合记录表（分析结果 + 押注 + 结算）
CREATE TABLE rounds (
    id              TEXT PRIMARY KEY,          -- UUID
    task_id         TEXT NOT NULL,             -- FK → tasks.id
    round_seq       INTEGER NOT NULL,          -- 回合序号 (1, 2, 3, ...)
    status          TEXT NOT NULL DEFAULT 'BET_PLACED',  -- BET_PLACED | SETTLED

    -- 触发 K 线信息
    trigger_kline_ts    TEXT NOT NULL,         -- 触发时 K 线收盘时间 ISO 8601
    trigger_kline_open  REAL,                  -- 触发 K 线开盘价
    trigger_kline_close REAL,                  -- 触发 K 线收盘价（即入场价）

    -- 分析结果 (decision)
    direction       TEXT,                      -- "long" / "short" / "none"
    score           REAL,                      -- Fusion score [-1, 1]
    confidence      REAL,                      -- Fusion confidence [0, 1]
    entry_point     REAL,                      -- 入场价

    -- 三个 Agent 各自分数
    indicator_score         REAL,              -- Indicator Agent movement_score
    indicator_confidence    REAL,              -- Indicator Agent movement_confidence
    structure_score         REAL,              -- Structure Agent movement_score
    structure_confidence    REAL,              -- Structure Agent movement_confidence
    mechanics_score         REAL,              -- Mechanics Agent movement_score
    mechanics_confidence    REAL,              -- Mechanics Agent movement_confidence

    -- 三个 Agent 完整摘要 (JSON)
    indicator_summary   TEXT,                  -- IndicatorSummary JSON
    structure_summary   TEXT,                  -- StructureSummary JSON
    mechanics_summary   TEXT,                  -- MechanicsSummary JSON

    -- Fusion 原始结果 (JSON)
    fusion_raw          TEXT,                  -- 完整 fusion 结果 JSON

    -- 押注信息
    bet_direction   TEXT,                      -- "long" / "short"
    bet_amount      REAL,                      -- 押注金额
    fee_amount      REAL DEFAULT 0,            -- 实际手续费

    -- 结算信息
    settle_kline_ts     TEXT,                  -- 结算 K 线收盘时间
    settle_price        REAL,                  -- 结算价（下一根 K 线收盘价）
    result              TEXT,                  -- "WIN" / "LOSE" / "SKIP"
    pnl                 REAL,                  -- 本回合盈亏（含手续费）

    created_at          TEXT NOT NULL,         -- ISO 8601
    settled_at          TEXT                   -- ISO 8601
);

-- 索引
CREATE INDEX idx_rounds_task_id ON rounds(task_id);
CREATE INDEX idx_rounds_task_seq ON rounds(task_id, round_seq);
CREATE UNIQUE INDEX idx_rounds_trigger ON rounds(task_id, trigger_kline_ts);  -- 防重复
```

### 2.2 数据可靠性策略

- **防重复**：`(task_id, trigger_kline_ts)` 唯一索引，同一根 K 线不会触发两次
- **崩溃恢复**：启动时检查 `rounds.status='BET_PLACED'` 的记录，补结算
- **原子写入**：每回合的 分析记录 + 押注 在同一次事务中写入

---

## 3. 核心引擎

### 3.1 调度器 (`scheduler.py`)

**职责**：精确计算每根 K 线收盘时间，到点触发回合执行。

**实现思路**：
```
asyncio 事件循环:
  维护一个优先队列 (heap)，按触发时间排序
  每任务在启动时计算下一次 K 线收盘时间
  到点 → 触发 round_executor → 执行完后计算下一个触发时间重新入队
```

**K 线收盘时间计算**（UTC）：
| 周期 | 收盘时刻 | 示例 |
|------|---------|------|
| 1m | 每分钟整 | 14:01, 14:02, ... |
| 5m | 每5分钟整 | 14:00, 14:05, ... |
| 15m | 每15分钟整 | 14:00, 14:15, ... |
| 1h | 每小时整 | 14:00, 15:00, ... |
| 4h | 0/4/8/12/16/20 整 | 00:00, 04:00, ... |
| 1d | 每日 00:00 | 每天一次 |

**触发时机**：收盘时间 + 缓冲（如 +30 秒），给 API 响应留余地。

**伪代码**：
```python
class Scheduler:
    def __init__(self):
        self._heap = []           # (next_trigger_ts, task_id)
        self._event = asyncio.Event()

    async def add_task(self, task: Task):
        next_ts = calc_next_kline_close(task.timeframe)
        heapq.heappush(self._heap, (next_ts, task.id))
        self._event.set()

    async def remove_task(self, task_id: str):
        # 标记删除，不实际从 heap 移除（惰性清理）

    async def run(self):
        while True:
            while self._heap and self._heap[0][0] <= now_ts():
                _, task_id = heapq.heappop(self._heap)
                if not is_marked_deleted(task_id):
                    await round_executor.execute(task_id)
                    next_ts = calc_next_kline_close(task.timeframe)
                    heapq.heappush(self._heap, (next_ts, task_id))
            await self._event.wait()
            self._event.clear()
```

### 3.2 回合执行器 (`round_executor.py`)

**职责**：执行单个回合的完整生命周期。

**状态机**：
```
  ┌─────────┐
  │ 触发    │ ← scheduler 到点触发
  └────┬────┘
       ▼
  ┌─────────────┐
  │ ① 结算上一局 │  若存在 status=BET_PLACED 的回合
  │   对比方向   │    → 用当前收盘价判定 WIN/LOSE
  │   更新资金   │    → 计算 PnL，更新 tasks.current_capital
  └────┬────────┘
       ▼
  ┌─────────────┐
  │ ② 调分析API │  POST backend:8000/api/v1/analyze/
  │   data_method="latest"  
  │   获取 direction/score/confidence + 3 agent 数据
  └────┬────────┘
       ▼
  ┌─────────────┐
  │ ③ 记录分析   │  写入 rounds 表（决策+agent分数+摘要）
  │   方向判断   │  若 direction="none" → 跳过押注，标记 SKIP
  └────┬────────┘
       ▼
  ┌─────────────┐
  │ ④ 押注       │  计算金额 → 写入 bet_direction + bet_amount
  │   status=BET_PLACED
  └────┬────────┘
       ▼
  ┌─────────────┐
  │ ⑤ WS 推送    │  新回合数据 → 前端实时更新
  └─────────────┘
```

**异常处理**：
- 分析 API 超时/报错 → 记录日志，本轮跳过，不阻塞后续
- direction 为 "none" → 标记 `result="SKIP"`，`status="SETTLED"`（无需等下一根 K 线结算）
- direction 为 "long"/"short" → 正常押注，等下一根 K 线收盘时结算

### 3.3 押注模型 (`betting.py`)

```python
def calculate_bet(task: Task) -> float:
    """根据任务配置计算本次押注金额"""
    if task.bet_mode == "fixed":
        return task.bet_amount
    elif task.bet_mode == "percent":
        return task.current_capital * task.bet_percent


def calculate_pnl(result: str, bet_amount: float, fee_rate: float) -> float:
    """
    result = "WIN"  → +bet_amount * (1 - fee_rate)
    result = "LOSE" → -bet_amount
    result = "SKIP" → 0
    """
    if result == "WIN":
        return bet_amount * (1 - fee_rate)
    elif result == "LOSE":
        return -bet_amount
    else:
        return 0.0
```

### 3.4 任务管理器 (`task_manager.py`)

```python
class TaskManager:
    async def create_task(config: CreateTaskRequest) -> Task
    async def start_task(task_id: str) -> None      # STOPPED → RUNNING, 入调度队列
    async def stop_task(task_id: str) -> None       # RUNNING → STOPPED, 移出调度队列
    async def delete_task(task_id: str) -> None     # 停止 + 删除记录（保留 rounds）
    async def get_task(task_id: str) -> Task
    async def list_tasks() -> List[Task]
    async def recover_on_startup() -> None          # 恢复所有 RUNNING 任务
```

### 3.5 崩溃恢复流程

```
server.py 启动:
  │
  ├─ 1. 初始化 SQLite 连接
  ├─ 2. 查询 tasks WHERE status = 'RUNNING'
  │
  ├─ 3. 对每个 RUNNING 任务:
  │     ├─ 查最新 round WHERE task_id = ?
  │     ├─ 若 round.status = 'BET_PLACED'（上一局未结算）
  │     │     → 先结算（获取当前价，判定 WIN/LOSE）
  │     │     → 然后正常执行下一步（分析+押注）
  │     └─ 若 round.status = 'SETTLED'（上一局已结算）
  │           → 正常从"分析"步骤继续
  │
  └─ 4. 将所有 RUNNING 任务加入调度器
```

---

## 4. API 设计

### 4.1 REST 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/tasks` | 创建任务 |
| `GET` | `/api/tasks` | 列出所有任务 |
| `GET` | `/api/tasks/{id}` | 获取任务详情 + 统计摘要 |
| `POST` | `/api/tasks/{id}/start` | 启动任务 |
| `POST` | `/api/tasks/{id}/stop` | 停止任务 |
| `DELETE` | `/api/tasks/{id}` | 删除任务 |
| `GET` | `/api/tasks/{id}/rounds` | 分页获取回合记录（交易日记） |
| `GET` | `/api/tasks/{id}/stats` | 任务统计（胜率、盈亏比、资金曲线数据点） |
| `GET` | `/api/tasks/{id}/equity` | 资金曲线数据（用于图表） |

**创建任务请求体**：
```json
{
    "asset": "BTC",
    "timeframe": "4h",
    "bet_mode": "fixed",
    "bet_amount": 100.0,
    "fee_rate": 0.002,
    "initial_capital": 10000.0
}
```

**统计响应体**：
```json
{
    "task_id": "...",
    "total_rounds": 42,
    "wins": 23,
    "losses": 17,
    "skips": 2,
    "win_rate": 0.575,
    "total_pnl": 1245.0,
    "current_capital": 11245.0,
    "roi": 0.1245,
    "max_drawdown": -0.08,
    "sharpe_ratio": 1.32,
    "profit_factor": 1.85,
    "best_win_streak": 5,
    "worst_lose_streak": 3,
    "current_streak": "W2"
}
```

### 4.2 WebSocket

**端点**：`ws://localhost:18520/ws`

**客户端连接后无需订阅，服务端主动推送所有任务的事件。**

**消息格式**：
```json
{
    "type": "round_completed",      // 事件类型
    "task_id": "...",
    "data": {
        "round_seq": 43,
        "direction": "long",
        "score": 0.52,
        "confidence": 0.71,
        "bet_amount": 100.0,
        "result": "WIN",           // 或 "LOSE" / "SKIP" / null（刚押注未结算）
        "pnl": 99.8,
        "current_capital": 11344.8
    }
}
```

**事件类型**：
- `task_started` — 任务启动
- `task_stopped` — 任务停止
- `task_deleted` — 任务删除
- `round_completed` — 回合完成（分析+押注完成，含上一局结算结果）
- `stats_updated` — 统计数据更新

---

## 5. 前端设计

### 5.1 技术栈

- React 18 + TypeScript
- Vite
- Zustand（状态管理）
- Recharts（图表：资金曲线、统计图）
- TailwindCSS（样式）

### 5.2 页面结构

```
/                          → 仪表盘（所有任务概览卡片）
/tasks                     → 任务列表
/tasks/:id                 → 任务详情
  ├── 实时状态（运行中/已停止、当前资金）
  ├── 资金曲线图
  ├── 统计面板（胜率、盈亏、回撤、夏普等）
  ├── 最近交易日记（回合列表，滚动加载）
  └── 配置面板（修改参数）
```

### 5.3 核心组件

| 组件 | 说明 |
|------|------|
| `TaskCard` | 仪表盘上的任务小卡片（币种/周期/状态/盈亏） |
| `CreateTaskModal` | 创建任务弹窗（币种、周期、金额等参数） |
| `EquityChart` | 资金曲线折线图（Recharts） |
| `StatsPanel` | 统计指标网格（胜率、盈亏比、最大回撤、夏普...） |
| `RoundTable` | 交易日记表格（序号/方向/分数/结果/盈亏，分页+滚动加载） |
| `TaskConfigPanel` | 任务参数实时修改 |

### 5.4 实时更新

- Zustand store 维护 WebSocket 连接
- 收到推送 → 更新对应 task 的 `rounds` 列表 + `stats` + `current_capital`
- 资金曲线图自动刷新

---

## 6. 配置 (`config.py`)

```python
# 现有后端地址（分析 API）
BACKEND_ANALYZE_URL = "http://localhost:8000/api/v1/analyze/"

# 模拟模块自身
SIMULATION_HOST = "0.0.0.0"
SIMULATION_PORT = 18520

# 数据库
DATABASE_PATH = "simulation/data/simulation.db"

# K 线调度
KLINE_BUFFER_SECONDS = 30        # K 线收盘后等 30 秒再触发（给 API 响应缓冲）
ANALYZE_TIMEOUT = 120            # 分析 API 超时（秒）
ANALYZE_RETRY_COUNT = 2          # 分析 API 失败重试次数
ANALYZE_RETRY_DELAY = 10         # 重试间隔（秒）

# 资金
DEFAULT_INITIAL_CAPITAL = 10000.0
DEFAULT_BET_AMOUNT = 100.0
DEFAULT_FEE_RATE = 0.0
```

---

## 7. 关键边界条件

| 场景 | 处理 |
|------|------|
| 分析返回 `direction="none"` | 跳过押注，标记 `SKIP`，本轮不产生盈亏 |
| 分析 API 超时/报错 | 重试 2 次，仍失败则记录日志，本轮跳过 |
| 同一根 K 线重复触发 | `(task_id, trigger_kline_ts)` 唯一索引拦截 |
| 资金不足支付押注 | 自动停止任务，`status=STOPPED`，WS 推送告警 |
| 首次启动无上一局 | 跳过结算步骤，直接分析+押注 |
| 启动时程序崩溃 | `recover_on_startup()` 读取 RUNNING 任务，补结算未完成的回合 |
| 多任务同一时刻触发 | 异步并发执行，互不阻塞 |

---

## 8. 启动方式

```bash
# 终端 1: 现有后端（不变）
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 终端 2: 模拟模块后端
cd simulation && python server.py          # → localhost:18520

# 终端 3: 模拟模块前端
cd simulation/frontend && npm run dev      # → localhost:18521
```

---

## 9. 实施优先级

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **P0** | `models/` — SQLite 建表 + CRUD + Pydantic schemas | 无 |
| **P1** | `engine/` — scheduler + round_executor + betting + task_manager | P0 |
| **P2** | `api/` — REST routes + WebSocket manager | P1 |
| **P2** | `server.py` — FastAPI 入口 + 崩溃恢复 | P2 |
| **P3** | `frontend/` — React 独立前端 | P2 |
