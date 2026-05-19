"""
异步 SQLite 数据库层 — 任务表 + 回合表 CRUD
"""
import aiosqlite
from contextlib import asynccontextmanager
from config import settings

# ── 表结构 DDL ──

DDL_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    asset           TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'STOPPED',
    bet_amount      REAL NOT NULL,
    bet_mode        TEXT NOT NULL DEFAULT 'fixed',
    bet_percent     REAL DEFAULT NULL,
    fee_rate        REAL NOT NULL DEFAULT 0.0,
    initial_capital REAL NOT NULL,
    current_capital REAL NOT NULL,
    total_rounds    INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    skips           INTEGER NOT NULL DEFAULT 0,
    best_win_streak     INTEGER NOT NULL DEFAULT 0,
    worst_lose_streak   INTEGER NOT NULL DEFAULT 0,
    current_streak      TEXT DEFAULT NULL,
    last_kline_ts       TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
)
"""

DDL_ROUNDS = """
CREATE TABLE IF NOT EXISTS rounds (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    round_seq       INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'BET_PLACED',

    trigger_kline_ts    TEXT NOT NULL,
    trigger_kline_open  REAL,
    trigger_kline_close REAL,

    direction       TEXT,
    score           REAL,
    confidence      REAL,
    entry_point     REAL,

    indicator_score         REAL,
    indicator_confidence    REAL,
    structure_score         REAL,
    structure_confidence    REAL,
    mechanics_score         REAL,
    mechanics_confidence    REAL,

    indicator_summary   TEXT,
    structure_summary   TEXT,
    mechanics_summary   TEXT,
    fusion_raw          TEXT,

    bet_direction   TEXT,
    bet_amount      REAL,
    fee_amount      REAL DEFAULT 0,

    settle_kline_ts     TEXT,
    settle_price        REAL,
    result              TEXT,
    pnl                 REAL,

    created_at          TEXT NOT NULL,
    settled_at          TEXT
)
"""

DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_rounds_task_id ON rounds(task_id);
CREATE INDEX IF NOT EXISTS idx_rounds_task_seq ON rounds(task_id, round_seq);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rounds_trigger ON rounds(task_id, trigger_kline_ts);
"""


async def init_db(db_path: str | None = None) -> aiosqlite.Connection:
    """初始化数据库：创建表 + 索引，返回连接"""
    path = db_path or settings.DB_PATH
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute(DDL_TASKS)
    await db.execute(DDL_ROUNDS)
    for stmt in DDL_INDEXES.split(";"):
        stmt = stmt.strip()
        if stmt:
            await db.execute(stmt)
    await db.commit()
    return db


@asynccontextmanager
async def get_db(db_path: str | None = None):
    """异步上下文管理器：自动关闭连接"""
    path = db_path or settings.DB_PATH
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# ═══════════════════════════════════════════
#  Task CRUD
# ═══════════════════════════════════════════

async def create_task(db: aiosqlite.Connection, data: dict) -> str:
    """创建任务，返回 task_id"""
    await db.execute(
        """INSERT INTO tasks (id, asset, timeframe, status, bet_amount, bet_mode, bet_percent,
           fee_rate, initial_capital, current_capital, created_at, updated_at)
           VALUES (:id, :asset, :timeframe, :status, :bet_amount, :bet_mode, :bet_percent,
           :fee_rate, :initial_capital, :current_capital, :created_at, :updated_at)""",
        data,
    )
    await db.commit()
    return data["id"]


