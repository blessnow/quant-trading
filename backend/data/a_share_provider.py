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
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
}
MAX_RETRIES = 3
RETRY_DELAY = 3

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
            time.sleep(0.2)
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
        time.sleep(0.5)
        df = _retry(lambda: ak.stock_zt_pool_em(date=date_str), delay=3)
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


_industry_cache: pd.DataFrame | None = None
_industry_cache_time: float = 0

def get_industry_board_ranking() -> pd.DataFrame:
    """获取行业板块排名（带缓存，5分钟有效）"""
    global _industry_cache, _industry_cache_time
    
    import time as time_module
    now = time_module.time()
    
    if _industry_cache is not None and (now - _industry_cache_time) < 300:
        logger.info(f"[行业板块] 使用缓存数据")
        return _industry_cache
    
    for attempt in range(3):
        try:
            time.sleep(1 + attempt)
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                continue
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
            _industry_cache = df
            _industry_cache_time = now
            return df
        except Exception as e:
            logger.warning(f"[行业板块] 尝试 {attempt+1}/3 失败: {e}")
            if attempt < 2:
                time.sleep(3)
    
    logger.warning("[行业板块] 东方财富接口失败，返回空数据")
    return pd.DataFrame()


def get_emotion_indicators(zt_pool: pd.DataFrame = None,
                           quotes: pd.DataFrame = None) -> dict:
    """计算情绪指标并判定情绪周期阶段"""
    if zt_pool is None:
        zt_pool = get_zt_pool()
    
    zt_count = len(zt_pool) if not zt_pool.empty else 0

    dt_count = 0
    if quotes is not None and not quotes.empty:
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


def _em_prefix(code: str) -> str:
    """A股代码转东方财富前缀 SH/SE"""
    code = str(code).strip()
    if code.startswith("6") or code.startswith("9"):
        return "SH"
    return "SZ"


def get_stock_fundamentals(code: str) -> dict:
    """获取个股基本面数据：公司信息、财务指标、前十大股东（东方财富接口）"""
    result = {"code": code}
    prefix = _em_prefix(code)
    em_code = f"{prefix}{code}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com",
    }

    # 1. 公司概况
    try:
        r = requests.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={em_code}",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            jbzl = data.get("jbzl", [])
            if jbzl:
                row = jbzl[0]
                result["股票简称"] = row.get("SECURITY_NAME_ABBR", "")
                result["公司全称"] = row.get("ORG_NAME", "")
                result["英文名称"] = row.get("ORG_NAME_EN", "")
                result["行业"] = row.get("INDUSTRYCSRC1", "")
            fxxg = data.get("fxxg", [])
            if fxxg:
                row = fxxg[0]
                result["上市日期"] = str(row.get("LISTING_DATE", ""))[:10]
                result["成立日期"] = str(row.get("FOUND_DATE", ""))[:10]
            bydt = data.get("bydt", [])
            if bydt:
                row = bydt[0]
                result["行业"] = row.get("EM_INDUSTRY", "")
                result["主营业务"] = row.get("RANGE", "")
                result["经营范围"] = row.get("BUSINESS_SCOPE", "")
                result["公司简介"] = row.get("ORG_PROFILE", "")
    except Exception as e:
        logger.debug(f"[东方财富] {code} 公司概况失败: {e}")

    # 2. 主要财务指标（最近5期）
    try:
        r = requests.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={em_code}",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                data = data.get("data", [])
            if isinstance(data, list) and data:
                financials = []
                for item in data[:5]:
                    report_date = str(item.get("REPORT_DATE", ""))[:10]
                    eps = item.get("EPSJB") or item.get("EPSXS")
                    bps = item.get("BPS") or item.get("MGJZC")
                    revenue = item.get("TOTAL_OPERATE_INCOME") or item.get("TOTALOPERATEREVE")
                    net_profit = item.get("PARENT_NETPROFIT") or item.get("PARENTNETPROFIT")
                    roe = item.get("WEIGHTAVG_ROE")
                    revenue_growth = item.get("TOTALOPERATEREVETZ")
                    profit_growth = item.get("PARENTNETPROFITTZ")
                    gross_margin = item.get("XSMLL")
                    debt_ratio = item.get("ZCFZL")
                    ocf_per_share = item.get("MGJYXJJE")

                    financials.append({
                        "report_date": report_date,
                        "report_name": item.get("REPORT_DATE_NAME", ""),
                        "eps": _safe_float(eps),
                        "bps": _safe_float(bps),
                        "revenue": _safe_float(revenue, div=1e8),
                        "net_profit": _safe_float(net_profit, div=1e8),
                        "roe": _safe_float(roe),
                        "revenue_growth_pct": _safe_float(revenue_growth),
                        "profit_growth_pct": _safe_float(profit_growth),
                        "gross_margin_pct": _safe_float(gross_margin),
                        "debt_ratio_pct": _safe_float(debt_ratio),
                        "ocf_per_share": _safe_float(ocf_per_share),
                    })
                result["financials"] = financials
    except Exception as e:
        logger.debug(f"[东方财富] {code} 财务指标失败: {e}")

    # 3. 前十大股东
    try:
        r = requests.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/PageAjax?code={em_code}",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            sdgd = data.get("sdgd", [])
            if sdgd:
                top_holders = []
                for item in sdgd[:10]:
                    top_holders.append({
                        "rank": item.get("HOLDER_RANK", ""),
                        "name": item.get("HOLDER_NAME", ""),
                        "type": item.get("HOLDER_TYPE", ""),
                        "shares": item.get("HOLD_NUM", ""),
                        "ratio": item.get("HOLD_NUM_RATIO", ""),
                    })
                result["top_holders"] = top_holders

            # 实际控制人
            sjkzr = data.get("sjkzr", [])
            if sjkzr:
                result["实际控制人"] = sjkzr[0].get("HOLDER_NAME", "")
    except Exception as e:
        logger.debug(f"[东方财富] {code} 股东信息失败: {e}")

    logger.info(f"[基本面] {code} 基本面数据获取完成")
    return result


