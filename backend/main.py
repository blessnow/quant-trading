"""高频量化交易系统 — 主入口"""
import asyncio
import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

# 确保storage目录存在
from config import STORAGE_DIR
os.makedirs(STORAGE_DIR, exist_ok=True)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from database import init_db, close_db
from cache import init_redis, close_redis
from scheduler import start_scheduler
from strategies.registry import auto_discover
from rate_limit import setup_rate_limit
from api.portfolio import router as portfolio_router
from api.strategies import router as strategies_router
from api.trades import router as trades_router
from api.market import router as market_router
from api.backtest import router as backtest_router
from api.wechat_auth import router as wechat_auth_router
from api.wechat_pay import router as wechat_pay_router
from api.articles import router as articles_router
from api.phone_auth import router as phone_auth_router
from api.web_auth import router as web_auth_router
from api.chat import router as chat_router
from api.scheduler import router as scheduler_router
from api.health import router as health_router
from api.notifications import router as notifications_router

# WebSocket连接管理
ws_connections: list[WebSocket] = []
ws_log_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("高频量化交易系统启动")
    logger.info("=" * 60)

    await init_db()
    logger.info("[启动] 数据库初始化完成")

    await init_redis()
    logger.info("[启动] 缓存初始化完成")

    await _create_test_users()
    logger.info("[启动] 测试用户检查完成")

    count = auto_discover()
    logger.info(f"[启动] 策略注册完成: {count} 个策略")

    await _register_strategies_to_db()
    logger.info("[启动] 策略数据库同步完成")

    start_scheduler()
    logger.info("[启动] 调度器已启动")
    logger.info("[启动] 系统就绪 ✓")

    yield

    from scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown()
    await close_redis()
    await close_db()
    logger.info("[关闭] 系统已停止")


app = FastAPI(
    title="高频量化交易系统",
    description="A股+美股模拟盘量化交易系统",
    version="1.0.0",
    lifespan=lifespan,
)

setup_rate_limit(app)

from starlette.middleware.base import BaseHTTPMiddleware

class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)

app.add_middleware(TimeoutMiddleware)

import config

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
]
if config.FRONTEND_URL and config.FRONTEND_URL not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(config.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)
app.include_router(strategies_router)
app.include_router(trades_router)
app.include_router(market_router)
app.include_router(backtest_router)
app.include_router(wechat_auth_router)
app.include_router(wechat_pay_router)
app.include_router(articles_router)
app.include_router(phone_auth_router)
app.include_router(web_auth_router)
app.include_router(chat_router)
app.include_router(scheduler_router)
app.include_router(health_router)
app.include_router(notifications_router)


@app.get("/")
async def root():
    return {
        "name": "高频量化交易系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    ws_connections.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_connections.remove(ws)


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    """实时推送策略日志"""
    await ws.accept()
    ws_log_connections.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_log_connections.remove(ws)


async def broadcast(data: dict):
    """向所有WebSocket连接广播"""
    import json
    msg = json.dumps(data, ensure_ascii=False)
    for ws in ws_connections[:]:
        try:
            await ws.send_text(msg)
        except Exception:
            ws_connections.remove(ws)


async def broadcast_log(log_data: dict):
    """广播日志到所有日志WebSocket连接"""
    import json
    msg = json.dumps(log_data, ensure_ascii=False)
    for ws in ws_log_connections[:]:
        try:
            await ws.send_text(msg)
        except Exception:
            ws_log_connections.remove(ws)


async def _register_strategies_to_db():
    """将自动发现的策略同步到数据库，并为每个策略创建独立账户"""
    from database import get_db
    from strategies.registry import all_strategies
    import config

    db = await get_db()
    try:
        for name, cls in all_strategies().items():
            defaults = cls.default_params()
            market = "A_SHARE" if "a_share" in cls.__module__ else "US_STOCK"
            display_name = name.replace("_", " ")
            import re
            display_name = re.sub(r'([A-Z])', r' \1', display_name).strip().title()

            await db.execute(
                """INSERT OR IGNORE INTO strategies (name, display_name, market, description, params_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, display_name, market, "", json.dumps(defaults))
            )
            await db.execute(
                "UPDATE strategies SET display_name=? WHERE name=?",
                (display_name, name)
            )
        await db.commit()

        # 为每个策略创建独立账户
        async with db.execute("SELECT id, market FROM strategies") as cur:
            strategies = await cur.fetchall()
        for sid, market in strategies:
            await db.execute(
                """INSERT OR IGNORE INTO accounts (strategy_id, market, initial_capital, cash)
                   VALUES (?, ?, ?, ?)""",
                (sid, market, config.INITIAL_CAPITAL_PER_STRATEGY, config.INITIAL_CAPITAL_PER_STRATEGY)
            )
        await db.commit()
        logger.info(f"[启动] 为 {len(strategies)} 个策略创建独立账户，每个 {config.INITIAL_CAPITAL_PER_STRATEGY:.0f} 元")
    finally:
        await db.close()


async def _create_test_users():
    """创建测试用户：admin / 会员 / 非会员"""
    from database import get_db
    import config
    from auth import hash_password

    db = await get_db()
    try:
        pw = hash_password("123456")

        await db.execute(
            """INSERT OR REPLACE INTO users 
               (openid, phone, password_hash, nickname, login_type, is_member, is_admin) 
               VALUES ('phone_admin', '10000000001', ?, '管理员', 'phone', 1, 1)""",
            (pw,)
        )
        await db.execute(
            """INSERT OR REPLACE INTO users 
               (openid, phone, password_hash, nickname, login_type, is_member, is_admin) 
               VALUES ('phone_member', '10000000002', ?, '会员用户', 'phone', 1, 0)""",
            (pw,)
        )
        await db.execute(
            """INSERT OR REPLACE INTO users 
               (openid, phone, password_hash, nickname, login_type, is_member, is_admin) 
               VALUES ('phone_guest', '10000000003', ?, '普通用户', 'phone', 0, 0)""",
            (pw,)
        )

        await db.commit()
        logger.info("[启动] 测试用户已创建: admin(10000000001) / member(10000000002) / guest(10000000003)")
    finally:
        await db.close()


if __name__ == "__main__":
    import uvicorn
    import config

    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level="info",
        timeout_keep_alive=1200,
        limit_concurrency=100,
    )