async def get_task(db: aiosqlite.Connection, task_id: str) -> dict | None:
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_tasks(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute("SELECT * FROM tasks ORDER BY created_at DESC") as cursor:
        return [dict(row) for row in await cursor.fetchall()]


async def update_task_status(db: aiosqlite.Connection, task_id: str, status: str) -> None:
    await db.execute(
        "UPDATE tasks SET status = :status, updated_at = :now WHERE id = :id",
        {"status": status, "now": _now(), "id": task_id},
    )
    await db.commit()


async def update_task_capital(db: aiosqlite.Connection, task_id: str, new_capital: float, result: str) -> None:
    """更新资金，同时更新胜负统计和连胜/连败"""
    task = await get_task(db, task_id)
    if not task:
        return

    wins = task["wins"]
    losses = task["losses"]
    skips = task["skips"]
    best_ws = task["best_win_streak"]
    worst_ls = task["worst_lose_streak"]
    cur_streak = task["current_streak"]

    if result == "WIN":
        wins += 1
        if cur_streak and cur_streak.startswith("W"):
            streak_count = int(cur_streak[1:]) + 1
        else:
            streak_count = 1
        cur_streak = f"W{streak_count}"
        best_ws = max(best_ws, streak_count)
    elif result == "LOSE":
        losses += 1
        if cur_streak and cur_streak.startswith("L"):
            streak_count = int(cur_streak[1:]) + 1
        else:
            streak_count = 1
        cur_streak = f"L{streak_count}"
        worst_ls = max(worst_ls, streak_count)
    elif result == "SKIP":
        skips += 1
        cur_streak = None

    await db.execute(
        """UPDATE tasks SET current_capital = :cap, total_rounds = :total,
           wins = :wins, losses = :losses, skips = :skips,
           best_win_streak = :bws, worst_lose_streak = :wls,
           current_streak = :streak, updated_at = :now
           WHERE id = :id""",
        {
            "cap": new_capital, "total": task["total_rounds"] + 1,
            "wins": wins, "losses": losses, "skips": skips,
            "bws": best_ws, "wls": worst_ls, "streak": cur_streak,
            "now": _now(), "id": task_id,
        },
    )
    await db.commit()


async def update_task_last_kline(db: aiosqlite.Connection, task_id: str, kline_ts: str) -> None:
    await db.execute(
        "UPDATE tasks SET last_kline_ts = :ts, updated_at = :now WHERE id = :id",
        {"ts": kline_ts, "now": _now(), "id": task_id},
    )
    await db.commit()


async def delete_task(db: aiosqlite.Connection, task_id: str) -> None:
    await db.execute("DELETE FROM rounds WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.commit()


async def get_running_tasks(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute("SELECT * FROM tasks WHERE status = 'RUNNING'") as cursor:
        return [dict(row) for row in await cursor.fetchall()]


# ═══════════════════════════════════════════
#  Round CRUD
# ═══════════════════════════════════════════

async def insert_round(db: aiosqlite.Connection, data: dict) -> str | None:
    """插入回合，遇唯一约束冲突返回 None"""
    try:
        await db.execute(
            """INSERT INTO rounds (id, task_id, round_seq, status,
               trigger_kline_ts, trigger_kline_open, trigger_kline_close,
               direction, score, confidence, entry_point,
               indicator_score, indicator_confidence,
               structure_score, structure_confidence,
               mechanics_score, mechanics_confidence,
               indicator_summary, structure_summary, mechanics_summary, fusion_raw,
               bet_direction, bet_amount, fee_amount, created_at)
               VALUES (:id, :task_id, :round_seq, :status,
               :trigger_kline_ts, :trigger_kline_open, :trigger_kline_close,
               :direction, :score, :confidence, :entry_point,
               :indicator_score, :indicator_confidence,
               :structure_score, :structure_confidence,
               :mechanics_score, :mechanics_confidence,
               :indicator_summary, :structure_summary, :mechanics_summary, :fusion_raw,
               :bet_direction, :bet_amount, :fee_amount, :created_at)""",
            data,
        )
        await db.commit()
        return data["id"]
    except aiosqlite.IntegrityError:
        return None


async def get_round(db: aiosqlite.Connection, round_id: str) -> dict | None:
    async with db.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_latest_round(db: aiosqlite.Connection, task_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM rounds WHERE task_id = ? ORDER BY round_seq DESC LIMIT 1", (task_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_rounds_by_task(db: aiosqlite.Connection, task_id: str, offset: int = 0, limit: int = 50) -> list[dict]:
    async with db.execute(
        "SELECT * FROM rounds WHERE task_id = ? ORDER BY round_seq DESC LIMIT ? OFFSET ?",
        (task_id, limit, offset),
    ) as cursor:
        return [dict(row) for row in await cursor.fetchall()]


async def get_unsettled_round(db: aiosqlite.Connection, task_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM rounds WHERE task_id = ? AND status = 'BET_PLACED' ORDER BY round_seq DESC LIMIT 1",
        (task_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def settle_round(db: aiosqlite.Connection, round_id: str, settle_price: float, result: str, pnl: float) -> None:
    await db.execute(
        """UPDATE rounds SET status = 'SETTLED', settle_price = :price,
           result = :result, pnl = :pnl, settled_at = :now WHERE id = :id""",
        {"price": settle_price, "result": result, "pnl": pnl, "now": _now(), "id": round_id},
    )
    await db.commit()


async def get_round_count(db: aiosqlite.Connection, task_id: str) -> int:
    async with db.execute("SELECT COUNT(*) as c FROM rounds WHERE task_id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
        return row["c"] if row else 0


async def get_equity_curve(db: aiosqlite.Connection, task_id: str) -> list[dict]:
    async with db.execute(
        "SELECT round_seq, pnl FROM rounds WHERE task_id = ? AND pnl IS NOT NULL ORDER BY round_seq ASC",
        (task_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    cumulative = 0.0
    result = []
    for row in rows:
        cumulative += row["pnl"] or 0.0
        result.append({"round_seq": row["round_seq"], "pnl": row["pnl"], "cumulative_pnl": round(cumulative, 2)})
    return result


async def get_task_stats(db: aiosqlite.Connection, task_id: str) -> dict:
    task = await get_task(db, task_id)
    if not task:
        return {}

    async with db.execute(
        "SELECT result, pnl FROM rounds WHERE task_id = ? AND result IS NOT NULL", (task_id,)
    ) as cursor:
        rows = await cursor.fetchall()

    pnl_list = [r["pnl"] for r in rows if r["pnl"] is not None]
    total_pnl = sum(pnl_list)
    completed = task["wins"] + task["losses"]
    win_rate = task["wins"] / completed if completed > 0 else 0.0

    peak = task["initial_capital"]
    max_dd = 0.0
    running = task["initial_capital"]
    for p in pnl_list:
        running += p
        peak = max(peak, running)
        dd = (peak - running) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    if len(pnl_list) >= 2:
        mean = sum(pnl_list) / len(pnl_list)
        variance = sum((p - mean) ** 2 for p in pnl_list) / (len(pnl_list) - 1)
        std = variance ** 0.5
        sharpe = mean / std if std > 0 else 0.0
    else:
        sharpe = 0.0

    gross_profit = sum(p for p in pnl_list if p > 0)
    gross_loss = abs(sum(p for p in pnl_list if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    return {
        "task_id": task_id,
        "total_rounds": task["total_rounds"],
        "wins": task["wins"],
        "losses": task["losses"],
        "skips": task["skips"],
        "win_rate": round(win_rate, 4),
        "total_pnl": round(total_pnl, 2),
        "current_capital": round(task["current_capital"], 2),
        "roi": round((task["current_capital"] - task["initial_capital"]) / task["initial_capital"], 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_ratio": round(sharpe, 4),
        "profit_factor": round(profit_factor, 4),
        "best_win_streak": task["best_win_streak"],
        "worst_lose_streak": task["worst_lose_streak"],
        "current_streak": task["current_streak"],
    }


# ── 辅助 ──

def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