def get_pb_ratio(code: str) -> dict:
    """获取个股市净率PB、市盈率PE等估值指标（东方财富接口）"""
    result = {"code": code}
    prefix = _em_prefix(code)
    em_code = f"{prefix}{code}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com",
    }

    # 公司概况拿名称和行业
    try:
        r = requests.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={em_code}",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            jbzl = r.json().get("jbzl", [])
            if jbzl:
                result["股票简称"] = jbzl[0].get("SECURITY_NAME_ABBR", "")
    except Exception:
        pass

    # 当前价格
    price = get_current_price(code)
    if price and price > 0:
        result["current_price"] = price

    # 财务指标拿BPS(每股净资产)和EPS
    try:
        r = requests.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={em_code}",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                data = data.get("data", [])
            if isinstance(data, list) and data:
                latest = data[0]
                bps = _safe_float(latest.get("BPS") or latest.get("MGJZC"))
                eps = _safe_float(latest.get("EPSJB") or latest.get("EPSXS"))

                if bps and bps > 0:
                    result["book_value_per_share"] = bps
                    if price and price > 0:
                        result["pb_ratio"] = round(price / bps, 2)
                if eps and eps > 0:
                    result["eps"] = eps
                    if price and price > 0:
                        result["pe_ratio"] = round(price / eps, 2)
                elif eps and eps < 0:
                    result["eps"] = eps
                    result["pe_ratio"] = None  # 亏损不计算PE

                result["report_date"] = str(latest.get("REPORT_DATE", ""))[:10]
    except Exception as e:
        logger.debug(f"[东方财富] {code} 估值数据失败: {e}")

    logger.info(f"[估值] {code} PB={result.get('pb_ratio', 'N/A')} PE={result.get('pe_ratio', 'N/A')}")
    return result


def _safe_float(val, div=1.0) -> Optional[float]:
    """安全转换数值"""
    if val is None or str(val).strip() in ("", "None", "nan", "NaN"):
        return None
    try:
        v = float(val)
        if div != 1.0:
            v = v / div
        return round(v, 4)
    except (ValueError, TypeError):
        return None

    logger.info(f"[估值] {code} PB={result.get('pb_ratio', 'N/A')} PE={result.get('pe_ratio', 'N/A')}")
    return result


def get_commodity_prices() -> dict:
    """获取大宗商品/资源价格（橡胶、钼、黄金、原油等）"""
    import warnings
    warnings.filterwarnings("ignore")
    result = {}

    # 黄金现货
    try:
        df = _retry(lambda: ak.spot_hist_sge(symbol="Au99.99"))
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            result["黄金Au99.99"] = {
                "price": float(latest.get("收盘价", 0)),
                "date": str(latest.name) if hasattr(latest, 'name') else "",
            }
    except Exception:
        pass

    # 银现货
    try:
        df = _retry(lambda: ak.spot_hist_sge(symbol="Ag(T+D)"))
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            result["白银Ag(T+D)"] = {
                "price": float(latest.get("收盘价", 0)),
                "date": str(latest.name) if hasattr(latest, 'name') else "",
            }
    except Exception:
        pass

    # 通过搜索获取期货主力合约
    try:
        futures_map = {
            "橡胶ru": "ru2509", "螺纹钢rb": "rb2510", "铁矿石i": "i2509",
            "沪铜cu": "cu2506", "沪铝al": "al2506",
        }
        for name, symbol in futures_map.items():
            try:
                df = _retry(lambda s=symbol: ak.futures_main_sina(symbol=s))
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    result[name] = {
                        "price": float(latest.get("收盘价", latest.get("close", 0))),
                        "date": str(latest.get("日期", latest.get("date", ""))),
                    }
            except Exception:
                continue
    except Exception:
        pass

    logger.info(f"[商品价格] 获取 {len(result)} 种商品/资源价格")
    return result


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
