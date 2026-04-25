# AGENTS.md

Compact guidance for OpenCode sessions working in this repo.

## Commands

**Backend** (from `backend/`):
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py              # starts on 0.0.0.0:8000
```

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev                 # localhost:3000
npm run build && npm run start
```

No test, lint, or typecheck commands exist in this repo.

## Architecture

**Signal flow**: `Strategy.generate_signals()` → `RiskManager.pre_check/validate_signal` → `PaperBroker.execute` → SQLite

**Backend startup sequence** (in `main.py:lifespan`):
1. `init_db()` — creates tables if missing
2. `auto_discover()` — scans strategy directories
3. `_register_strategies_to_db()` — syncs to DB
4. `start_scheduler()` — begins cron jobs

**Strategy auto-discovery** (`strategies/registry.py`):
- Scans `strategies/a_share/` and `strategies/us_stock/` via `pkgutil.iter_modules`
- Registers any class that subclasses `BaseStrategy`
- Strategy class name becomes the unique identifier

**Adding a strategy**:
1. Create `.py` in `backend/strategies/a_share/` or `backend/strategies/us_stock/`
2. Subclass `BaseStrategy`, implement `generate_signals()`, `get_schedule_config()`, `get_market()`
3. Add cron job in `scheduler.py:setup_jobs()` if needed
4. Strategy auto-registers on next startup

**Database**: SQLite with WAL mode. Schema defined inline in `database.py:SCHEMA_SQL`. No migration system.

**Frontend API proxy**: `next.config.mjs` rewrites `/api/*` to `BACKEND_URL` (default `localhost:8000`).

**Miniapp**: API endpoint in `miniapp/app.js:globalData.apiBase`.

## Key Files

- `backend/main.py` — FastAPI app, lifespan startup, WebSocket at `/ws/dashboard`
- `backend/scheduler.py` — APScheduler cron jobs, timezone handling (CST for A-share, ET for US)
- `backend/paper_broker.py` — Simulates broker: lot sizes, slippage, commission, T+1 rules
- `backend/risk_manager.py` — Three-tier risk checks
- `backend/config.py` — All configurable values with env var overrides

## Environment Variables

Set in `backend/.env` or environment:
- `DATA_DIR` — SQLite data directory (defaults to `project_root/data`)
- `BACKEND_URL` — Frontend proxy target (defaults to `localhost:8000`)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Notifications
- `WX_APPID`, `WX_SECRET` — WeChat miniapp auth
- `JWT_SECRET` — Auth token signing

## Data Providers

- A-share: `backend/data/a_share_provider.py` uses `akshare`
- US stock: `backend/data/us_stock_provider.py` uses `yfinance`
- Market status: `backend/data/market_status.py` — timezone-aware trading day checks
