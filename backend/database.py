"""数据库初始化和连接管理"""
import aiosqlite
from config import DB_PATH, DATA_DIR, INITIAL_CAPITAL_A_SHARE, INITIAL_CAPITAL_US_STOCK
import os

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY,
    market      TEXT NOT NULL UNIQUE,
    initial_capital REAL NOT NULL DEFAULT 0,
    cash        REAL NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategies (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    market      TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    is_active   INTEGER NOT NULL DEFAULT 1,
    max_position_pct REAL NOT NULL DEFAULT 0.20,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    shares      REAL NOT NULL,
    avg_cost    REAL NOT NULL,
    buy_date    TEXT NOT NULL,
    sellable_date TEXT NOT NULL,
    current_price REAL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    side        TEXT NOT NULL,
    price       REAL NOT NULL,
    shares      REAL NOT NULL,
    notional    REAL NOT NULL,
    commission  REAL NOT NULL DEFAULT 0,
    slippage    REAL NOT NULL DEFAULT 0,
    pnl         REAL,
    signal_data TEXT,
    executed_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id          INTEGER PRIMARY KEY,
    market      TEXT NOT NULL,
    total_value REAL NOT NULL,
    cash        REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    daily_return_pct REAL NOT NULL,
    snapshot_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL DEFAULT '15:00',
    UNIQUE(market, snapshot_date, snapshot_time)
);

CREATE TABLE IF NOT EXISTS strategy_performance (
    id              INTEGER PRIMARY KEY,
    strategy_id     INTEGER NOT NULL UNIQUE,
    total_trades    INTEGER NOT NULL DEFAULT 0,
    win_trades      INTEGER NOT NULL DEFAULT 0,
    total_pnl       REAL NOT NULL DEFAULT 0,
    max_drawdown_pct REAL NOT NULL DEFAULT 0,
    sharpe_ratio    REAL,
    win_rate        REAL NOT NULL DEFAULT 0,
    avg_hold_bars   REAL,
    peak_value      REAL NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id          INTEGER PRIMARY KEY,
    event_type  TEXT NOT NULL,
    strategy_id INTEGER,
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategy_param_history (
    id          INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,
    old_params  TEXT NOT NULL,
    new_params  TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    sharpe_before REAL,
    sharpe_after  REAL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE IF NOT EXISTS notification_config (
    id          INTEGER PRIMARY KEY,
    channel     TEXT NOT NULL,
    is_enabled  INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    openid      TEXT NOT NULL UNIQUE,
    nickname    TEXT NOT NULL DEFAULT '',
    avatar_url  TEXT NOT NULL DEFAULT '',
    phone       TEXT,
    is_member   INTEGER NOT NULL DEFAULT 0,
    member_expire_at TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    order_no    TEXT NOT NULL UNIQUE,
    trade_no    TEXT,
    plan        TEXT NOT NULL,
    amount      REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    paid_at     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS strategy_equity_snapshots (
    id              INTEGER PRIMARY KEY,
    strategy_id     INTEGER NOT NULL,
    total_value     REAL NOT NULL,
    invested        REAL NOT NULL,
    unrealized_pnl  REAL NOT NULL,
    daily_return_pct REAL NOT NULL DEFAULT 0,
    snapshot_date   TEXT NOT NULL,
    snapshot_time   TEXT NOT NULL DEFAULT '15:00',
    UNIQUE(strategy_id, snapshot_date, snapshot_time),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE IF NOT EXISTS benchmark_snapshots (
    id              INTEGER PRIMARY KEY,
    symbol          TEXT NOT NULL,
    name            TEXT NOT NULL,
    market          TEXT NOT NULL,
    close_price     REAL NOT NULL,
    return_pct      REAL NOT NULL DEFAULT 0,
    snapshot_date   TEXT NOT NULL,
    UNIQUE(symbol, snapshot_date)
);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT 'market',  -- market/strategy/opinion/tutorial
    tag         TEXT NOT NULL DEFAULT '',         -- 逗号分隔标签
    is_published INTEGER NOT NULL DEFAULT 1,
    view_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        # 初始化账户
        await db.execute(
            "INSERT OR IGNORE INTO accounts (market, initial_capital, cash) VALUES (?, ?, ?)",
            ("A_SHARE", INITIAL_CAPITAL_A_SHARE, INITIAL_CAPITAL_A_SHARE)
        )
        await db.execute(
            "INSERT OR IGNORE INTO accounts (market, initial_capital, cash) VALUES (?, ?, ?)",
            ("US_STOCK", INITIAL_CAPITAL_US_STOCK, INITIAL_CAPITAL_US_STOCK)
        )
        await db.commit()
