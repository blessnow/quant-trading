import { api } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const revalidate = 60;

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pnlColor(n: number) {
  return n > 0 ? "text-[#e05555]" : n < 0 ? "text-[#22c55e]" : "text-gray-500";
}
function sign(n: number) {
  return n > 0 ? "+" : "";
}

const STRATEGY_META: Record<string, { desc: string; schedule: string }> = {
  LimitUpPredictor: { desc: "14:40扫描接近涨停股，多因子评分选最佳", schedule: "每10分钟 9:00-14:00 CST" },
  MultiFactorDaily: { desc: "资金流入+聪明钱+量价背离，每日盘前选股", schedule: "09:00 CST" },
  EventArbitrage: { desc: "监控新闻事件，LLM分析生成交易信号", schedule: "每30分钟 9:00-14:00 CST" },
  MomentumBreakout: { desc: "20日新高+放量突破，5日最大持有", schedule: "每10分钟 9:00-15:00 ET" },
  MeanReversion: { desc: "RSI超卖+Bollinger下轨反弹", schedule: "每15分钟 10:00-15:00 ET" },
  GapScanner: { desc: "隔夜跳空>3%的回补交易", schedule: "09:35 ET" },
};

export default async function StrategiesPage() {
  const [strategies, ranking, trades, positions, logs] = await Promise.all([
    api.strategies.list().catch(() => ({ strategies: [] as any[] })),
    api.strategies.ranking().catch(() => ({ rankings: [] as any[], period: "month" })),
    api.trades.list(50).catch(() => ({ trades: [] as any[], total: 0 })),
    api.portfolio.positions().catch(() => ({ positions: [] as any[], total: 0 })),
    api.strategies.logs(undefined, 50).catch(() => ({ logs: [] as any[], count: 0 })),
  ]);

  return (
    <div className="space-y-5">
      <AutoRefresh />
      {/* 深色 Hero */}
      <div className="bg-gradient-to-br from-[#1a1a2e] to-[#2d2b55] rounded-2xl p-6 text-white -mx-4 -mt-2 md:mx-0 md:mt-0">
        <h1 className="text-xl font-bold mb-1">策略中心</h1>
        <p className="text-white/40 text-sm">{strategies.strategies.length} 个策略运行中 · 排行榜</p>
      </div>

      {/* 排行榜 — 奖牌风格 */}
      {ranking.rankings.length > 0 && (
        <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
          <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">策略排行榜</h2>
          <div className="space-y-3">
            {ranking.rankings.map((r: any, i: number) => (
              <div key={r.strategy_id} className="flex items-center gap-3 rounded-xl bg-gray-50 p-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white ${i === 0 ? "bg-gradient-to-br from-amber-400 to-amber-500" : i === 1 ? "bg-gradient-to-br from-gray-300 to-gray-400" : i === 2 ? "bg-gradient-to-br from-amber-600 to-amber-700" : "bg-gray-200 text-gray-500"}`}>
                  {i + 1}
                </div>
                <span className={`text-xs font-bold text-white px-2 py-1 rounded-md ${(r.market || "A_SHARE") === "A_SHARE" ? "bg-gradient-to-br from-[#e05555] to-[#f07070]" : "bg-gradient-to-br from-[#4f6ef7] to-[#7b93f9]"}`}>
                  {(r.market || "A_SHARE") === "A_SHARE" ? "A" : "U"}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm text-[#1a1a2e] truncate">{r.display_name}</div>
                  <div className="text-xs text-gray-400">得分 {r.score.toFixed(1)} · 胜率 {(r.win_rate * 100).toFixed(0)}%</div>
                </div>
                <div className={`text-sm font-bold ${pnlColor(r.total_pnl)}`}>
                  {sign(r.total_pnl)}¥{fmt(r.total_pnl)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 策略详情卡片 */}
      <div className="space-y-4">
        {(strategies.strategies || []).map((s: any) => {
          const meta = STRATEGY_META[s.name] || { desc: s.description || "", schedule: "-" };
          const strategyTrades = (trades.trades || []).filter((t: any) => t.strategy_name === s.display_name);
          const strategyPositions = (positions.positions || []).filter((p: any) => p.strategy_name === s.display_name);
          const wins = strategyTrades.filter((t: any) => t.side === "SELL" && (t.pnl ?? 0) > 0).length;
          const totalSells = strategyTrades.filter((t: any) => t.side === "SELL").length;
          const totalPnl = strategyTrades.filter((t: any) => t.side === "SELL").reduce((sum: number, t: any) => sum + (t.pnl ?? 0), 0);

          return (
            <div key={s.id} className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${s.is_active ? "border-black/5" : "border-dashed border-gray-200 opacity-70"}`}>
              {/* 策略头部 */}
              <div className="p-5 border-b border-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-bold text-white px-2.5 py-1.5 rounded-lg ${s.market === "A_SHARE" ? "bg-gradient-to-br from-[#e05555] to-[#f07070]" : "bg-gradient-to-br from-[#4f6ef7] to-[#7b93f9]"}`}>
                      {s.market === "A_SHARE" ? "A" : "U"}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[#1a1a2e]">{s.display_name}</span>
                        <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded ${s.is_active ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-400"}`}>
                          <span className={`inline-block w-1.5 h-1.5 rounded-full ${s.is_active ? "bg-green-500" : "bg-gray-400"}`} />
                          {s.is_active ? "运行中" : "已暂停"}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">{meta.desc}</div>
                      <div className="text-xs text-gray-300 mt-0.5">调度: {meta.schedule}</div>
                    </div>
                  </div>
                  <form action={async () => {
                    "use server";
                    await api.strategies.toggle(s.id, !s.is_active);
                  }}>
                    <button type="submit" className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${s.is_active ? "bg-red-50 text-[#e05555] hover:bg-red-100" : "bg-green-50 text-[#22c55e] hover:bg-green-100"}`}>
                      {s.is_active ? "暂停" : "启用"}
                    </button>
                  </form>
                </div>
              </div>

              {/* 绩效指标 */}
              <div className="grid grid-cols-5 border-b border-gray-50">
                <MetricCell label="总交易" value={`${s.performance?.total_trades ?? strategyTrades.length}笔`} />
                <MetricCell label="胜率" value={s.performance ? `${(s.performance.win_rate * 100).toFixed(1)}%` : totalSells > 0 ? `${((wins / totalSells) * 100).toFixed(1)}%` : "-"} />
                <MetricCell label="总盈亏" value={`${sign(s.performance?.total_pnl ?? totalPnl)}¥${fmt(s.performance?.total_pnl ?? totalPnl)}`} className={pnlColor(s.performance?.total_pnl ?? totalPnl)} />
                <MetricCell label="Sharpe" value={s.performance?.sharpe_ratio?.toFixed(2) ?? "-"} />
                <MetricCell label="持仓" value={`${strategyPositions.length}只`} />
              </div>

              {/* 当前持仓 */}
              {strategyPositions.length > 0 && (
                <div className="p-4 border-b border-gray-50">
                  <div className="text-xs text-gray-400 font-medium mb-2">当前持仓</div>
                  <div className="space-y-2">
                    {strategyPositions.map((p: any) => (
                      <div key={p.id} className="flex items-center justify-between text-sm">
                        <span className="font-mono text-xs font-semibold text-[#1a1a2e]">{p.symbol}</span>
                        <span className="text-gray-500">{p.name}</span>
                        <span className="text-gray-400">{p.shares}股</span>
                        <span>{(p.current_price || p.avg_cost).toFixed(2)}</span>
                        <span className={`font-semibold ${pnlColor(p.unrealized_pnl)}`}>{sign(p.unrealized_pnl)}¥{fmt(p.unrealized_pnl)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 最近交易 */}
              {strategyTrades.length > 0 && (
                <div className="p-4">
                  <div className="text-xs text-gray-400 font-medium mb-2">最近交易</div>
                  <div className="space-y-2">
                    {strategyTrades.slice(0, 5).map((t: any) => (
                      <div key={t.id} className="flex items-center justify-between text-sm">
                        <span className="text-xs text-gray-300">{t.executed_at?.slice(5, 16) || "-"}</span>
                        <span className={`text-xs px-2 py-0.5 rounded font-semibold ${t.side === "BUY" ? "bg-red-50 text-[#e05555]" : "bg-green-50 text-[#22c55e]"}`}>
                          {t.side === "BUY" ? "买入" : "卖出"}
                        </span>
                        <span className="font-mono text-xs text-[#1a1a2e]">{t.symbol}</span>
                        <span className="text-gray-400">{t.shares}股 @ {t.price.toFixed(2)}</span>
                        <span className={`font-semibold ${t.pnl != null ? pnlColor(t.pnl) : ""}`}>
                          {t.pnl != null ? `${sign(t.pnl)}¥${fmt(t.pnl)}` : "-"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!strategyTrades.length && !strategyPositions.length && (
                <div className="p-8 text-center text-sm text-gray-300">策略等待首次运行</div>
              )}
            </div>
          );
        })}
      </div>

      {/* 执行日志 */}
      {logs.logs.length > 0 && (
        <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
          <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">执行日志</h2>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {(logs.logs as any[]).map((l: any) => (
              <div key={l.id} className="flex items-start gap-2 text-sm">
                <span className="text-xs text-gray-300 shrink-0 mt-0.5 w-16">{l.created_at?.slice(5, 16)}</span>
                <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded font-medium ${
                  l.level === "error" ? "bg-red-50 text-red-500" :
                  l.level === "warn" ? "bg-amber-50 text-amber-600" :
                  "bg-blue-50 text-blue-500"
                }`}>{l.level}</span>
                <span className="font-semibold text-[#1a1a2e] shrink-0">{l.strategy_name}</span>
                <span className="text-gray-600">{l.message}</span>
                {l.detail && <span className="text-gray-400 text-xs truncate">{l.detail}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCell({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="p-3 text-center">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-sm font-bold mt-0.5 ${className || "text-[#1a1a2e]"}`}>{value}</div>
    </div>
  );
}

function AutoRefresh() {
  return (
    <script dangerouslySetInnerHTML={{ __html: `
      setInterval(function(){ location.reload(); }, 60000);
    `}} />
  );
}
