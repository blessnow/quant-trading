"""A股数据提供层 — 移植自 stock/data_fetcher.py"""
import math
import re
import time
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd
import requests
from loguru import logger

HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
MAX_RETRIES = 3
RETRY_DELAY = 2

_history_cache: dict[str, pd.DataFrame] = {}
_code_list_cache: list[str] | None = None
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CODE_LIST_FILE = CACHE_DIR / "a_share_codes.csv"


def _retry(fn, retries=MAX_RETRIES, delay=RETRY_DELAY):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"请求失败({attempt+1}/{retries}), {delay}s后重试: {e}")
                time.sleep(delay)
            else:
                raise


def _code_to_sina(code: str) -> str:
    code = str(code).strip()
    if code.startswith("6") or code.startswith("9"):
        return f"sh{code}"
    return f"sz{code}"


def get_all_codes() -> list[str]:
    global _code_list_cache
    if _code_list_cache is not None:
        return _code_list_cache
    if CODE_LIST_FILE.exists():
        df = pd.read_csv(CODE_LIST_FILE, dtype={"code": str})
        _code_list_cache = df["code"].tolist()
        logger.info(f"[本地缓存] 加载 {len(_code_list_cache)} 只A股代码")
        return _code_list_cache
    try:
        df = _retry(ak.stock_info_a_code_name)
        codes = df["code"].astype(str).tolist()
        CODE_LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        df[["code", "name"]].to_csv(CODE_LIST_FILE, index=False)
        _code_list_cache = codes
        logger.info(f"[akshare] 获取并缓存 {len(codes)} 只A股代码")
        return codes
    except Exception as e:
        logger.error(f"获取股票代码列表失败: {e}")
        return []


def _parse_sina_hq_line(line: str) -> dict | None:
    m = re.match(r'var hq_str_(s[hz]\d+)="(.+)"', line.strip())
    if not m:
        return None
    full_code = m.group(1)
    fields = m.group(2).split(",")
    if len(fields) < 32:
        return None
    code = full_code[2:]
    try:
        pre_close = float(fields[2])
        price = float(fields[3])
        if pre_close <= 0 or price <= 0:
            return None
        change_pct = round((price - pre_close) / pre_close * 100, 2)
        return {
            "code": code,
            "name": fields[0],
            "open": float(fields[1]),
            "pre_close": pre_close,
            "price": price,
            "high": float(fields[4]),
            "low": float(fields[5]),
            "volume": float(fields[8]),
            "amount": float(fields[9]),
            "change_pct": change_pct,
        }
    except (ValueError, IndexError):
        return None


def get_realtime_quotes() -> pd.DataFrame:
    codes = get_all_codes()
    if not codes:
        return pd.DataFrame()
    all_items = []
    batch_size = 800
    total_batches = (len(codes) + batch_size - 1) // batch_size
    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        batch = codes[start:start + batch_size]
        sina_codes = [_code_to_sina(c) for c in batch]
        try:
            url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    info = _parse_sina_hq_line(line)
                    if info:
                        all_items.append(info)
        except Exception as e:
            logger.warning(f"批次 {batch_idx+1}/{total_batches} 失败: {e}")
        if batch_idx < total_batches - 1:
            time.sleep(0.15)
    if not all_items:
        return pd.DataFrame()
    df = pd.DataFrame(all_items)
    df["volume_ratio"] = 0.0
    df["turnover_rate"] = 0.0
    df["circ_mv_yi"] = 0.0
    logger.info(f"[A股行情] 获取 {len(df)} 只股票实时行情")
    return df


