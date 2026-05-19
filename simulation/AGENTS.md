# Simulation 模块 — 实时模拟交易系统

> 独立于主项目的模拟交易引擎。提供任务生命周期管理、K线定时调度、回合结算、WebSocket 实时推送，以及基于 React 的可视化看板。

## 📋 模块职责

Simulation 是一个完整的独立子系统，负责：

1. **任务管理**：创建/启动/停止/删除模拟交易任务，支持崩溃恢复
2. **定时调度**：基于 K 线收盘时间的精确定时器（heapq + asyncio），到点自动执行交易回合
3. **回合执行**：每轮执行"结算上一局 → 调用分析 API → 记录新押注"的完整流水线
4. **盈亏计算**：纯数学函数，固定金额或百分比两种押注模式
5. **实时推送**：WebSocket 广播任务状态变化、回合结果、统计更新
6. **数据持久化**：基于 aiosqlite 的异步 SQLite 存储，任务表 + 回合表
7. **可视化看板**：React 前端，权益曲线图、统计面板、回合交易日记表格

## 🏗️ 目录结构

```
simulation/
├── __init__.py                    # 包标记
├── .env.example                   # 环境变量模板
├── config.py                      # 全局配置 (pydantic-settings)
├── conftest.py                    # pytest 共享 fixtures（临时数据库、事件循环）
├── server.py                      # ★ FastAPI 入口，端口 18520
├── pytest.ini                     # pytest 配置（asyncio_mode=auto）
├── pyproject.toml                 # 项目元数据与依赖
│
├── api/                           # API 层
│   ├── __init__.py
│   ├── routes_tasks.py            # 任务 CRUD 端点 (POST/GET/DELETE /api/tasks)
│   ├── routes_stats.py            # 统计/权益/日记端点 (GET /api/tasks/{id}/stats|equity|rounds)
│   └── ws_manager.py              # WebSocket 连接管理器（广播/心跳/死连接清理）
│
├── engine/                        # ★ 核心引擎
│   ├── __init__.py
│   ├── betting.py                 # 纯数学：押注计算、PnL、胜率、最大回撤、夏普比率
│   ├── round_executor.py          # 回合编排器：结算→分析API→记录新注
│   ├── scheduler.py               # K线调度器（asyncio + heapq 优先级队列）
│   └── task_manager.py            # 多任务生命周期管理器（创建/启动/停止/恢复）
│
├── models/                        # 数据层
│   ├── __init__.py
│   ├── db.py                      # 异步 SQLite CRUD（aiosqlite，DDL + 索引）
│   └── schemas.py                 # Pydantic v2 请求/响应模型 + 枚举定义
│
├── frontend/                      # React 前端 (端口 18521，代理到 18520)
│   ├── vite.config.ts             # Vite 配置（TailwindCSS、代理规则）
│   ├── package.json               # React 19 / TypeScript 6 / Zustand 5 / lightweight-charts
│   └── src/
│       ├── App.tsx                # 主布局（顶栏 + 左侧任务列表 + 右侧详情面板）
│       ├── index.css              # 全局样式 + Tailwind 自定义主题（surface/accent 色系）
│       ├── main.tsx               # React 入口
│       ├── api/client.ts          # Axios HTTP 客户端（baseURL /api）
│       ├── store/useSimStore.ts   # Zustand 状态管理（任务、统计、权益、回合）
│       ├── hooks/useWebSocket.ts  # WebSocket 连接 Hook（自动重连）
│       ├── types/index.ts         # TypeScript 类型定义
│       └── components/
│           ├── TaskCard.tsx        # 任务卡片（状态指示灯、启动/停止/删除操作）
│           ├── CreateTaskModal.tsx # 新建任务弹窗（交易对、周期、押注参数）
│           ├── EquityChart.tsx     # 权益曲线图（lightweight-charts）
│           ├── StatsPanel.tsx      # 统计面板（胜率、盈亏、最大回撤、夏普比率）
│           └── RoundTable.tsx      # 交易回合日记表格（分页）
│
├── data/                          # SQLite 数据库文件（已 gitignore）
│   └── simulation.db
│
└── tests/                         # 测试套件（pytest-asyncio）
    ├── test_betting.py            # 押注计算、PnL、统计指标单元测试
    ├── test_db.py                 # 数据库 CRUD 集成测试
    ├── test_scheduler.py          # K线调度器单元测试（时间计算 + 调度逻辑）
    └── test_schemas.py            # Pydantic 模型验证测试
```

