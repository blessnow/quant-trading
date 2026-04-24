"""策略抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from models import Signal, MarketContext, Market


class BaseStrategy(ABC):
    """所有策略的抽象基类。子类只需实现3个方法即可接入系统。"""

    def __init__(self, strategy_id: int, params: dict):
        self.strategy_id = strategy_id
        self.params = params

    @abstractmethod
    def generate_signals(self, context: MarketContext) -> list[Signal]:
        """核心逻辑：根据市场上下文生成交易信号列表"""
        ...

    @abstractmethod
    def get_schedule_config(self) -> dict:
        """调度配置：返回 {cron, timezone, market}"""
        ...

    @abstractmethod
    def get_market(self) -> str:
        """返回 'A_SHARE' 或 'US_STOCK'"""
        ...

    def on_execution_report(self, trades: list):
        """可选回调：策略可根据执行结果自适应"""
        pass

    @classmethod
    def default_params(cls) -> dict:
        return {}

    @classmethod
    def param_space(cls) -> dict:
        """参数空间定义，用于自动优化。格式: {param_name: [min, max, step]}"""
        return {}