def get_stock_history(code: str, days: int = 30) -> pd.DataFrame:
    cache_key = f"{code}_{days}"
    if cache_key in _history_cache:
        return _history_cache[cache_key].copy()
    try:
        sina_code = _code_to_sina(code)
        df = _retry(lambda: ak.stock_zh_a_daily(symbol=sina_code, adjust="qfq"))
        if df is None or df.empty:
            return pd.DataFrame()
        for c in ["open", "close", "high", "low", "volume", "amount"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "turnover" in df.columns:
            df["turnover_rate"] = pd.to_numeric(df["turnover"], errors="coerce") * 100
        result = df.tail(days).reset_index(drop=True)
        _history_cache[cache_key] = result
        return result.copy()
    except Exception as e:
        logger.debug(f"获取 {code} 历史失败: {e}")
        return pd.DataFrame()


def enrich_candidate(code: str, current_volume: float) -> dict:
    info = {"volume_ratio": 2.0, "turnover_rate": 5.0, "circ_mv_yi": 0.0}
    hist = get_stock_history(code, days=10)
    if hist.empty or len(hist) < 2:
        return info
    try:
        n = min(5, len(hist) - 1)
        avg_vol = hist["volume"].iloc[-(n+1):-1].mean()
        if avg_vol > 0 and current_volume > 0:
            info["volume_ratio"] = round(current_volume / avg_vol, 2)
        if "turnover_rate" in hist.columns:
            tr = hist["turnover_rate"].iloc[-1]
            if not pd.isna(tr) and tr > 0:
                info["turnover_rate"] = round(float(tr), 2)
        if info["turnover_rate"] > 0 and "amount" in hist.columns:
            amt = hist["amount"].iloc[-1]
            if not pd.isna(amt) and amt > 0:
                info["circ_mv_yi"] = round(amt / (info["turnover_rate"] / 100) / 1e8, 1)
    except Exception:
        pass
    return info


def get_limit_up_codes(quotes: pd.DataFrame) -> set:
    if quotes.empty:
        return set()
    zt = quotes[quotes["change_pct"] >= 9.5]
    return set(zt["code"].astype(str).tolist())


def get_current_price(code: str) -> Optional[float]:
    try:
        sina_code = _code_to_sina(code)
        url = f"https://hq.sinajs.cn/list={sina_code}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        info = _parse_sina_hq_line(r.text.strip())
        if info:
            return info["price"]
    except Exception as e:
        logger.error(f"获取 {code} 价格失败: {e}")
    return None


def get_batch_prices(codes: list[str]) -> dict[str, float]:
    """批量获取A股实时价格，返回 {code: price}"""
    if not codes:
        return {}
    result = {}
    batch_size = 800
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        sina_codes = [_code_to_sina(c) for c in batch]
        try:
            url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    info = _parse_sina_hq_line(line)
                    if info and info["price"] > 0:
                        result[info["code"]] = info["price"]
        except Exception as e:
            logger.warning(f"批量获取A股价格失败: {e}")
    return result


def get_limit_pct(code: str, name: str = "") -> float:
    if "ST" in name or "st" in name:
        return 0.05
    if code.startswith("3") or code.startswith("688"):
        return 0.20
    return 0.10


def calc_limit_price(pre_close: float, code: str = "", name: str = "") -> float:
    pct = get_limit_pct(code, name)
    return round(pre_close * (1 + pct), 2)


def is_at_limit(price: float, pre_close: float, code: str = "", name: str = "") -> bool:
    limit = calc_limit_price(pre_close, code, name)
    return price == limit


def get_trading_dates() -> list[str]:
    try:
        df = ak.tool_trade_date_hist_sina()
        return df["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return []


def get_index_history(symbol: str = "sz399006", days: int = 90) -> list[dict]:
    """获取A股指数历史收盘价

    常用symbol: sz399006(创业板指), sh000016(上证50), sh000300(沪深300)
    """
    cache_key = f"idx_{symbol}_{days}"
    if cache_key in _history_cache:
        return _history_cache[cache_key]
    try:
        df = _retry(lambda: ak.stock_zh_index_daily(symbol=symbol))
        if df is None or df.empty:
            return []
        df["date"] = pd.to_datetime(df["date"])
        df = df.tail(days).reset_index(drop=True)
        result = [
            {"date": row["date"].strftime("%Y-%m-%d"), "close": float(row["close"])}
            for _, row in df.iterrows()
        ]
        _history_cache[cache_key] = result
        logger.info(f"[A股指数] {symbol} 获取 {len(result)} 条数据")
        return result
    except Exception as e:
        logger.error(f"获取指数 {symbol} 历史失败: {e}")
        return []


def get_zt_pool(date_str: str = None) -> pd.DataFrame:
    """获取涨停池数据，含连板数/所属行业/换手率等"""
    if date_str is None:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
    try:
        df = _retry(lambda: ak.stock_zt_pool_em(date=date_str))
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "代码": "code", "名称": "name", "涨跌幅": "change_pct",
            "最新价": "price", "成交额": "amount", "流通市值": "circ_mv",
            "总市值": "total_mv", "换手率": "turnover", "封板资金": "seal_fund",
            "首次封板时间": "first_seal_time", "最后封板时间": "last_seal_time",
            "炸板次数": "bomb_count", "涨停统计": "zt_stat",
            "连板数": "consecutive_boards", "所属行业": "industry",
        })
        keep = ["code", "name", "change_pct", "price", "amount", "circ_mv",
                "turnover", "seal_fund", "first_seal_time", "last_seal_time",
                "bomb_count", "consecutive_boards", "industry"]
        for c in keep:
            if c not in df.columns:
                df[c] = 0
        df = df[keep].copy()
        df["code"] = df["code"].astype(str)
        for num_col in ["change_pct", "price", "amount", "turnover", "seal_fund",
                         "bomb_count", "consecutive_boards"]:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)
        logger.info(f"[涨停池] {date_str} 获取 {len(df)} 只涨停股")
        return df
    except Exception as e:
        logger.warning(f"获取涨停池失败: {e}")
        return pd.DataFrame()