## 🔄 数据流

```
┌─────────────┐     HTTP POST      ┌──────────────┐
│   Frontend   │ ─────────────────> │  REST API    │
│  (port 18521)│ <── JSON/SSE ──── │  (port 18520) │
└──────┬───────┘                    └──────┬───────┘
       │ WebSocket                        │
       │ /ws                              │
       v                                  v
┌──────────────┐                  ┌──────────────┐
│  WsManager   │ <── broadcast ── │ TaskManager  │
│ (广播推送)    │                  │ (生命周期)    │
└──────────────┘                  └──────┬───────┘
                                         │
                          ┌──────────────┼──────────────┐
                          │              │              │
                          v              v              v
                   ┌──────────┐  ┌────────────┐  ┌──────────┐
                   │ Scheduler│  │RoundExecutor│  │  SQLite  │
                   │ (定时触发)│  │ (回合编排)  │  │ (持久化)  │
                   └──────────┘  └─────┬──────┘  └──────────┘
                                       │
                                       v
                                ┌──────────────┐
                                │  Analyze API │
                                │  (外部后端)   │
                                │  :8000        │
                                └──────────────┘
```

### 典型回合流程

```
K线收盘时间到达
    │
    ▼
Scheduler 触发回调 ──> execute_round(task_id)
    │
    ├── ① 结算上一局
    │      ├── 获取当前价格（或使用 trigger_kline_close）
    │      ├── 判定 WIN/LOSE（long: settle > entry, short: settle < entry）
    │      ├── 计算 PnL → 更新任务资金
    │      └── 更新 rounds 表 status=SETTLED
    │
    ├── ② 调用分析 API
    │      └── POST {analyze_api_url}?symbol={asset}&timeframe={timeframe}
    │          返回: {direction, score, confidence, indicator_*, structure_*, mechanics_*}
    │
    ├── ③ 计算押注
    │      ├── bet_mode=fixed → min(bet_amount, current_capital)
    │      └── bet_mode=percent → current_capital * bet_percent
    │
    └── ④ 记录新回合
           └── INSERT INTO rounds (status=BET_PLACED, bet_direction, bet_amount, ...)
                  ↓
           WsManager.broadcast({type: "round_completed", ...})
```

## ⚙️ 关键配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ANALYZE_API_URL` | `http://localhost:8000/api/v1/analyze/` | 外部分析 API 地址 |
| `ANALYZE_TIMEOUT` | `120` | 分析 API 超时（秒） |
| `ANALYZE_RETRY_COUNT` | `2` | 分析 API 重试次数 |
| `ANALYZE_RETRY_DELAY` | `10` | 重试间隔（秒） |
| `SIM_HOST` | `0.0.0.0` | 服务监听地址 |
| `SIM_PORT` | `18520` | 服务端口 |
| `DB_PATH` | `./data/simulation.db` | SQLite 数据库路径 |
| `KLINE_BUFFER_SECONDS` | `30` | K线收盘后延迟触发（秒） |
| `DEFAULT_INITIAL_CAPITAL` | `10000.0` | 默认初始资金 |
| `DEFAULT_BET_AMOUNT` | `100.0` | 默认固定押注金额 |
| `WS_HEARTBEAT_INTERVAL` | `30` | WebSocket 心跳间隔（秒） |

## 🧩 核心类与接口

### KlineScheduler (`engine/scheduler.py`)

基于 `heapq` 的异步 K 线收盘时间调度器。

```python
class KlineScheduler:
    def __init__(self, buffer_seconds: int = 30)           # buffer: K线收盘后延迟秒数
    def schedule(trigger_ts: float, task_id: str, callback) # 注册定时回调
    def cancel(task_id: str)                                # 取消某任务所有待执行事件
    async def run()                                         # 主循环（需 asyncio.create_task 启动）
    def stop()                                              # 停止调度
    @staticmethod calc_next_kline_close(timeframe, ts)      # 静态方法：计算下一根K线收盘UTC时间戳
```

**支持的时间周期**: `1m` `3m` `5m` `15m` `1h` `4h` `1d`

### TaskManager (`engine/task_manager.py`)

多任务生命周期管理器，所有数据库操作均通过 `models/db.py` 的 CRUD 函数。

