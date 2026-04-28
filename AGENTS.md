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
```

No test, lint, or typecheck commands exist in this repo.

## Architecture

**Signal flow**: `Strategy.generate_signals()` → `RiskManager.pre_check/validate_signal` → `PaperBroker.execute` → SQLite

**Backend startup sequence** (in `main.py:lifespan`):
1. `init_db()` — creates tables, runs inline migrations
2. `auto_discover()` — scans strategy directories
3. `_register_strategies_to_db()` — syncs to DB, creates strategy accounts
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

**Database**: SQLite with WAL mode at `data/quant.db`. Schema in `database.py:SCHEMA_SQL`. Migrations are inline in `init_db()` — check for `ALTER TABLE` blocks when adding columns.

**Accounts**: Each strategy has its own account (strategy_id set). Do NOT create market-level accounts (strategy_id=NULL).

**Frontend API proxy**: `next.config.mjs` rewrites `/api/*` to `BACKEND_URL`. Chat SSE bypasses proxy and calls backend directly.

## Key Files

- `backend/main.py` — FastAPI app, lifespan startup, WebSocket at `/ws/dashboard`
- `backend/scheduler.py` — APScheduler cron jobs, timezone handling (CST for A-share, ET for US)
- `backend/paper_broker.py` — Simulates broker: lot sizes, slippage, commission, T+1 rules
- `backend/risk_manager.py` — Three-tier risk checks
- `backend/config.py` — All configurable values with env var overrides
- `backend/api/chat.py` — SSE streaming for LLM chat
- `backend/llm/chat_agent.py` — LLM agent with tool calling

## Railway Deployment

Project ID: `55c5c716-d74a-457d-a980-85595938c2ce`
Environment ID: `5e5725da-3bed-4c1e-8ce4-d7e71f466216`

| Service | ID | Deploy from |
|---------|----|-------------|
| Frontend | `af882ee6-a488-42c2-8a84-5e9b679b0d91` | `frontend/` |
| Backend | `3556c239-8ed9-41ce-a7fe-00073ac206a0` | `backend/` |

```bash
# Link and deploy frontend
railway link --project=55c5c716-d74a-457d-a980-85595938c2ce --environment=5e5725da-3bed-4c1e-8ce4-d7e71f466216 --service=af882ee6-a488-42c2-8a84-5e9b679b0d91
railway up

# Link and deploy backend
railway link --project=55c5c716-d74a-457d-a980-85595938c2ce --environment=5e5725da-3bed-4c1e-8ce4-d7e71f466216 --service=3556c239-8ed9-41ce-a7fe-00073ac206a0
railway up
```

## Environment Variables

Set in `backend/.env`:
- `DATA_DIR` — SQLite data directory (defaults to `project_root/data`)
- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` — LLM config (uses 讯飞 Anthropic-compatible API)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Notifications
- `WX_APPID`, `WX_SECRET` — WeChat miniapp auth
- `JWT_SECRET` — Auth token signing

## Data Providers

- A-share: `backend/data/a_share_provider.py` uses `akshare`
- US stock: `backend/data/us_stock_provider.py` uses `yfinance`
- Market status: `backend/data/market_status.py` — timezone-aware trading day checks

## LLM Integration

- Provider: 讯飞 (Xunfei) using Anthropic-compatible API at `https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic`
- Chat API: `backend/api/chat.py` — SSE streaming with heartbeat
- Agent: `backend/llm/chat_agent.py` — tool calling, batch tool merging
- Timeout: 1200s for long-running LLM requests

## Auth & Permissions

- Admin account: phone `13800138000`, password `admin123`
- Monitor page (`/monitor`) requires `is_admin=true` cookie
- Password hashing: `hashlib.sha256((password + JWT_SECRET).encode()).hexdigest()`

## Frontend SSE Gotchas

- Chat SSE uses `isStreamingRef` to prevent `useEffect` from overwriting messages when `currentSession` changes
- SSE bypasses Next.js proxy, directly calls `http://localhost:8000/api/chat/send`
