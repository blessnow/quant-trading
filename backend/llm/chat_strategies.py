"""聊天策略配置 — 预设策略和提示词模板"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PromptTemplate:
    """提示词模板"""
    title: str
    content: str
    icon: str = "💬"


@dataclass
class ChatStrategy:
    """聊天策略配置"""
    id: str
    name: str
    avatar: str
    color: str
    description: str
    system_prompt_key: str
    tools: list[str]
    prompts: list[PromptTemplate]


# ─── 陈小群短线策略 ───────────────────────────────────────

CHEN_XIAOQUN_PROMPTS = [
    PromptTemplate(
        title="今天市场怎么看",
        content="今天A股市场情绪如何？有哪些主线板块？适合操作吗？",
        icon="📊"
    ),
    PromptTemplate(
        title="分析股票",
        content="请分析 {stock_code} 这只股票，从短线角度看看是否值得关注",
        icon="🔍"
    ),
    PromptTemplate(
        title="帮我选股",
        content="根据当前市场情绪，帮我找几个值得关注的短线标的",
        icon="🎯"
    ),
    PromptTemplate(
        title="检查持仓",
        content="帮我看看当前持仓，哪些该止盈，哪些该止损？",
        icon="📋"
    ),
    PromptTemplate(
        title="找龙头",
        content="今天市场龙头是谁？连板情况如何？",
        icon="🐉"
    ),
]

CHEN_XIAOQUN_STRATEGY = ChatStrategy(
    id="chen_xiaoqun",
    name="陈小群短线",
    avatar="🎯",
    color="#ef4444",
    description="短线龙头战法，关注情绪周期、连板高度、板块轮动",
    system_prompt_key="chen_xiaoqun",
    tools=["search_web", "get_market_data", "get_stock_info", "get_positions"],
    prompts=CHEN_XIAOQUN_PROMPTS,
)


# ─── 鱼哥价值策略 ───────────────────────────────────────

YU_GE_PROMPTS = [
    PromptTemplate(
        title="发现涨价品种",
        content="最近有哪些商品在涨价？对应的股票有哪些机会？",
        icon="📈"
    ),
    PromptTemplate(
        title="分析股票",
        content="请用六步研究法分析 {stock_code}，从股东、公司、财务、行业、产品价格、估值角度分析",
        icon="🔍"
    ),
    PromptTemplate(
        title="价值选股",
        content="帮我找几个低估值的资源股或周期股",
        icon="💎"
    ),
    PromptTemplate(
        title="商品价格",
        content="当前大宗商品价格走势如何？黄金、橡胶、铜等品种怎么样？",
        icon="🛢️"
    ),
    PromptTemplate(
        title="检查持仓",
        content="帮我看看当前持仓的基本面有没有变化？",
        icon="📋"
    ),
]

YU_GE_STRATEGY = ChatStrategy(
    id="yu_ge",
    name="鱼哥价值",
    avatar="💎",
    color="#3b82f6",
    description="价值投资六步研究，专注资源周期股、低估值高安全边际",
    system_prompt_key="yu_ge",
    tools=["search_web", "get_stock_fundamentals", "get_pb_ratio", "get_commodity_prices", "get_positions"],
    prompts=YU_GE_PROMPTS,
)


# ─── 通用投顾策略 ───────────────────────────────────────

GENERAL_PROMPTS = [
    PromptTemplate(
        title="市场概览",
        content="请给我一个A股和美股市场的整体概览",
        icon="🌍"
    ),
    PromptTemplate(
        title="分析股票",
        content="请全面分析 {stock_code} 这只股票的投资价值",
        icon="🔍"
    ),
    PromptTemplate(
        title="解读新闻",
        content="请帮我解读这条新闻对市场的影响：{news_content}",
        icon="📰"
    ),
    PromptTemplate(
        title="板块分析",
        content="请分析 {sector} 板块的投资机会和风险",
        icon="🏭"
    ),
    PromptTemplate(
        title="对比股票",
        content="请对比分析 {stock1} 和 {stock2} 的投资价值",
        icon="⚖️"
    ),
]

GENERAL_STRATEGY = ChatStrategy(
    id="general",
    name="通用投顾",
    avatar="🤖",
    color="#10b981",
    description="全能投资顾问，覆盖A股美股、行业分析、个股研究",
    system_prompt_key="general",
    tools=["search_web", "get_market_data", "get_stock_info", "get_positions", "get_stock_fundamentals", "get_pb_ratio", "get_commodity_prices"],
    prompts=GENERAL_PROMPTS,
)


# ─── 策略注册表 ───────────────────────────────────────

STRATEGIES: dict[str, ChatStrategy] = {
    "chen_xiaoqun": CHEN_XIAOQUN_STRATEGY,
    "yu_ge": YU_GE_STRATEGY,
    "general": GENERAL_STRATEGY,
}


def get_strategy(strategy_id: str) -> Optional[ChatStrategy]:
    """获取策略配置"""
    return STRATEGIES.get(strategy_id)


def get_all_strategies() -> list[ChatStrategy]:
    """获取所有策略列表"""
    return list(STRATEGIES.values())


def get_strategy_prompts(strategy_id: str) -> list[PromptTemplate]:
    """获取策略的提示词模板"""
    strategy = get_strategy(strategy_id)
    if strategy:
        return strategy.prompts
    return []