```python
class TaskManager:
    async def create_task(asset, timeframe, bet_mode, ...)  → dict
    async def start_task(task_id)                            → dict | None
    async def stop_task(task_id)                             → dict | None
    async def delete_task(task_id)                           → bool
    async def list_tasks()                                   → list[dict]
    async def get_task(task_id)                              → dict | None
    async def recover_on_startup()                           # 崩溃恢复：重启所有 RUNNING 任务
```

### 押注计算 (`engine/betting.py`)

纯函数模块，无副作用、无 I/O。

```python
def calculate_bet(bet_mode, bet_amount, bet_percent, current_capital) → float
def calculate_pnl(direction, result, bet_amount, fee_rate)            → float
def calculate_win_rate(wins, total)                                   → float
def calculate_max_drawdown(equity_curve)                              → float
def calculate_sharpe_ratio(returns, risk_free_rate)                   → float
```

### WsManager (`api/ws_manager.py`)

WebSocket 连接管理器，支持广播和死连接自动清理。

```python
class WsManager:
    async def connect(ws)            # 接受连接并注册
    async def disconnect(ws)         # 移除连接
    async def broadcast(message)     # 向所有客户端广播 JSON 消息
    connection_count → int           # 当前连接数
```

**WebSocket 消息类型**（定义在 `models/schemas.py:WsMessageType`）：
- `task_started` / `task_stopped` / `task_deleted`
- `round_completed`
- `stats_updated`

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 健康检查 |
| `POST` | `/api/tasks` | 创建任务 |
| `GET` | `/api/tasks` | 列出所有任务 |
| `GET` | `/api/tasks/{id}` | 获取单个任务 |
| `POST` | `/api/tasks/{id}/start` | 启动任务 |
| `POST` | `/api/tasks/{id}/stop` | 停止任务 |
| `DELETE` | `/api/tasks/{id}` | 删除任务 |
| `GET` | `/api/tasks/{id}/stats` | 任务统计（胜率/盈亏/回撤/夏普） |
| `GET` | `/api/tasks/{id}/equity` | 权益曲线数据 |
| `GET` | `/api/tasks/{id}/rounds?offset=&limit=` | 交易回合日记（分页） |
| `WS` | `/ws` | WebSocket 实时推送 |

## 🗄️ 数据库设计

**tasks 表**：任务主表，记录交易对、周期、状态、资金、连胜/连败统计

**rounds 表**：每轮交易记录，包含：
- 触发 K 线信息（时间戳、开盘/收盘价）
- 分析结果（3 个 Agent 的分数/信心度/摘要、Fusion 共识原始数据）
- 押注信息（方向、金额、手续费）
- 结算信息（结算价、结果 WIN/LOSE/SKIP、PnL）

**关键索引**:
- `idx_rounds_task_id` — 按任务查回合
- `idx_rounds_task_seq` — 按任务+序号排序
- `idx_rounds_trigger` — 唯一索引，防重复触发同一根 K 线

## 🧪 测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行全部测试
pytest

# 仅运行特定模块
pytest tests/test_betting.py
pytest tests/test_db.py -v
pytest tests/test_scheduler.py -v
```

测试使用临时数据库（`tmp_db_path` fixture），不会污染生产数据。`conftest.py` 提供 session 级事件循环和 Windows 兼容的文件清理。

## 🚀 启动方式

```bash
# 后端（端口 18520）
cd simulation
python server.py
# 或: uvicorn server:app --host 0.0.0.0 --port 18520

# 前端（端口 18521，自动代理 API 到 18520）
cd simulation/frontend
npm install
npm run dev
```

前端 Vite 配置了代理规则：`/api` → `http://localhost:18520`，`/ws` → `ws://localhost:18520`。

## 🔗 依赖关系

```
simulation
  ├── 上游依赖: 外部分析 API (ANALYZE_API_URL, 默认 localhost:8000)
  ├── 下游消费者: 前端看板 (frontend/)
  └── 数据存储: SQLite (data/simulation.db)
```

**与主项目的关系**: simulation 是独立进程，通过 HTTP 调用主项目的 `/api/v1/analyze/` 端点获取交易信号。它不导入主项目的任何模块。

## 📝 代码规范

- **Python**: `from __future__ import annotations` 全局启用延迟求值；遵循 Ruff 规则（E/F/I/N/W/UP）
- **TypeScript**: ESLint + typescript-eslint，React Hooks 规则
- **风格**: 行宽 120 字符；Google-style docstring；中文注释
- **异步**: 全链路 `async/await`，SQLite 使用 `aiosqlite`
- **类型**: Pydantic v2（`from_attributes=True`），TypeScript strict mode
