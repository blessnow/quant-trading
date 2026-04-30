"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface Trade {
  id: number;
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

interface Position {
  id: number;
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
  stop_loss_pct: number;
  take_profit_pct: number;
}

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function fmtPct(n: number) {
  const pct = (n * 100).toFixed(2);
  return n > 0 ? `+${pct}%` : `${pct}%`;
}

function pnlColor(n: number) {
  return n > 0 ? "text-[#e05555]" : n < 0 ? "text-[#22c55e]" : "text-gray-500";
}

function sign(n: number) {
  return n > 0 ? "+" : "";
}

function holdDays(buyDate: string): number {
  const buy = new Date(buyDate);
  const now = new Date();
  return Math.floor((now.getTime() - buy.getTime()) / (1000 * 60 * 60 * 24));
}

interface LoadMoreListProps<T> {
  initialData: T[];
  initialTotal: number;
  fetchMore: (offset: number) => Promise<{ data: T[]; total: number; has_more: boolean }>;
  renderItem: (item: T) => React.ReactNode;
  title: string;
  emptyText: string;
  pageSize: number;
  header?: React.ReactNode;
}

function LoadMoreList<T extends { id: number }>({
  initialData,
  initialTotal,
  fetchMore,
  renderItem,
  title,
  emptyText,
  pageSize,
  header,
}: LoadMoreListProps<T>) {
  const [data, setData] = useState<T[]>(initialData);
  const [total, setTotal] = useState(initialTotal);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(initialData.length < initialTotal);
  const observerRef = useRef<HTMLDivElement>(null);

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return;
    setLoading(true);
    try {
      const result = await fetchMore(data.length);
      setData((prev) => [...prev, ...result.data]);
      setTotal(result.total);
      setHasMore(result.has_more);
    } catch (e) {
      console.error("Load more failed:", e);
    } finally {
      setLoading(false);
    }
  }, [data.length, loading, hasMore, fetchMore]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          loadMore();
        }
      },
      { threshold: 0.1 }
    );

    if (observerRef.current) {
      observer.observe(observerRef.current);
    }

    return () => observer.disconnect();
  }, [hasMore, loading, loadMore]);

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">{title}</h2>
        <div className="text-center text-gray-400 py-8">{emptyText}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
      <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">
        {title} <span className="text-sm font-normal text-gray-400">{total}条</span>
      </h2>
      <div className="overflow-x-auto">
        {header}
        {data.map((item) => renderItem(item))}
      </div>
      {/* 底部加载触发器 */}
      <div ref={observerRef} className="h-10 flex items-center justify-center">
        {loading && <span className="text-gray-400 text-sm">加载中...</span>}
        {!hasMore && data.length > 0 && (
          <span className="text-gray-300 text-sm">已加载全部 {total} 条</span>
        )}
      </div>
    </div>
  );
}

export function TradesList({ strategyId, initialTrades }: { strategyId: number; initialTrades: Trade[] }) {
  const fetchMore = async (offset: number) => {
    const res = await fetch(`/api/strategies/${strategyId}/trades?limit=20&offset=${offset}`);
    const json = await res.json();
    return { data: json.trades || [], total: json.total || 0, has_more: json.has_more || false };
  };

  return (
    <LoadMoreList
      initialData={initialTrades}
      initialTotal={initialTrades.length}
      fetchMore={fetchMore}
      pageSize={20}
      title="历史交易"
      emptyText="暂无交易记录"
      renderItem={(t) => (
        <div key={t.id} className="border-b border-gray-50 py-2.5 grid grid-cols-7 gap-2 text-sm">
          <span className="text-xs text-gray-400">{t.executed_at?.slice(0, 16) || "-"}</span>
          <span className="font-mono text-xs font-semibold text-[#1a1a2e] truncate">
            {t.symbol} <span className="text-gray-400 font-normal">{t.name}</span>
          </span>
          <span className={`text-xs px-2 py-0.5 rounded font-semibold text-center ${t.side === "BUY" ? "bg-red-50 text-[#e05555]" : "bg-green-50 text-[#22c55e]"}`}>
            {t.side === "BUY" ? "买入" : "卖出"}
          </span>
          <span className="text-right text-xs">{t.price.toFixed(2)}</span>
          <span className="text-right text-xs">{t.shares}</span>
          <span className="text-right text-xs text-gray-500">¥{fmt(t.notional || t.price * t.shares)}</span>
          <span className={`text-right text-xs font-semibold ${t.pnl != null ? pnlColor(t.pnl) : ""}`}>
            {t.pnl != null ? `${sign(t.pnl)}¥${fmt(t.pnl)}` : "-"}
          </span>
        </div>
      )}
      header={
        <div className="border-b border-gray-100 py-2 grid grid-cols-7 gap-2 text-xs text-gray-400 font-medium">
          <span>时间</span>
          <span>代码</span>
          <span className="text-center">方向</span>
          <span className="text-right">价格</span>
          <span className="text-right">数量</span>
          <span className="text-right">金额</span>
          <span className="text-right">盈亏</span>
        </div>
      }
    />
  );
}

