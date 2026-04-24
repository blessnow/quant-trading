"""告警通知服务"""
import json
from typing import Optional

import httpx
from loguru import logger

import config


async def send_telegram(message: str):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.debug("[通知] Telegram未配置，跳过")
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            })
        logger.info(f"[通知] Telegram发送成功")
    except Exception as e:
        logger.error(f"[通知] Telegram发送失败: {e}")


async def notify(event_type: str, message: str):
    """统一通知入口"""
    full_msg = f"📊 <b>[{event_type}]</b>\n{message}"
    logger.info(f"[通知] {event_type}: {message}")
    await send_telegram(full_msg)


async def notify_trade(trade_info: dict):
    """交易通知"""
    side = "买入" if trade_info["side"] == "BUY" else "卖出"
    market = "A股" if trade_info["market"] == "A_SHARE" else "美股"
    msg = (
        f"{'🟢' if trade_info['side'] == 'BUY' else '🔴'} <b>交易执行</b>\n"
        f"市场: {market}\n"
        f"操作: {side} {trade_info['name']}({trade_info['symbol']})\n"
        f"价格: {trade_info['price']}\n"
        f"数量: {trade_info['shares']}\n"
        f"金额: {trade_info['notional']:.2f}"
    )
    if trade_info.get("pnl") is not None:
        emoji = "📈" if trade_info["pnl"] > 0 else "📉"
        msg += f"\n盈亏: {emoji} {trade_info['pnl']:.2f}"
    await notify("交易", msg)


async def notify_risk(event_type: str, message: str):
    """风控通知"""
    await notify("⚠️ 风控", f"{event_type}: {message}")


async def notify_daily_report(summary: dict):
    """每日报告"""
    msg = (
        f"📋 <b>每日交易报告</b>\n"
        f"日期: {summary['date']}\n"
        f"总资产: ¥{summary['total_value']:,.0f}\n"
        f"日盈亏: ¥{summary['daily_pnl']:,.0f} ({summary['daily_return']:.2f}%)\n"
        f"A股: ¥{summary['a_share_value']:,.0f}\n"
        f"美股: ¥{summary['us_stock_value']:,.0f}\n"
        f"持仓数: {summary['positions_count']}\n"
        f"今日交易: {summary['trades_today']}笔"
    )
    await notify("日报", msg)
