import { api } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const revalidate = 30;

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function pnl(n: number) {
  return n > 0 ? "text-red-500" : n < 0 ? "text-green-600" : "text-gray-500";
}

function sign(n: number) {
  return n > 0 ? "+" : "";
}

const STRATEGY_META: Record<string, { emoji: string; desc: string; schedule: string }> = {
  LimitUpPredictor: { emoji: "🚀", desc: "14:40扫描接近涨停股，多因子评分选最佳，次日9:35卖出", schedule: "14:40 CST" },
  MultiFactorDaily: { emoji: "📊", desc: "资金流入+聪明钱+量价背离多因子评分，每日盘前选股", schedule: "09:00 CST" },
  EventArbitrage: { emoji: "📰", desc: "监控新闻事件，LLM分析影响，生成交易信号", schedule: "每30分钟" },
  MomentumBreakout: { emoji: "⚡", desc: "20日新高+放量突破，追踪止损，5日最大持有", schedule: "09:45 ET" },
  MeanReversion: { emoji: "🔄", desc: "RSI超卖+Bollinger下轨反弹，均值回归交易", schedule: "12:00 ET" },
  GapScanner: { emoji: "📉", desc: "隔夜跳空>3%的回补交易，日内了结", schedule: "09:35 ET" },
};

export default async function StrategiesPage() {
  const [strategies, ranking, trades, positions] = await Promise.all([
    api.strategies.list().catch(() => ({ strategies: [] })),
    api.strategies.ranking().catch(() => ({ rankings: [], period: "month" })),
    api.trades.list(50).catch(() => ({ trades: [], total: 0 })),
    api.portfolio.positions().catch(() => ({ positions: [], total: 0 })),
  ]);

  return (
    <div className="space-y-6">
      {/* 排行榜 */}
      {ranking.rankings.length > 0 && (
        <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">策略排行榜</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {ranking.rankings.map((r, i) => (
              <div key={r.strategy_id} className="flex items-center gap-3 border border-black/5 rounded-xl p-3">
                <div className={`text-2xl font-bold ${i === 0 ? "text-amber-500" : i === 1 ? "text-gray-400" : i === 2 ? "text-amber-700" : "text-gray-300"}`}>
                  #{i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{r.display_name}</div>
                  <div className="text-xs text-gray-500">
                    得分 {r.score.toFixed(1)} · 胜率 {(r.win_rate * 100).toFixed(0)}% · {r.total_trades}笔
                  </div>
                </div>
                <div className={`text-sm font-medium ${pnl(r.total_pnl)}`}>
                  {sign(r.total_pnl)}{fmt(r.total_pnl)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 每个策略独立卡片 */}
      <h2 className="text-lg font-semibold">策略详情</h2>
      <div className="space-y-4">
        {strategies.strategies.map((s) => {
          const meta = STRATEGY_META[s.name] || { emoji: "📈", desc: s.description, schedule: "-" };
          const strategyTrades = trades.trades.filter((t) => t.strategy_name === s.display_name);
          const strategyPositions = positions.positions.filter((p) => p.strategy_name === s.display_name);
          const wins = strategyTrades.filter((t) => t.side === "SELL" && (t.pnl ?? 0) > 0).length;
          const totalSells = strategyTrades.filter((t) => t.side === "SELL").length;
          const totalPnl = strategyTrades.filter((t) => t.side === "SELL").reduce((sum, t) => sum + (t.pnl ?? 0), 0);

          return (
            <div key={s.id} className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${s.is_active ? "border-black/10" : "border-dashed border-gray-200 opacity-70"}`}>
              {/* 策略头部 */}
              <div className="p-5 border-b border-black/5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{meta.emoji}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg">{s.display_name}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${s.market === "A_SHARE" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
                          {s.market === "A_SHARE" ? "A股" : "美股"}
                        </span>
                        <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded ${s.is_active ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-400"}`}>
                          <span className={`inline-block w-1.5 h-1.5 rounded-full ${s.is_active ? "bg-green-500" : "bg-gray-400"}`} />
                          {s.is_active ? "运行中" : "已暂停"}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">{meta.desc}</div>
                      <div className="text-xs text-gray-400 mt-0.5">调度: {meta.schedule}</div>
                    </div>
                  </div>
                  <form action={async () => {
                    "use server";
                    await api.strategies.toggle(s.id, !s.is_active);
                  }}>
                    <button type="submit" className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${s.is_active ? "bg-red-50 text-red-600 hover:bg-red-100" : "bg-green-50 text-green-600 hover:bg-green-100"}`}>
                      {s.is_active ? "暂停" : "启用"}
                    </button>
                  </form>
                </div>
              </div>

              {/* 绩效指标 */}
              <div className="grid grid-cols-2 md:grid-cols-5 border-b border-black/5">
                <MetricCell label="总交易" value={`${strategyTrades.length}笔`} />
                <MetricCell label="胜率" value={totalSells > 0 ? `${((wins / totalSells) * 100).toFixed(1)}%` : "-"} />
                <MetricCell label="总盈亏" value={`${sign(totalPnl)}${fmt(totalPnl)}`} className={pnl(totalPnl)} />
                <MetricCell label="Sharpe" value={s.performance?.sharpe_ratio?.toFixed(2) ?? "-"} />
                <MetricCell label="持仓中" value={`${strategyPositions.length}只`} />
              </div>

              {/* 当前持仓 */}
              {strategyPositions.length > 0 && (
                <div className="p-4 border-b border-black/5">
                  <div className="text-xs text-gray-500 font-medium mb-2">当前持仓</div>
                  <div className="space-y-1.5">
                    {strategyPositions.map((p) => (
                      <div key={p.id} className="flex items-center justify-between text-sm">
                        <span className="font-mono text-xs">{p.symbol}</span>
                        <span className="text-gray-600">{p.name}</span>
                        <span className="text-gray-500">{p.shares}股</span>
                        <span>{(p.current_price || p.avg_cost).toFixed(2)}</span>
                        <span className={`font-medium ${pnl(p.unrealized_pnl)}`}>{sign(p.unrealized_pnl)}{fmt(p.unrealized_pnl)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 最近交易 */}
              {strategyTrades.length > 0 && (
                <div className="p-4">
                  <div className="text-xs text-gray-500 font-medium mb-2">最近交易</div>
                  <div className="space-y-1.5">
                    {strategyTrades.slice(0, 5).map((t) => (
                      <div key={t.id} className="flex items-center justify-between text-sm">
                        <span className="text-xs text-gray-400">{t.executed_at?.slice(5, 19)}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${t.side === "BUY" ? "bg-red-50 text-red-600" : "bg-green-50 text-green-600"}`}>
                          {t.side === "BUY" ? "买入" : "卖出"}
                        </span>
                        <span className="font-mono text-xs">{t.symbol}</span>
                        <span className="text-gray-500">{t.shares}股 @ {t.price.toFixed(2)}</span>
                        <span className={`font-medium ${t.pnl != null ? pnl(t.pnl) : ""}`}>
                          {t.pnl != null ? `${sign(t.pnl)}${fmt(t.pnl)}` : "-"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!strategyTrades.length && !strategyPositions.length && (
                <div className="p-8 text-center text-sm text-gray-400">策略等待首次运行</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MetricCell({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="p-3 border-r border-black/5 last:border-r-0">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${className || ""}`}>{value}</div>
    </div>
  );
}
