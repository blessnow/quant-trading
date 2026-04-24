# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A quantitative paper-trading platform covering A-share and US stock markets. Three frontends (Next.js web dashboard, WeChat miniapp) connect to a Python FastAPI backend. Strategies auto-discover at startup and run on cron schedules via APScheduler. All data lives in SQLite.

## Build & Run Commands

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py                    # starts on 0.0.0.0:8000
```
API docs available at `http://localhost:8000/docs` (Swagger UI).

### Frontend
```bash
cd frontend
npm install
npm run dev                       # dev server on localhost:3000
npm run build && npm run start    # production
```
Frontend proxies `/api/*` to `localhost:8000` via Next.js rewrites in `next.config.mjs`.

### WeChat Miniapp
Open `miniapp/` in WeChat Developer Tools. API endpoint configured in `miniapp/app.js`.

### Docker
```bash
cd backend && docker build -t quant-trading . && docker run -p 8000:8000 quant-trading
```

## Architecture

### Signal Flow
Strategy.generate_signals() → RiskManager.pre_check/validate_signal → PaperBroker.execute → SQLite (trades/positions/accounts)

### Key Backend Modules
- **`main.py`** — FastAPI app, lifespan startup (init_db → auto_discover strategies → register to DB → start scheduler), WebSocket broadcast at `/ws/dashboard`
- **`scheduler.py`** — APScheduler cron jobs per strategy per market (CST for A-share, ET for US). Also handles equity snapshots, realtime price updates, T+1 sell, and stop-loss/take-profit monitoring
- **`paper_broker.py`** — Simulates real broker: enforces lot sizes (100 shares for A-share), slippage (±0.1%), commission, stamp tax, T+1 rules, USD/CNY conversion
- **`risk_manager.py`** — Three-tier: strategy-level (drawdown, consecutive losses, position count), signal-level (position size cap, cash reserve), post-trade (performance stats)
- **`strategies/registry.py`** — Auto-discovers subclasses of `BaseStrategy` in `strategies/a_share/` and `strategies/us_stock/` via `pkgutil.iter_modules`

### Adding a New Strategy
1. Create a `.py` file in `backend/strategies/a_share/` or `backend/strategies/us_stock/`
2. Subclass `BaseStrategy` — implement `generate_signals()`, `get_schedule_config()`, `get_market()`
3. Optionally override `default_params()` and `param_space()`
4. Register a cron job for it in `scheduler.py:setup_jobs()`
5. Strategy auto-registers by class name on startup

### Frontend Structure
- `app/page.tsx` — Main dashboard with portfolio summary, equity chart, positions
- `app/strategies/page.tsx` — Strategy list with toggle controls
- `app/trades/page.tsx` — Trade history table
- `app/backtest/page.tsx` — Backtesting UI
- `lib/api-client.ts` — Typed API client; all endpoints under `/api/`

### Database
SQLite via `aiosqlite`. Schema defined inline in `database.py:SCHEMA_SQL`. Key tables: `strategies`, `accounts` (per-strategy + market-level aggregates), `positions`, `trades`, `equity_snapshots`, `strategy_equity_snapshots`, `benchmark_snapshots`, `risk_events`, `users`, `orders`, `articles`. WAL mode enabled. Migration logic handles legacy `accounts` table without `strategy_id`.

## Data Providers
- **A-share**: `data/a_share_provider.py` — uses `akshare` for quotes, index history
- **US stock**: `data/us_stock_provider.py` — uses `yfinance` for quotes, index history, USD/CNY rate
- **Market status**: `data/market_status.py` — timezone-aware (CST/ET), trading day checks

## Environment Variables
Set in env or `config.py` defaults:
- `DATA_DIR` — SQLite data directory (defaults to `project_root/data`)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram notifications
- `WX_APPID`, `WX_SECRET` — WeChat miniapp login
- `WX_MCH_ID`, `WX_MCH_KEY` — WeChat payments
- `JWT_SECRET` — auth token signing

## Tech Stack
- Backend: Python 3.12, FastAPI, uvicorn, aiosqlite, APScheduler, akshare, yfinance, loguru
- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS 4, Recharts
- Miniapp: WeChat Mini Program framework
- Database: SQLite with WAL mode