export function PositionsList({ strategyId, initialPositions }: { strategyId: number; initialPositions: Position[] }) {
  const [positions, setPositions] = useState<Position[]>(initialPositions);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editStopLoss, setEditStopLoss] = useState<string>("");
  const [editTakeProfit, setEditTakeProfit] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const refreshPositions = useCallback(async () => {
    const res = await fetch(`/api/strategies/${strategyId}/positions`);
    const json = await res.json();
    if (json.positions) {
      setPositions(json.positions);
    }
  }, [strategyId]);

  const startEdit = (p: Position) => {
    setEditingId(p.id);
    setEditStopLoss(String(p.stop_loss_pct));
    setEditTakeProfit(String(p.take_profit_pct));
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditStopLoss("");
    setEditTakeProfit("");
  };

  const saveEdit = async (positionId: number) => {
    const stopLoss = parseFloat(editStopLoss);
    const takeProfit = parseFloat(editTakeProfit);
    if (isNaN(stopLoss) || isNaN(takeProfit)) {
      alert("请输入有效的数字");
      return;
    }
    if (stopLoss > 0 || stopLoss < -50) {
      alert("止损百分比应为负数且在-50%以内");
      return;
    }
    if (takeProfit < 0 || takeProfit > 100) {
      alert("止盈百分比应为正数且在100%以内");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`/api/strategies/${strategyId}/positions/${positionId}/risk-params`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stop_loss_pct: stopLoss, take_profit_pct: takeProfit }),
      });
      const json = await res.json();
      if (json.success) {
        setPositions(prev => prev.map(p => p.id === positionId ? { ...p, stop_loss_pct: stopLoss, take_profit_pct: takeProfit } : p));
        setEditingId(null);
      } else {
        alert(json.detail || "保存失败");
      }
    } catch (e) {
      alert("保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (positions.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">当前持仓</h2>
        <div className="text-center text-gray-400 py-8">暂无持仓</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
      <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">
        当前持仓 <span className="text-sm font-normal text-gray-400">{positions.length}条</span>
      </h2>
      <div className="space-y-3">
        {positions.map((p) => {
          const pnlPct = p.unrealized_pnl_pct * 100;
          const nearStopLoss = pnlPct > p.stop_loss_pct && pnlPct <= p.stop_loss_pct + 2;
          const nearTakeProfit = pnlPct < p.take_profit_pct && pnlPct >= p.take_profit_pct - 2;
          const isEditing = editingId === p.id;

          return (
            <div key={p.id} className="border border-gray-100 rounded-xl p-4 hover:border-gray-200 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-[#1a1a2e]">{p.symbol}</span>
                  <span className="text-gray-500 text-sm">{p.name}</span>
                  {nearStopLoss && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-amber-50 text-amber-600">接近止损</span>
                  )}
                  {nearTakeProfit && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-amber-50 text-amber-600">接近止盈</span>
                  )}
                </div>
                <div className="text-right">
                  <div className={`text-lg font-bold ${pnlColor(p.unrealized_pnl)}`}>
                    {sign(p.unrealized_pnl)}¥{fmt(p.unrealized_pnl)}
                  </div>
                  <div className={`text-sm ${pnlColor(p.unrealized_pnl_pct)}`}>
                    {fmtPct(p.unrealized_pnl_pct)}
                  </div>
                </div>
              </div>

              {/* Risk bar */}
              <RiskBar
                stopLossPct={p.stop_loss_pct}
                takeProfitPct={p.take_profit_pct}
                currentPct={pnlPct}
              />

              <div className="flex items-center justify-between mt-3 text-sm">
                <div className="flex items-center gap-4 text-gray-500">
                  <span>持仓 {p.shares}股</span>
                  <span>成本 ¥{p.avg_cost.toFixed(2)}</span>
                  <span>现价 ¥{p.current_price.toFixed(2)}</span>
                  <span>市值 ¥{fmt(p.market_value)}</span>
                  <span>持有 {holdDays(p.buy_date)}天</span>
                </div>
                <div className="flex items-center gap-2">
                  {isEditing ? (
                    <>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-400">止损</span>
                        <input
                          type="number"
                          value={editStopLoss}
                          onChange={(e) => setEditStopLoss(e.target.value)}
                          className="w-16 px-1.5 py-1 text-xs border border-gray-200 rounded"
                          step="0.5"
                        />
                        <span className="text-xs text-gray-400">%</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-400">止盈</span>
                        <input
                          type="number"
                          value={editTakeProfit}
                          onChange={(e) => setEditTakeProfit(e.target.value)}
                          className="w-16 px-1.5 py-1 text-xs border border-gray-200 rounded"
                          step="0.5"
                        />
                        <span className="text-xs text-gray-400">%</span>
                      </div>
                      <button
                        onClick={() => saveEdit(p.id)}
                        disabled={saving}
                        className="px-2 py-1 text-xs bg-[#1a1a2e] text-white rounded hover:bg-[#2d2b55] disabled:opacity-50"
                      >
                        {saving ? "保存中..." : "确认"}
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="px-2 py-1 text-xs border border-gray-200 rounded hover:bg-gray-50"
                      >
                        取消
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => startEdit(p)}
                      className="text-xs text-gray-400 hover:text-gray-600 underline"
                    >
                      止损 {p.stop_loss_pct}% / 止盈 +{p.take_profit_pct}%
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RiskBar({ stopLossPct, takeProfitPct, currentPct }: { stopLossPct: number; takeProfitPct: number; currentPct: number }) {
  // Normalize to 0-100 scale for bar position
  // stopLossPct is negative (e.g., -8), takeProfitPct is positive (e.g., 15)
  const range = takeProfitPct - stopLossPct; // e.g., 15 - (-8) = 23
  const stopLossPos = 0; // left edge
  const takeProfitPos = 100; // right edge
  const currentPos = Math.max(0, Math.min(100, ((currentPct - stopLossPct) / range) * 100));

  // Determine color for current position
  let currentColor = "#22c55e"; // green (profit)
  if (currentPct < 0) {
    currentColor = "#e05555"; // red (loss)
  }
  if (currentPct <= stopLossPct + 2 && currentPct > stopLossPct) {
    currentColor = "#f59e0b"; // amber (near stop loss)
  }
  if (currentPct >= takeProfitPct - 2 && currentPct < takeProfitPct) {
    currentColor = "#f59e0b"; // amber (near take profit)
  }

  return (
    <div className="relative h-6 bg-gray-100 rounded-full overflow-hidden">
      {/* Stop loss zone */}
      <div
        className="absolute top-0 left-0 h-full bg-red-100"
        style={{ width: `${Math.max(0, Math.min(100, ((0 - stopLossPct) / range) * 100))}%` }}
      />
      {/* Take profit zone */}
      <div
        className="absolute top-0 right-0 h-full bg-green-100"
        style={{ width: `${Math.max(0, 100 - ((takeProfitPct - 0) / range) * 100)}%` }}
      />
      {/* Stop loss line */}
      <div
        className="absolute top-0 h-full w-0.5 bg-red-400"
        style={{ left: `${stopLossPos}%` }}
      />
      {/* Take profit line */}
      <div
        className="absolute top-0 h-full w-0.5 bg-green-500"
        style={{ left: `${takeProfitPos}%` }}
      />
      {/* Zero line */}
      <div
        className="absolute top-0 h-full w-0.5 bg-gray-300"
        style={{ left: `${((0 - stopLossPct) / range) * 100}%` }}
      />
      {/* Current position marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-white shadow-sm"
        style={{ left: `calc(${currentPos}% - 6px)`, backgroundColor: currentColor }}
      />
      {/* Labels */}
      <div className="absolute top-0 left-0 h-full flex items-center pl-1">
        <span className="text-[10px] text-red-500 font-medium">{stopLossPct}%</span>
      </div>
      <div className="absolute top-0 right-0 h-full flex items-center pr-1">
        <span className="text-[10px] text-green-600 font-medium">+{takeProfitPct}%</span>
      </div>
    </div>
  );
}