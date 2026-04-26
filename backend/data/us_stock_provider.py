"""美股数据提供层"""
import asyncio
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pandas as pd
import requests
import yfinance as yf
from loguru import logger

_executor = ThreadPoolExecutor(max_workers=5)
_history_cache: dict[str, pd.DataFrame] = {}

# 关注的美股标的池
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "NFLX", "CRM", "ADBE", "INTC", "PYPL", "UBER", "SQ", "SHOP",
    "SPOT", "SNAP", "PLTR", "COIN", "RIVN", "SOFI", "NIO", "XPEV",
    "PDD", "BABA", "JD", "BIDU", "NTES", "TME", "VIPS", "TAL",
    "DIS", "BA", "CAT", "GS", "JPM", "V", "MA", "UNH",
    "JNJ", "PFE", "MRK", "ABT", "LLY", "TMO", "UNP", "HON",
]


def get_stock_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    cache_key = f"{symbol}_{period}_{interval}"
    if cache_key in _history_cache:
        return _history_cache[cache_key].copy()
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        _history_cache[cache_key] = df
        return df.copy()
    except Exception as e:
        logger.debug(f"获取 {symbol} 历史失败: {e}")
        return pd.DataFrame()


def get_current_price(symbol: str) -> Optional[float]:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        return info.last_price if hasattr(info, 'last_price') else None
    except Exception:
        try:
            hist = yf.Ticker(symbol).history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return None


def get_realtime_quotes(symbols: list[str] = None) -> pd.DataFrame:
    symbols = symbols or DEFAULT_UNIVERSE
    items = []
    
    def fetch_one(sym: str) -> dict | None:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.fast_info
            price = info.last_price if hasattr(info, 'last_price') else None
            prev = info.previous_close if hasattr(info, 'previous_close') else None
            if price and prev and prev > 0:
                change_pct = round((price - prev) / prev * 100, 2)
                return {
                    "symbol": sym,
                    "price": price,
                    "pre_close": prev,
                    "change_pct": change_pct,
                    "high": info.day_high if hasattr(info, 'day_high') else price,
                    "low": info.day_low if hasattr(info, 'day_low') else price,
                    "volume": info.last_volume if hasattr(info, 'last_volume') else 0,
                }
        except Exception:
            pass
        return None
    
    for sym in symbols:
        result = fetch_one(sym)
        if result:
            items.append(result)
    
    if not items:
        return pd.DataFrame()
    logger.info(f"[美股行情] 获取 {len(items)} 只股票报价")
    return pd.DataFrame(items)


def get_usd_cny_rate() -> float:
    try:
        ticker = yf.Ticker("USDCNY=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 4)
    except Exception:
        pass
    return 7.25


def get_gap_stocks(symbols: list[str] = None, min_gap_pct: float = 3.0) -> pd.DataFrame:
    """扫描隔夜跳空的美股"""
    symbols = symbols or DEFAULT_UNIVERSE
    gap_stocks = []
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if len(hist) < 2:
                continue
            prev_close = hist["Close"].iloc[-2]
            today_open = hist["Open"].iloc[-1]
            if prev_close <= 0:
                continue
            gap_pct = (today_open - prev_close) / prev_close * 100
            if abs(gap_pct) >= min_gap_pct:
                gap_stocks.append({
                    "symbol": sym,
                    "prev_close": prev_close,
                    "open": today_open,
                    "gap_pct": round(gap_pct, 2),
                    "price": float(hist["Close"].iloc[-1]),
                    "volume": float(hist["Volume"].iloc[-1]),
                })
        except Exception:
            pass
    return pd.DataFrame(gap_stocks)


def get_momentum_stocks(symbols: list[str] = None, lookback: int = 20, top_n: int = 20) -> pd.DataFrame:
    """获取动量排名靠前的美股"""
    symbols = symbols or DEFAULT_UNIVERSE
    momentum = []
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period=f"{lookback + 10}d")
            if len(hist) < lookback:
                continue
            close = hist["Close"]
            ret = (close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback] * 100
            vol_avg = hist["Volume"].iloc[-5:].mean()
            vol_latest = hist["Volume"].iloc[-1]
            vol_ratio = vol_latest / vol_avg if vol_avg > 0 else 0
            high_20d = close.iloc[-lookback:].max()
            at_high = close.iloc[-1] >= high_20d * 0.98
            momentum.append({
                "symbol": sym,
                "price": float(close.iloc[-1]),
                "momentum_20d": round(float(ret), 2),
                "volume_ratio": round(float(vol_ratio), 2),
                "at_20d_high": at_high,
                "high_20d": float(high_20d),
            })
        except Exception:
            pass
    df = pd.DataFrame(momentum)
    if df.empty:
        return df
    return df.sort_values("momentum_20d", ascending=False).head(top_n).reset_index(drop=True)


def get_index_history(symbol: str = "^NDX", days: int = 90) -> list[dict]:
    """获取美股指数历史收盘价

    常用symbol: ^NDX(纳斯达克100), ^GSPC(标普500), ^DJI(道琼斯)
    """
    cache_key = f"idx_{symbol}_{days}"
    if cache_key in _history_cache:
        return _history_cache[cache_key]
    
    result = _get_index_history_yfinance(symbol, days)
    if result:
        _history_cache[cache_key] = result
        return result
    
    logger.warning(f"[美股指数] yfinance失败，尝试tushare备用")
    result = _get_index_history_tushare(symbol, days)
    if result:
        _history_cache[cache_key] = result
    return result


def _get_index_history_yfinance(symbol: str, days: int) -> list[dict]:
    """yfinance获取指数历史"""
    try:
        import time
        for attempt in range(3):
            try:
                time.sleep(2 + attempt * 2)
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=f"{days + 10}d", interval="1d")
                if df.empty:
                    continue
                df = df.tail(days).reset_index()
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]
                result = []
                for _, row in df.iterrows():
                    date_val = row.get("date")
                    if hasattr(date_val, "strftime"):
                        date_str = date_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(date_val)[:10]
                    result.append({"date": date_str, "close": float(row["close"])})
                logger.info(f"[美股指数] {symbol} 获取 {len(result)} 条数据")
                return result
            except Exception as e:
                if "Rate limited" in str(e) and attempt < 2:
                    logger.warning(f"[美股指数] yfinance限流，等待重试...")
                    time.sleep(10)
                else:
                    raise
        return []
    except Exception as e:
        logger.error(f"获取指数 {symbol} 历史失败: {e}")
        return []


def _get_index_history_tushare(symbol: str, days: int) -> list[dict]:
    """stooq备用获取美股指数历史"""
    try:
        import time
        from datetime import datetime, timedelta
        
        symbol_map = {
            "^NDX": "^ndq",
            "^GSPC": "^spx",
            "^DJI": "^dji",
        }
        stooq_symbol = symbol_map.get(symbol)
        if not stooq_symbol:
            return []
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)
        
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&d1={start_date.strftime('%Y%m%d')}&d2={end_date.strftime('%Y%m%d')}&i=d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200 or not r.text:
            return []
        
        lines = r.text.strip().split('\n')
        if len(lines) < 2:
            return []
        
        result = []
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) >= 5:
                date_str = parts[0]
                close = float(parts[4])
                result.append({"date": date_str, "close": close})
        
        result = result[-days:]
        logger.info(f"[美股指数-Stooq] {symbol} 获取 {len(result)} 条数据")
        return result
    except Exception as e:
        logger.error(f"[美股指数-Stooq] 失败: {e}")
        return []
