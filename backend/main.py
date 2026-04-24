"""高频量化交易系统 — 主入口"""
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from database import init_db
from scheduler import start_scheduler
from strategies.registry import auto_discover
from api.portfolio import router as portfolio_router
from api.strategies import router as strategies_router
from api.trades import router as trades_router
from api.market import router as market_router
from api.backtest import router as backtest_router
from api.wechat_auth import router as wechat_auth_router
from api.wechat_pay import router as wechat_pay_router
from api.articles import router as articles_router

# WebSocket连接管理
ws_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    logger.info("=" * 60)
    logger.info("高频量化交易系统启动")
    logger.info("=" * 60)

    await init_db()
    logger.info("[启动] 数据库初始化完成")

    count = auto_discover()
    logger.info(f"[启动] 策略注册完成: {count} 个策略")

    await _register_strategies_to_db()
    logger.info("[启动] 策略数据库同步完成")

    start_scheduler()
    logger.info("[启动] 调度器已启动")
    logger.info("[启动] 系统就绪 ✓")

    yield

    # 关闭
    from scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown()
    logger.info("[关闭] 系统已停止")


app = FastAPI(
    title="高频量化交易系统",
    description="A股+美股模拟盘量化交易系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
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
            # 心跳
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_connections.remove(ws)


async def broadcast(data: dict):
    """向所有WebSocket连接广播"""
    import json
    msg = json.dumps(data, ensure_ascii=False)
    for ws in ws_connections[:]:
        try:
            await ws.send_text(msg)
        except Exception:
            ws_connections.remove(ws)


async def _register_strategies_to_db():
    """将自动发现的策略同步到数据库"""
    from database import get_db
    from strategies.registry import all_strategies

    db = await get_db()
    try:
        for name, cls in all_strategies().items():
            defaults = cls.default_params()
            market = "A_SHARE" if "a_share" in cls.__module__ else "US_STOCK"
            display_name = name.replace("_", " ").title()

            await db.execute(
                """INSERT OR IGNORE INTO strategies (name, display_name, market, description, params_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, display_name, market, "", json.dumps(defaults))
            )
        await db.commit()
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
    )
