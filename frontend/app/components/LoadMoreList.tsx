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
  market_value: number;
  buy_date: string;
  sellable_date: string;
}

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function pnlColor(n: number) {
  return n > 0 ? "text-[#e05555]" : n < 0 ? "text-[#22c55e]" : "text-gray-500";
}

function sign(n: number) {
  return n > 0 ? "+" : "";
}

interface LoadMoreListProps<T> {
  initialData: T[];
  initialTotal: number;
  fetchMore: (offset: number) => Promise<{ data: T[]; total: number; has_more: boolean }>;
  renderItem: (item: T) => React.ReactNode;
  title: string;
  emptyText: string;
  pageSize: number;
}

function LoadMoreList<T extends { id: number }>({
  initialData,
  initialTotal,
  fetchMore,
  renderItem,
  title,
  emptyText,
  pageSize,
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
        <div key={t.id} className="border-b border-gray-50 py-2.5 flex items-center text-sm">
          <span className="text-xs text-gray-400 w-20 shrink-0">{t.executed_at?.slice(0, 16) || "-"}</span>
          <span className="font-mono text-xs font-semibold text-[#1a1a2e] w-32 shrink-0">
            {t.symbol} <span className="text-gray-400 font-normal">{t.name}</span>
          </span>
          <span className={`text-xs px-2 py-0.5 rounded font-semibold w-16 shrink-0 ${t.side === "BUY" ? "bg-red-50 text-[#e05555]" : "bg-green-50 text-[#22c55e]"}`}>
            {t.side === "BUY" ? "买入" : "卖出"}
          </span>
          <span className="text-right w-16 shrink-0">{t.price.toFixed(2)}</span>
          <span className="text-right w-16 shrink-0">{t.shares}</span>
          <span className="text-right text-gray-500 w-20 shrink-0">¥{fmt(t.notional || t.price * t.shares)}</span>
          <span className={`text-right font-semibold flex-1 ${t.pnl != null ? pnlColor(t.pnl) : ""}`}>
            {t.pnl != null ? `${sign(t.pnl)}¥${fmt(t.pnl)}` : "-"}
          </span>
        </div>
      )}
    />
  );
}

export function PositionsList({ strategyId, initialPositions }: { strategyId: number; initialPositions: Position[] }) {
  const fetchMore = async (offset: number) => {
    const res = await fetch(`/api/strategies/${strategyId}/positions?limit=20&offset=${offset}`);
    const json = await res.json();
    return { data: json.positions || [], total: json.total || 0, has_more: json.has_more || false };
  };

  return (
    <LoadMoreList
      initialData={initialPositions}
      initialTotal={initialPositions.length}
      fetchMore={fetchMore}
      pageSize={20}
      title="当前持仓"
      emptyText="暂无持仓"
      renderItem={(p) => (
        <div key={p.id} className="border-b border-gray-50 py-2.5 flex items-center text-sm">
          <span className="font-mono text-xs font-semibold text-[#1a1a2e] w-20 shrink-0">{p.symbol}</span>
          <span className="text-gray-700 w-24 shrink-0">{p.name}</span>
          <span className="text-right w-16 shrink-0">{p.shares}</span>
          <span className="text-right text-gray-500 w-16 shrink-0">{p.avg_cost.toFixed(2)}</span>
          <span className="text-right w-16 shrink-0">{p.current_price.toFixed(2)}</span>
          <span className="text-right w-20 shrink-0">¥{fmt(p.market_value || p.shares * p.current_price)}</span>
          <span className={`text-right font-semibold flex-1 ${pnlColor(p.unrealized_pnl)}`}>
            {sign(p.unrealized_pnl)}¥{fmt(p.unrealized_pnl)}
          </span>
        </div>
      )}
    />
  );
}