"""数据库初始化和连接管理 — 使用连接池"""
import aiosqlite
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from config import DB_PATH, DATA_DIR, INITIAL_CAPITAL_A_SHARE, INITIAL_CAPITAL_US_STOCK, INITIAL_CAPITAL_PER_STRATEGY
import os
import logging

class DatabasePool:
    """数据库连接池"""
    _instance: Optional['DatabasePool'] = None
    _pool: list[aiosqlite.Connection] = []
    _pool_size: int = 10
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self, pool_size: int = 10):
        """初始化连接池"""
        self._pool_size = pool_size
        os.makedirs(DATA_DIR, exist_ok=True)
        
        for _ in range(pool_size):
            conn = await aiosqlite.connect(DB_PATH)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=-64000")
            self._pool.append(conn)
        
        logging.info(f"[数据库] 连接池初始化完成，大小={pool_size}")
    
    async def acquire(self) -> aiosqlite.Connection:
        """获取连接"""
        async with self._lock:
            if self._pool:
                return self._pool.pop()
            conn = await aiosqlite.connect(DB_PATH)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            return conn
    
    async def release(self, conn: aiosqlite.Connection):
        """释放连接"""
        async with self._lock:
            if len(self._pool) < self._pool_size:
                self._pool.append(conn)
            else:
                await conn.close()
    
    async def close_all(self):
        """关闭所有连接"""
        async with self._lock:
            for conn in self._pool:
                await conn.close()
            self._pool.clear()
        logging.info("[数据库] 连接池已关闭")

db_pool = DatabasePool()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY,
    strategy_id INTEGER,
    market      TEXT NOT NULL,
    initial_capital REAL NOT NULL DEFAULT 0,
    cash        REAL NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(strategy_id, market),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
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
    user_id     INTEGER NOT NULL DEFAULT 1,
    channel     TEXT NOT NULL,
    is_enabled  INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, channel),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    openid      TEXT UNIQUE,
    nickname    TEXT NOT NULL DEFAULT '',
    avatar_url  TEXT NOT NULL DEFAULT '',
    phone       TEXT UNIQUE,
    password_hash TEXT,
    login_type  TEXT NOT NULL DEFAULT 'wechat',
    web_openid  TEXT UNIQUE,
    unionid     TEXT UNIQUE,
    is_member   INTEGER NOT NULL DEFAULT 0,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    member_expire_at TEXT,
    last_login_at TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS login_sessions (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL UNIQUE,
    qr_code_url TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    user_id     INTEGER,
    token       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL,
    confirmed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS payment_sessions (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL UNIQUE,
    order_no    TEXT NOT NULL,
    user_id     INTEGER NOT NULL,
    qr_code_url TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL,
    paid_at     TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (order_no) REFERENCES orders(order_no)
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

CREATE TABLE IF NOT EXISTS strategy_logs (
    id          INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,
    strategy_name TEXT NOT NULL,
    level       TEXT NOT NULL DEFAULT 'info',
    message     TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT 'market',
    tag         TEXT NOT NULL DEFAULT '',
    is_published INTEGER NOT NULL DEFAULT 1,
    view_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    strategy_id TEXT NOT NULL,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    tool_calls  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_positions_strategy_id ON positions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_logs_strategy_id ON strategy_logs(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_logs_created_at ON strategy_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
"""

async def init_db():
    """初始化数据库"""
    await db_pool.initialize(pool_size=10)
    
    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)
        
        try:
            async with db.execute("SELECT strategy_id FROM accounts LIMIT 1") as cur:
                await cur.fetchone()
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE accounts RENAME TO accounts_old")
            await db.execute("""
                CREATE TABLE accounts (
                    id          INTEGER PRIMARY KEY,
                    strategy_id INTEGER,
                    market      TEXT NOT NULL,
                    initial_capital REAL NOT NULL DEFAULT 0,
                    cash        REAL NOT NULL DEFAULT 0,
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(strategy_id, market),
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """)
            await db.execute("""
                INSERT INTO accounts (strategy_id, market, initial_capital, cash, updated_at)
                SELECT NULL, market, initial_capital, cash, updated_at FROM accounts_old
            """)
            await db.execute("DROP TABLE accounts_old")
            logging.info("[数据库] accounts 表迁移完成：新增 strategy_id 列")

        async with db.execute("SELECT id, market FROM strategies") as cur:
            strategies = await cur.fetchall()
        for sid, market in strategies:
            await db.execute(
                "INSERT OR IGNORE INTO accounts (strategy_id, market, initial_capital, cash) VALUES (?, ?, ?, ?)",
                (sid, market, INITIAL_CAPITAL_PER_STRATEGY, INITIAL_CAPITAL_PER_STRATEGY)
            )

        await db.commit()

        try:
            async with db.execute("SELECT password_hash FROM users LIMIT 1") as cur:
                await cur.fetchone()
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            await db.execute("ALTER TABLE users ADD COLUMN login_type TEXT NOT NULL DEFAULT 'wechat'")
            await db.execute("ALTER TABLE users ADD COLUMN web_openid TEXT")
            await db.execute("ALTER TABLE users ADD COLUMN unionid TEXT")
            await db.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
            await db.commit()
            logging.info("[数据库] users 表迁移完成：新增登录相关字段")

        try:
            async with db.execute("SELECT user_id FROM notification_config LIMIT 1") as cur:
                await cur.fetchone()
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE notification_config ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            await db.commit()
            logging.info("[数据库] notification_config 表迁移完成：新增 user_id 列")

        try:
            async with db.execute("SELECT is_admin FROM users LIMIT 1") as cur:
                await cur.fetchone()
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            await db.commit()
            logging.info("[数据库] users 表迁移完成：新增 is_admin 列")

        try:
            async with db.execute("SELECT last_login_at FROM users LIMIT 1") as cur:
                await cur.fetchone()
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
            await db.commit()
            logging.info("[数据库] users 表迁移完成：新增 last_login_at 列")

        logging.info("[数据库] 初始化完成")
    finally:
        await db.close()


async def close_db():
    """关闭数据库连接池"""
    await db_pool.close_all()


async def get_db():
    """获取数据库连接（向后兼容）

    旧代码: db = await get_db() / try / finally / await db.close()
    新代码: async with get_db() as db: ...
    两者都支持，close() 实际是释放回连接池。
    """
    conn = await db_pool.acquire()
    original_close = conn.close

    async def _release_instead_of_close():
        await db_pool.release(conn)

    conn.close = _release_instead_of_close
    return conn
