"""全局配置"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# 数据存储目录（数据库、日志等）- 与代码分离，可被volume挂载
_storage_env = os.environ.get("STORAGE_DIR", "")
STORAGE_DIR = _storage_env if _storage_env else os.path.join(PROJECT_DIR, "storage")
DATA_DIR = STORAGE_DIR  # 兼容旧代码

# 数据库
DB_PATH = os.path.join(STORAGE_DIR, "quant.db")

# 初始资金（单位：RMB）
INITIAL_CAPITAL_A_SHARE = 500_000.0
INITIAL_CAPITAL_US_STOCK = 500_000.0
INITIAL_CAPITAL_PER_STRATEGY = 500_000.0  # 每个策略独立资金
USD_CNY_RATE = 7.25  # 默认汇率，运行时更新

# A股交易规则
A_SHARE_COMMISSION_RATE = 0.00025  # 佣金费率
A_SHARE_COMMISSION_MIN = 5.0       # 最低佣金
A_SHARE_STAMP_TAX_RATE = 0.0005    # 印花税（卖出）
A_SHARE_LOT_SIZE = 100             # 最小交易单位
A_SHARE_PRICE_LIMIT_MAIN = 0.10    # 主板涨跌停 10%
A_SHARE_PRICE_LIMIT_GEM = 0.20     # 创业板/科创板 20%

# 美股交易规则
US_STOCK_COMMISSION_PER_SHARE = 0.01  # 每股佣金
US_STOCK_MIN_COMMISION = 1.0         # 最低佣金

# 风控参数
RISK_MAX_CONSECUTIVE_LOSSES = 3      # 连续亏损暂停阈值
RISK_STRATEGY_DRAWDOWN_LIMIT = 0.10  # 单策略最大回撤
RISK_PORTFOLIO_DRAWDOWN_LIMIT = 0.15 # 组合最大回撤
RISK_MAX_POSITION_PCT = 0.25         # 单仓位最大占比
RISK_MAX_POSITIONS = 20              # 最大持仓数
RISK_MIN_CASH_RESERVE = 0.10         # 最低现金储备比例
RISK_DEFAULT_STOP_LOSS_PCT = -8.0    # 默认止损百分比（负数）
RISK_DEFAULT_TAKE_PROFIT_PCT = 15.0  # 默认止盈百分比（正数）

# 通知配置
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

# 服务配置
# Railway 私网常见 IPv6；未在 Railway 时默认 0.0.0.0 便于本机
_on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PRIVATE_DOMAIN"))
_default_api_host = "::" if _on_railway else "0.0.0.0"
API_HOST = os.environ.get("API_HOST", _default_api_host)
API_PORT = int(os.environ.get("PORT", os.environ.get("API_PORT", "8000")))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# 为 true 时：非内网 Host 仅允许 BACKEND_PUBLIC_ALLOWED_PATHS（微信/扫码回调等）
BACKEND_PRIVATE_ONLY = os.environ.get("BACKEND_PRIVATE_ONLY", "").lower() in ("1", "true", "yes")
_extra_public = [
    p.strip().rstrip("/") or "/"
    for p in os.environ.get("BACKEND_PUBLIC_PATHS", "").split(",")
    if p.strip()
]
BACKEND_PUBLIC_ALLOWED_PATHS = tuple(
    sorted({"/api/pay/notify", "/api/auth/callback", *_extra_public})
)

# 微信小程序配置（测试号）
WX_APPID = os.environ.get("WX_APPID", "wx_test_appid")
WX_SECRET = os.environ.get("WX_SECRET", "wx_test_secret")

# 微信支付配置（APIv3；WX_MCH_ID 为空为 mock）
WX_MCH_ID = os.environ.get("WX_MCH_ID", "")
WX_MCH_KEY = os.environ.get("WX_MCH_KEY", "")  # 遗留 V2，仅兼容旧文档
WX_PAY_NOTIFY_URL = os.environ.get("WX_PAY_NOTIFY_URL", "https://your-domain.com/api/pay/notify")
WX_MCH_SERIAL_NO = os.environ.get("WX_MCH_SERIAL_NO", "")
WX_API_V3_KEY = os.environ.get("WX_API_V3_KEY", "")
WX_MCH_PRIVATE_KEY_PATH = os.environ.get("WX_MCH_PRIVATE_KEY_PATH", "")

# JWT配置
JWT_SECRET = os.environ.get("JWT_SECRET", "quant-trading-jwt-secret-key-2026")
JWT_EXPIRE_HOURS = 72

# 会员价格（单位：元）
MEMBER_PRICE_MONTHLY = 49
MEMBER_PRICE_YEARLY = 399

# 微信开放平台Web扫码登录（暂未申请）
WX_WEB_APPID = os.environ.get("WX_WEB_APPID", "")
WX_WEB_SECRET = os.environ.get("WX_WEB_SECRET", "")
WX_WEB_REDIRECT_URI = os.environ.get("WX_WEB_REDIRECT_URI", "")

# 短信验证码配置
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "mock")  # mock/aliyun/tencent
SMS_ACCESS_KEY = os.environ.get("SMS_ACCESS_KEY", "")
SMS_SECRET_KEY = os.environ.get("SMS_SECRET_KEY", "")
SMS_SIGN_NAME = os.environ.get("SMS_SIGN_NAME", "QuantTrader")
SMS_TEMPLATE_CODE = os.environ.get("SMS_TEMPLATE_CODE", "")

# 固定测试号：免真实短信，验证码为 SMS_FIXED_TEST_CODE（默认 123456）即通过。
# SMS_FIXED_TEST_PHONES 未设置时，使用脚本/main 里创建的测试号；设为 none/off/- 可关闭。
_sms_fixed = os.environ.get("SMS_FIXED_TEST_CODE", "123456").strip()
SMS_FIXED_TEST_CODE: str | None = _sms_fixed if _sms_fixed else None
_sms_fp = os.environ.get("SMS_FIXED_TEST_PHONES")
if _sms_fp is None:
    SMS_FIXED_TEST_PHONES = frozenset(
        {
            "13800000001",
            "13800000002",
            "13800138000",  # 文档中的管理员示例号
            "10000000001",
            "10000000002",
            "10000000003",
        }
    )
elif _sms_fp.strip().lower() in ("", "none", "off", "-"):
    SMS_FIXED_TEST_PHONES = frozenset()
else:
    SMS_FIXED_TEST_PHONES = frozenset(
        p.strip() for p in _sms_fp.split(",") if len(p.strip()) == 11
    )

# 二维码有效期（秒）
LOGIN_QR_EXPIRE_SECONDS = 300
PAY_QR_EXPIRE_SECONDS = 300
