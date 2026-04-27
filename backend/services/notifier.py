"""通知发送服务"""
import aiohttp
from typing import Optional
from loguru import logger


class Notifier:
    """通知发送器"""
    
    @staticmethod
    async def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
        """发送Telegram消息"""
        if not bot_token or not chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.info(f"[Telegram] 消息发送成功: {chat_id}")
                        return True
                    else:
                        logger.error(f"[Telegram] 发送失败: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"[Telegram] 发送异常: {e}")
            return False
    
    @staticmethod
    async def send_wechat(webhook_url: str, message: str) -> bool:
        """发送微信企业消息"""
        if not webhook_url:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json={
                    "msgtype": "text",
                    "text": {"content": message}
                }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.info("[WeChat] 消息发送成功")
                        return True
                    else:
                        logger.error(f"[WeChat] 发送失败: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"[WeChat] 发送异常: {e}")
            return False
    
    @staticmethod
    async def send_email(
        smtp_server: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        to_email: str,
        subject: str,
        body: str
    ) -> bool:
        """发送邮件"""
        if not smtp_server or not to_email:
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            logger.info(f"[Email] 邮件发送成功: {to_email}")
            return True
        except Exception as e:
            logger.error(f"[Email] 发送异常: {e}")
            return False
    
    @staticmethod
    async def send_to_user(user_id: int, message: str, channels: list[str] = None):
        """向用户发送通知（根据用户配置）"""
        from database import get_db
        import json
        
        db = await get_db()
        try:
            # 获取用户通知配置
            async with db.execute(
                "SELECT channel, config_json FROM notification_config WHERE user_id=? AND is_enabled=1",
                (user_id,)
            ) as cur:
                rows = await cur.fetchall()
            
            for row in rows:
                channel = row[0]
                if channels and channel not in channels:
                    continue
                
                config = json.loads(row[1]) if row[1] else {}
                
                if channel == "telegram":
                    await Notifier.send_telegram(
                        config.get("bot_token", ""),
                        config.get("chat_id", ""),
                        message
                    )
                elif channel == "wechat":
                    await Notifier.send_wechat(
                        config.get("webhook_url", ""),
                        message
                    )
                elif channel == "email":
                    await Notifier.send_email(
                        config.get("smtp_server", ""),
                        config.get("smtp_port", 587),
                        config.get("smtp_user", ""),
                        config.get("smtp_password", ""),
                        config.get("to_email", ""),
                        "📊 量化交易通知",
                        message
                    )
        finally:
            await db.close()
