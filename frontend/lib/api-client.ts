const API_BASE = "/api";

async function fetchAPI<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
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

export const api = {
  portfolio: {
    summary: () => fetchAPI<PortfolioSummary>("/portfolio/summary"),
    positions: (market?: string) =>
      fetchAPI<{ positions: Position[]; total: number }>(
        `/portfolio/positions${market ? `?market=${market}` : ""}`
      ),
    equityCurve: (days = 90) =>
      fetchAPI<{ curve: EquityPoint[]; count: number }>(
        `/portfolio/equity-curve?days=${days}`
      ),
  },
  strategies: {
    list: () => fetchAPI<{ strategies: Strategy[] }>("/strategies"),
    toggle: (id: number, active: boolean) =>
      fetchAPI(`/strategies/${id}/toggle`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: active }),
      }),
    ranking: (period = "month") =>
      fetchAPI<{ rankings: Strategy[]; period: string }>(
        `/strategies/ranking?period=${period}`
      ),
  },
  trades: {
    list: (limit = 100, offset = 0) =>
      fetchAPI<{ trades: Trade[]; total: number }>(
        `/trades?limit=${limit}&offset=${offset}`
      ),
  },
  market: {
    status: () => fetchAPI<MarketStatus>("/market/status"),
  },
};
