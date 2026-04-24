"""全局配置"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(os.environ.get("DATA_DIR", PROJECT_DIR), "data")

# 数据库
DB_PATH = os.path.join(DATA_DIR, "quant.db")

# 初始资金（单位：RMB）
INITIAL_CAPITAL_A_SHARE = 500_000.0
INITIAL_CAPITAL_US_STOCK = 500_000.0
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

# 通知配置
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

# 服务配置
API_HOST = "0.0.0.0"
API_PORT = 8000
FRONTEND_URL = "http://localhost:3000"

# 微信小程序配置（测试号）
WX_APPID = os.environ.get("WX_APPID", "wx_test_appid")
WX_SECRET = os.environ.get("WX_SECRET", "wx_test_secret")

# 微信支付配置（测试）
WX_MCH_ID = os.environ.get("WX_MCH_ID", "")           # 商户号
WX_MCH_KEY = os.environ.get("WX_MCH_KEY", "")          # 商户API密钥
WX_PAY_NOTIFY_URL = os.environ.get("WX_PAY_NOTIFY_URL", "https://your-domain.com/api/pay/notify")

# JWT配置
JWT_SECRET = os.environ.get("JWT_SECRET", "quant-trading-jwt-secret-key-2026")
JWT_EXPIRE_HOURS = 72

# 会员价格（单位：元）
MEMBER_PRICE_MONTHLY = 49
MEMBER_PRICE_YEARLY = 399
