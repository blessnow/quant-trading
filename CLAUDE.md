# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A quantitative paper-trading platform covering A-share and US stock markets. Three frontends (Next.js web dashboard, WeChat miniapp) connect to a Python FastAPI backend. Strategies auto-discover at startup and run on cron schedules via APScheduler. All data lives in SQLite.

## Build & Run Commands

No test, lint, or typecheck commands exist in this repo.

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py                    # starts on 0.0.0.0:8000
```
API docs at `http://localhost:8000/docs` (Swagger UI).

### Frontend
```bash
cd frontend
npm install
npm run dev                       # dev server on localhost:3000
npm run build && npm run start    # production
```
Frontend proxies `/api/*` to `BACKEND_URL` (default `localhost:8000`) via Next.js rewrites in `next.config.mjs`.

### WeChat Miniapp
Open `miniapp/` in WeChat Developer Tools. API endpoint configured in `miniapp/app.js:globalData.apiBase`.

### Docker
```bash
cd backend && docker build -t quant-trading . && docker run -p 8000:8000 quant-trading
```
Railway deployment configured in `railway.toml` (Root Directory set to `backend`).

## Architecture

### Signal Flow
`Strategy.generate_signals()` → `RiskManager.pre_check/validate_signal` → `PaperBroker.execute` → SQLite (trades/positions/accounts)

### Backend Startup Sequence (`main.py:lifespan`)
1. `init_db()` — creates tables if missing
2. `auto_discover()` — scans strategy directories
3. `_register_strategies_to_db()` — syncs to DB
4. `start_scheduler()` — begins cron jobs

### Key Backend Modules
- **`main.py`** — FastAPI app, lifespan startup, WebSocket broadcast at `/ws/dashboard`
- **`scheduler.py`** — APScheduler cron jobs per strategy per market (CST for A-share, ET for US). Also handles equity snapshots, realtime price updates, T+1 sell, and stop-loss/take-profit monitoring
- **`paper_broker.py`** — Simulates real broker: enforces lot sizes (100 shares for A-share), slippage (±0.1%), commission, stamp tax, T+1 rules, USD/CNY conversion
- **`risk_manager.py`** — Three-tier: strategy-level (drawdown, consecutive losses, position count), signal-level (position size cap, cash reserve), post-trade (performance stats)
- **`database.py`** — SQLite via aiosqlite, WAL mode. Schema inline in `SCHEMA_SQL`. No migration system — handles legacy `accounts` table without `strategy_id` inline
- **`config.py`** — All configurable values with env var overrides (trading rules, risk params, service config, WeChat/SMS integration)
- **`models.py`** — Data models: `Signal`, `MarketContext`, `Market` enum
- **`strategies/base.py`** — `BaseStrategy` ABC with 3 required methods: `generate_signals()`, `get_schedule_config()`, `get_market()`
- **`strategies/registry.py`** — Auto-discovers `BaseStrategy` subclasses via `pkgutil.iter_modules`. Class name is the unique identifier

### API Routes (`api/`)
| File | Purpose |
|------|---------|
| `portfolio.py` | Portfolio management |
| `strategies.py` | Strategy control (toggle, params) |
| `trades.py` | Trade history |
| `market.py` | Market data |
| `backtest.py` | Backtesting interface |
| `chat.py` | AI chat (uses `anthropic` SDK) |
| `articles.py` | Article content |
| `notifications.py` | Notification system |
| `web_auth.py` / `phone_auth.py` | Web/phone authentication |
| `wechat_auth.py` / `wechat_pay.py` | WeChat login and payments |
| `health.py` | Health check |

### Adding a New Strategy
1. Create a `.py` file in `backend/strategies/a_share/` or `backend/strategies/us_stock/`
2. Subclass `BaseStrategy` — implement `generate_signals()`, `get_schedule_config()`, `get_market()`
3. Optionally override `default_params()` and `param_space()`
4. Add cron job in `scheduler.py:setup_jobs()` if custom schedule needed
5. Strategy auto-registers by class name on next startup

### Existing Strategies
- **A-share**: `chen_xiaoqun_short`, `event_arbitrage`, `limit_up_predictor`, `multi_factor_daily`, `yu_ge_value`
- **US stock**: `gap_scanner`, `mean_reversion`, `momentum_breakout`

### Frontend Structure
- `app/page.tsx` — Main dashboard (portfolio summary, equity chart, positions)
- `app/strategies/page.tsx` — Strategy list with toggle controls
- `app/trades/page.tsx` — Trade history table
- `app/backtest/page.tsx` — Backtesting UI
- `app/auth/` — Authentication pages
- `app/chat/` — AI chat interface
- `app/membership/` — Membership features
- `app/monitor/` — Monitoring dashboard
- `app/settings/` — User settings
- `lib/api-client.ts` — Typed API client; all endpoints under `/api/`
- `lib/auth-api.ts` / `lib/auth-context.tsx` — Auth API and context provider

### Miniapp Pages
`miniapp/pages/`: `index`, `strategies`, `strategy-detail`, `trades`, `membership`, `my`, `article-detail`

### Database
SQLite via `aiosqlite`. Key tables: `strategies`, `accounts` (per-strategy + market-level aggregates), `positions`, `trades`, `equity_snapshots`, `strategy_equity_snapshots`, `benchmark_snapshots`, `risk_events`, `users`, `orders`, `articles`. WAL mode enabled.

### Data Providers
- **A-share**: `data/a_share_provider.py` — uses `akshare` for quotes, index history
- **US stock**: `data/us_stock_provider.py` — uses `yfinance` for quotes, index history, USD/CNY rate
- **Market status**: `data/market_status.py` — timezone-aware (CST/ET), trading day checks

## Environment Variables
Set in env or `config.py` defaults:
- `DATA_DIR` — SQLite data directory (defaults to `project_root/data`)
- `BACKEND_URL` — Frontend proxy target (defaults to `localhost:8000`)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram notifications
- `WX_APPID`, `WX_SECRET` — WeChat miniapp login
- `WX_MCH_ID`, `WX_MCH_KEY` — WeChat payments
- `WX_WEB_APPID`, `WX_WEB_SECRET` — WeChat web scan login
- `SMS_PROVIDER`, `SMS_ACCESS_KEY`, `SMS_SECRET_KEY` — SMS verification
- `JWT_SECRET` — auth token signing

## Tech Stack
- Backend: Python 3.12, FastAPI, uvicorn, aiosqlite, APScheduler, akshare, yfinance, loguru, anthropic
- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS 4, Recharts
- Miniapp: WeChat Mini Program framework
- Database: SQLite with WAL mode
