"""市场状态检测"""
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from loguru import logger

CST = ZoneInfo("Asia/Shanghai")
ET = ZoneInfo("America/New_York")

# 美股休市日（2024-2026主要节假日）
US_HOLIDAYS = {
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27",
    "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-04", "2026-09-07", "2026-11-26", "2026-12-25",
}


def is_a_share_market_open(now: datetime = None) -> bool:
    now = now or datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    return morning or afternoon


def is_us_market_open(now: datetime = None) -> bool:
    now = now or datetime.now(ET)
    date_str = now.strftime("%Y-%m-%d")
    if now.weekday() >= 5 or date_str in US_HOLIDAYS:
        return False
    return time(9, 30) <= now.time() <= time(16, 0)


def get_market_status() -> dict:
    now_cst = datetime.now(CST)
    now_et = datetime.now(ET)
    return {
        "a_share": {
            "is_open": is_a_share_market_open(now_cst),
            "current_time": now_cst.strftime("%Y-%m-%d %H:%M:%S CST"),
            "next_open": _next_a_share_open(now_cst),
        },
        "us_stock": {
            "is_open": is_us_market_open(now_et),
            "current_time": now_et.strftime("%Y-%m-%d %H:%M:%S ET"),
            "next_open": _next_us_open(now_et),
        },
    }


def _next_a_share_open(now: datetime) -> str:
    d = now.date()
    t = now.time()
    if now.weekday() < 5 and t < time(9, 30):
        return f"{d} 09:30 CST"
    # 下一个工作日
    for i in range(1, 7):
        next_d = d + timedelta(days=i)
        if next_d.weekday() < 5:
            return f"{next_d} 09:30 CST"
    return ""


def _next_us_open(now: datetime) -> str:
    d = now.date()
    t = now.time()
    date_str = d.strftime("%Y-%m-%d")
    if now.weekday() < 5 and date_str not in US_HOLIDAYS and t < time(9, 30):
        return f"{d} 09:30 ET"
    for i in range(1, 7):
        next_d = d + timedelta(days=i)
        next_str = next_d.strftime("%Y-%m-%d")
        if next_d.weekday() < 5 and next_str not in US_HOLIDAYS:
            return f"{next_d} 09:30 ET"
    return ""


def is_trading_day(market: str, date: datetime = None) -> bool:
    if market == "A_SHARE":
        d = date or datetime.now(CST)
        return d.weekday() < 5
    elif market == "US_STOCK":
        d = date or datetime.now(ET)
        date_str = d.strftime("%Y-%m-%d")
        return d.weekday() < 5 and date_str not in US_HOLIDAYS
    return False


def get_today_str(market: str) -> str:
    if market == "A_SHARE":
        return datetime.now(CST).strftime("%Y-%m-%d")
    return datetime.now(ET).strftime("%Y-%m-%d")


def get_next_trading_day(market: str, date_str: str) -> Optional[str]:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    tz = CST if market == "A_SHARE" else ET
    for i in range(1, 10):
        next_d = dt + timedelta(days=i)
        if is_trading_day(market, next_d):
            return next_d.strftime("%Y-%m-%d")
    return None
