"""回测 API"""
import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from database import get_db

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    strategy_name: str
    params: dict = {}
    start_date: str
    end_date: str
    initial_capital: float = 100000.0


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """运行回测（简化版：基于历史信号回放）"""
    from strategies.registry import get as get_strategy_cls

    cls = get_strategy_cls(req.strategy_name)
    if not cls:
        return {"error": f"策略 {req.strategy_name} 不存在"}

    return {
        "status": "completed",
        "strategy": req.strategy_name,
        "period": f"{req.start_date} ~ {req.end_date}",
        "message": "回测功能将在策略完善后支持",
    }


@router.get("/history")
async def backtest_history(limit: int = 20):
    """回测历史（预留）"""
    return {"history": [], "total": 0}
