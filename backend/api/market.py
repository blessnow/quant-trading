"""市场状态 API"""
from fastapi import APIRouter

from data.market_status import get_market_status
from data.a_share_provider import get_current_price as get_a_price
from data.us_stock_provider import get_current_price as get_us_price

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/status")
async def market_status():
    return get_market_status()


@router.get("/quote/{symbol}")
async def get_quote(symbol: str, market: str = "A_SHARE"):
    if market == "A_SHARE":
        price = get_a_price(symbol)
        return {"symbol": symbol, "market": "A_SHARE", "price": price}
    else:
        price = get_us_price(symbol)
        return {"symbol": symbol, "market": "US_STOCK", "price": price}
