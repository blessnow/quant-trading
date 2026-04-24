"""策略注册表 — 自动发现和管理策略"""
import importlib
import pkgutil
from typing import Optional

from loguru import logger

from strategies.base import BaseStrategy

_REGISTRY: dict[str, type[BaseStrategy]] = {}


def register(name: str, cls: type[BaseStrategy]):
    _REGISTRY[name] = cls


def get(name: str) -> Optional[type[BaseStrategy]]:
    return _REGISTRY.get(name)


def all_strategies() -> dict[str, type[BaseStrategy]]:
    return dict(_REGISTRY)


def create_instance(name: str, strategy_id: int, params: dict) -> Optional[BaseStrategy]:
    cls = get(name)
    if cls:
        return cls(strategy_id, params)
    return None


def auto_discover():
    """扫描 strategies/a_share/ 和 strategies/us_stock/ 自动注册策略"""
    import strategies.a_share as a_pkg
    import strategies.us_stock as us_pkg

    count = 0
    for pkg in [a_pkg, us_pkg]:
        for _, mod_name, _ in pkgutil.iter_modules(pkg.__path__):
            try:
                mod = importlib.import_module(f"{pkg.__name__}.{mod_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type)
                            and issubclass(attr, BaseStrategy)
                            and attr is not BaseStrategy):
                        register(attr.__name__, attr)
                        count += 1
                        logger.info(f"[策略注册] {attr.__name__}")
            except Exception as e:
                logger.error(f"[策略注册失败] {pkg.__name__}.{mod_name}: {e}")
    logger.info(f"[策略注册] 共注册 {count} 个策略")
    return count