def get_industry_board_ranking() -> pd.DataFrame:
    """获取行业板块排名"""
    try:
        df = _retry(ak.stock_board_industry_name_em)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "板块名称": "name", "涨跌幅": "change_pct",
            "上涨家数": "up_count", "下跌家数": "down_count",
            "领涨股票": "leading_stock", "领涨股票-涨跌幅": "leading_change",
        })
        keep = ["name", "change_pct", "up_count", "down_count",
                "leading_stock", "leading_change"]
        for c in keep:
            if c not in df.columns:
                df[c] = 0
        df = df[keep].copy()
        for num_col in ["change_pct", "up_count", "down_count", "leading_change"]:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)
        df = df.sort_values("change_pct", ascending=False).reset_index(drop=True)
        logger.info(f"[行业板块] 获取 {len(df)} 个行业排名")
        return df
    except Exception as e:
        logger.warning(f"获取行业板块排名失败: {e}")
        return pd.DataFrame()


def get_emotion_indicators(zt_pool: pd.DataFrame = None,
                           quotes: pd.DataFrame = None) -> dict:
    """计算情绪指标并判定情绪周期阶段"""
    if zt_pool is None:
        zt_pool = get_zt_pool()
    if quotes is None:
        quotes = get_realtime_quotes()

    zt_count = len(zt_pool) if not zt_pool.empty else 0

    dt_count = 0
    if not quotes.empty:
        dt_mask = quotes["change_pct"] <= -9.5
        dt_count = int(dt_mask.sum())

    max_boards = 0
    avg_boards = 0.0
    bomb_rate = 0.0
    total_seal_fund = 0.0
    if not zt_pool.empty:
        max_boards = int(zt_pool["consecutive_boards"].max())
        avg_boards = float(zt_pool["consecutive_boards"].mean())
        bombed = (zt_pool["bomb_count"] > 0).sum()
        bomb_rate = round(bombed / len(zt_pool) * 100, 1) if len(zt_pool) > 0 else 0
        total_seal_fund = float(zt_pool["seal_fund"].sum())

    # 涨停溢价率：需要前日涨停池对比今日涨幅（简化用当前涨停池的change_pct均值）
    zt_premium = 0.0
    if not zt_pool.empty and zt_pool["change_pct"].mean() > 0:
        zt_premium = round(float(zt_pool["change_pct"].mean()), 2)

    # 连板晋级率：连板>=2的比例
    upgrade_rate = 0.0
    if not zt_pool.empty and zt_pool["consecutive_boards"].max() > 1:
        multi = (zt_pool["consecutive_boards"] >= 2).sum()
        upgrade_rate = round(multi / len(zt_pool) * 100, 1)

    # 判定情绪阶段
    stage = _classify_emotion_stage(zt_count, dt_count, max_boards, bomb_rate, upgrade_rate)

    return {
        "zt_count": zt_count,
        "dt_count": dt_count,
        "max_boards": max_boards,
        "avg_boards": round(avg_boards, 1),
        "bomb_rate": bomb_rate,
        "total_seal_fund": round(total_seal_fund, 2),
        "zt_premium": zt_premium,
        "upgrade_rate": upgrade_rate,
        "stage": stage,
    }


def _classify_emotion_stage(zt_count: int, dt_count: int,
                             max_boards: int, bomb_rate: float,
                             upgrade_rate: float) -> str:
    """四阶段情绪周期判定"""
    # 退潮：炸板率>40% 或 跌停>涨停 或 连板骤降
    if bomb_rate > 40 or dt_count > zt_count or (zt_count > 0 and max_boards <= 1):
        return "退潮"
    # 高潮：涨停>80 且 连板>5 且 升级率高
    if zt_count > 80 and max_boards >= 5 and upgrade_rate > 25:
        return "高潮"
    # 发酵：涨停30-80, 连板梯队展开, 炸板率低
    if zt_count >= 30 and max_boards >= 3 and bomb_rate < 30:
        return "发酵"
    # 冰点/启动
    return "启动"
