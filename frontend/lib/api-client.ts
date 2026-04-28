const API_BASE = typeof window === "undefined"
  ? `${process.env.BACKEND_URL || "http://localhost:8000"}/api`
  : "/api";

function fetchAPI<T>(path: string, init?: RequestInit, authToken?: string): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> || {}),
  };

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const res = fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  }).then(r => {
    if (!r.ok) throw new Error(`API Error: ${r.status}`);
    return r.json();
  });
  return res;
}

export interface PortfolioSummary {
  total_value: number;
  initial_capital: number;
  total_pnl: number;
  markets: {
    [key: string]: {
      cash: number;
      market_value: number;
      total: number;
      initial_capital: number;
      total_pnl: number;
      daily_return_pct: number;
    };
  };
}

export interface Position {
  id: number;
  strategy_name: string;
  symbol: string;
  market: string;
  name: string;
  shares: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  market_value: number;
  buy_date: string;
  sellable_date: string;
}

export interface Strategy {
  id: number;
  name: string;
  display_name: string;
  market: string;
  description: string;
  params: Record<string, unknown>;
  is_active: boolean;
  max_position_pct: number;
  performance?: {
    total_trades: number;
    win_trades: number;
    total_pnl: number;
    win_rate: number;
    sharpe_ratio: number | null;
  };
}

export interface Trade {
  id: number;
  strategy_name: string;
  symbol: string;
  market: string;
  name: string;
  side: string;
  price: number;
  shares: number;
  notional: number;
  commission: number;
  pnl: number | null;
  executed_at: string;
}

export interface EquityPoint {
  market: string;
  total_value: number;
  daily_return_pct: number;
  date: string;
  time: string;
}

export interface MarketStatus {
  a_share: { is_open: boolean; current_time: string; next_open: string };
  us_stock: { is_open: boolean; current_time: string; next_open: string };
}

export interface StrategyLog {
  id: number;
  strategy_id: number;
  strategy_name: string;
  level: string;
  message: string;
  detail: string;
  created_at: string;
}

export function createApiClient(authToken?: string) {
  const fetchWithAuth = <T>(path: string, init?: RequestInit): Promise<T> => {
    const headers: Record<string, string> = {
      ...(init?.headers as Record<string, string> || {}),
    };
    if (authToken) {
      headers["Authorization"] = `Bearer ${authToken}`;
    }
    return fetch(`${API_BASE}${path}`, { ...init, headers }).then(r => {
      if (!r.ok) throw new Error(`API Error: ${r.status}`);
      return r.json();
    });
  };

  return {
    portfolio: {
      summary: () => fetchWithAuth<PortfolioSummary>("/portfolio/summary"),
      positions: (market?: string) =>
        fetchWithAuth<{ positions: Position[]; total: number }>(
          `/portfolio/positions${market ? `?market=${market}` : ""}`
        ),
      equityCurve: (days = 90) =>
        fetchWithAuth<{ curve: EquityPoint[]; count: number }>(
          `/portfolio/equity-curve?days=${days}`
        ),
    },
    strategies: {
      list: () => fetchWithAuth<{ strategies: Strategy[] }>("/strategies"),
      toggle: (id: number, active: boolean) =>
        fetchWithAuth(`/strategies/${id}/toggle`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: active }),
        }),
      ranking: (period = "month") =>
        fetchWithAuth<{ rankings: Strategy[]; period: string }>(
          `/strategies/ranking?period=${period}`
        ),
      logs: (strategyId?: number, limit = 100) =>
        fetchWithAuth<{ logs: StrategyLog[]; count: number }>(
          `/strategies/logs?limit=${limit}${strategyId ? `&strategy_id=${strategyId}` : ""}`
        ),
    },
    trades: {
      list: (limit = 100, offset = 0) =>
        fetchWithAuth<{ trades: Trade[]; total: number }>(
          `/trades?limit=${limit}&offset=${offset}`
        ),
    },
    market: {
      status: () => fetchWithAuth<MarketStatus>("/market/status"),
    },
  };
}

export const api = createApiClient();
