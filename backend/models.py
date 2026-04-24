"""数据模型定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Market(str, Enum):
    A_SHARE = "A_SHARE"
    US_STOCK = "US_STOCK"


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Signal:
    signal_type: SignalType
    symbol: str
    market: Market
    name: str
    price: float
    shares: float
    confidence: float = 0.5
    metadata: dict = field(default_factory=dict)


@dataclass
class MarketContext:
    account_cash: float
    current_positions: list
    market: Market
    trading_date: str
    is_market_open: bool


@dataclass
class Position:
    id: int
    strategy_id: int
    symbol: str
    market: Market
    name: str
    shares: float
    avg_cost: float
    buy_date: str
    sellable_date: str
    current_price: Optional[float] = None

    @property
    def market_value(self) -> float:
        price = self.current_price or self.avg_cost
        return self.shares * price

    @property
    def unrealized_pnl(self) -> float:
        if not self.current_price:
            return 0.0
        return (self.current_price - self.avg_cost) * self.shares

    @property
    def unrealized_pnl_pct(self) -> float:
        if not self.current_price or self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost


@dataclass
class Trade:
    id: int
    strategy_id: int
    symbol: str
    market: Market
    name: str
    side: Side
    price: float
    shares: float
    notional: float
    commission: float = 0.0
    slippage: float = 0.0
    pnl: Optional[float] = None
    signal_data: Optional[str] = None
    executed_at: str = ""


@dataclass
class Account:
    id: int
    market: Market
    initial_capital: float
    cash: float

    @property
    def total_invested(self) -> float:
        return self.initial_capital - self.cash


@dataclass
class StrategyInfo:
    id: int
    name: str
    display_name: str
    market: Market
    description: str
    params_json: str
    is_active: bool
    max_position_pct: float


@dataclass
class EquitySnapshot:
    id: int
    market: Market
    total_value: float
    cash: float
    unrealized_pnl: float
    daily_return_pct: float
    snapshot_date: str
    snapshot_time: str


@dataclass
class StrategyPerformance:
    id: int
    strategy_id: int
    total_trades: int
    win_trades: int
    total_pnl: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    win_rate: float
    avg_hold_bars: Optional[float]
    peak_value: float
