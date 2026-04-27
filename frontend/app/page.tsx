import { cookies } from "next/headers";
import { api } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const revalidate = 30;

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function pnlColor(n: number) {
  return n > 0 ? "text-[#ef4444]" : n < 0 ? "text-[#22c55e]" : "text-white/40";
}

function sign(n: number) {
  return n > 0 ? "+" : "";
}

export default async function Dashboard() {
  const cookieStore = await cookies();
  const isMember = cookieStore.get("is_member")?.value === "true";

  const [summary, positions, trades, marketStatus, equityCurve, strategies] = await Promise.all([
    api.portfolio.summary().catch(() => null),
    isMember ? api.portfolio.positions().catch(() => ({ positions: [] as any[], total: 0 })) : Promise.resolve({ positions: [] as any[], total: 0 }),
    isMember ? api.trades.list(10).catch(() => ({ trades: [] as any[], total: 0 })) : Promise.resolve({ trades: [] as any[], total: 0 }),
    api.market.status().catch(() => null),
    api.portfolio.equityCurve(90).catch(() => ({ curve: [] as any[], count: 0 })),
    api.strategies.list().catch(() => ({ strategies: [] as any[] })),
  ]);

  const totalValue = summary?.total_value || 1000000;
  const totalPnl = summary?.total_pnl || 0;
  const pnlPct = summary?.initial_capital ? (totalPnl / summary.initial_capital) * 100 : 0;
  const aShare = summary?.markets?.A_SHARE;
  const usStock = summary?.markets?.US_STOCK;

  return (
    <div className="space-y-6">
      {/* Hero — 总资产卡片 */}
      <div className="glass-card p-6 glow-blue">
        <div className="flex items-center justify-between mb-4">
          <div className="text-white/50 text-sm">总资产 (RMB)</div>
          <div className="flex gap-3">
            <div className="flex items-center gap-2">
              <div className={`status-dot ${marketStatus?.a_share?.is_open ? "active" : "inactive"}`} />
              <span className="text-xs text-white/50">A股 {marketStatus?.a_share?.is_open ? "交易中" : "休市"}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={`status-dot ${marketStatus?.us_stock?.is_open ? "active" : "inactive"}`} />
              <span className="text-xs text-white/50">美股 {marketStatus?.us_stock?.is_open ? "交易中" : "休市"}</span>
            </div>
          </div>
        </div>

        <div className="big-number text-white mb-2">¥{fmt(totalValue)}</div>

        <div className="flex items-center gap-4 mb-6">
          <div className={`text-lg font-semibold ${pnlColor(totalPnl)}`}>
            今日 {sign(totalPnl)}¥{fmt(Math.abs(totalPnl))}
          </div>
          <div className={`px-2 py-1 rounded-md text-sm font-medium ${totalPnl >= 0 ? "bg-red-500/20 text-red-400" : "bg-green-500/20 text-green-400"}`}>
            {sign(pnlPct)}{pnlPct.toFixed(2)}%
          </div>
        </div>

        {/* 市场分布 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="data-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-md bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center">
                <span className="text-white text-xs font-bold">A</span>
              </div>
              <span className="text-white/60 text-sm">A股市场</span>
            </div>
            <div className="text-2xl font-bold text-white">¥{fmt(aShare?.total || 500000)}</div>
            <div className={`text-sm mt-1 ${pnlColor(aShare?.total_pnl || 0)}`}>
              {sign(aShare?.total_pnl || 0)}¥{fmt(Math.abs(aShare?.total_pnl || 0))}
            </div>
          </div>
          <div className="data-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-md bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center">
                <span className="text-white text-xs font-bold">U</span>
              </div>
              <span className="text-white/60 text-sm">美股市场</span>
            </div>
            <div className="text-2xl font-bold text-white">¥{fmt(usStock?.total || 500000)}</div>
            <div className={`text-sm mt-1 ${pnlColor(usStock?.total_pnl || 0)}`}>
              {sign(usStock?.total_pnl || 0)}¥{fmt(Math.abs(usStock?.total_pnl || 0))}
            </div>
          </div>
        </div>
      </div>

      {/* 收益曲线 */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">收益曲线</h2>
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-white/60">A股</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="text-white/60">美股</span>
            </div>
          </div>
        </div>
        {equityCurve.curve && equityCurve.curve.length >= 2 ? (
          <Chart data={equityCurve.curve} />
        ) : (
          <div className="h-48 flex items-center justify-center text-white/40 text-sm">
            收盘后将生成净值曲线
          </div>
        )}
      </div>

      {/* 策略运行状态 */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-bold text-white mb-4">策略运行状态</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(strategies?.strategies || []).map((s: any) => (
            <div key={s.id} className={`data-card p-4 ${s.is_active ? "" : "opacity-50"}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={`w-5 h-5 rounded-md flex items-center justify-center ${s.market === "A_SHARE" ? "bg-gradient-to-br from-red-500 to-red-600" : "bg-gradient-to-br from-blue-500 to-blue-600"}`}>
                    <span className="text-white text-xs font-bold">{s.market === "A_SHARE" ? "A" : "U"}</span>
                  </div>
                  <span className="font-semibold text-white">{s.display_name}</span>
                </div>
                <div className={`status-dot ${s.is_active ? "active" : "inactive"}`} />
              </div>
              {s.performance ? (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="text-white/50">交易 <span className="text-white font-medium">{s.performance.total_trades}笔</span></div>
                  <div className="text-white/50">胜率 <span className="text-white font-medium">{(s.performance.win_rate * 100).toFixed(1)}%</span></div>
                  <div className="text-white/50">盈亏 <span className={`font-medium ${pnlColor(s.performance.total_pnl)}`}>{sign(s.performance.total_pnl)}{fmt(s.performance.total_pnl)}</span></div>
                  <div className="text-white/50">Sharpe <span className="text-white font-medium">{s.performance.sharpe_ratio?.toFixed(2) ?? "-"}</span></div>
                </div>
              ) : (
                <div className="text-sm text-white/40">等待首次运行</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 会员内容：持仓 + 交易 */}
      {isMember ? (
        <>
          {positions.positions.length > 0 && (
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-white">当前持仓</h2>
                <span className="text-sm text-white/40">{positions.positions.length}只</span>
              </div>
              <div className="overflow-x-auto">
                <table className="dark-table">
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>市场</th>
                      <th className="text-right">持仓</th>
                      <th className="text-right">成本</th>
                      <th className="text-right">现价</th>
                      <th className="text-right">浮盈</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.positions.map((p: any) => (
                      <tr key={p.id}>
                        <td className="font-mono text-white font-semibold">{p.symbol}</td>
                        <td className="text-white/70">{p.name}</td>
                        <td>
                          <span className={p.market === "A_SHARE" ? "tag-red" : "tag-blue"}>
                            {p.market === "A_SHARE" ? "A股" : "美股"}
                          </span>
                        </td>
                        <td className="text-right text-white">{p.shares}</td>
                        <td className="text-right text-white/50">{p.avg_cost.toFixed(2)}</td>
                        <td className="text-right text-white">{(p.current_price || p.avg_cost).toFixed(2)}</td>
                        <td className={`text-right font-semibold ${pnlColor(p.unrealized_pnl)}`}>
                          {sign(p.unrealized_pnl)}{fmt(p.unrealized_pnl)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {trades.trades.length > 0 && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-bold text-white mb-4">最近交易</h2>
              <div className="overflow-x-auto">
                <table className="dark-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>代码</th>
                      <th>方向</th>
                      <th className="text-right">价格</th>
                      <th className="text-right">数量</th>
                      <th className="text-right">盈亏</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.trades.map((t: any) => (
                      <tr key={t.id}>
                        <td className="text-white/40">{t.executed_at?.slice(5, 16) || "-"}</td>
                        <td className="font-mono text-white font-semibold">{t.symbol} <span className="text-white/40">{t.name}</span></td>
                        <td>
                          <span className={t.side === "BUY" ? "tag-red" : "tag-green"}>
                            {t.side === "BUY" ? "买入" : "卖出"}
                          </span>
                        </td>
                        <td className="text-right text-white">{t.price.toFixed(2)}</td>
                        <td className="text-right text-white">{t.shares}</td>
                        <td className={`text-right font-semibold ${t.pnl != null ? pnlColor(t.pnl) : "text-white/40"}`}>
                          {t.pnl != null ? `${sign(t.pnl)}${fmt(t.pnl)}` : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="glass-card p-8 text-center glow-blue">
          <div className="text-lg font-semibold text-white mb-2">升级会员查看完整数据</div>
          <div className="text-sm text-white/50 mb-6">持仓详情、交易记录、策略绩效等高级功能</div>
          <form action={async () => {
            "use server";
            const { cookies } = await import("next/headers");
            (await cookies()).set("is_member", "true", { path: "/", maxAge: 60 * 60 * 24 * 365 });
          }}>
            <button type="submit" className="btn-primary">
              立即升级
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function Chart({ data }: { data: { market: string; total_value: number; date: string }[] }) {
  const aShare = data.filter((d) => d.market === "A_SHARE");
  const usStock = data.filter((d) => d.market === "US_STOCK");
  const allVals = data.map((d) => d.total_value);
  const minV = Math.min(...allVals) * 0.995;
  const maxV = Math.max(...allVals) * 1.005;
  const range = maxV - minV || 1;
  const w = 800, h = 240, px = 55, py = 15;

  function pts(arr: typeof data) {
    return arr.map((d, i) => {
      const x = px + (i / Math.max(arr.length - 1, 1)) * (w - 2 * px);
      const y = h - py - ((d.total_value - minV) / range) * (h - 2 * py);
      return `${x},${y}`;
    }).join(" ");
  }

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48">
      {[0, 0.25, 0.5, 0.75, 1].map((p) => {
        const y = h - py - p * (h - 2 * py);
        return (
          <g key={p}>
            <line x1={px} y1={y} x2={w - px} y2={y} stroke="rgba(255,255,255,0.06)" />
            <text x={px - 5} y={y + 4} textAnchor="end" className="text-[10px] fill-white/40">¥{fmt(minV + p * range)}</text>
          </g>
        );
      })}
      {aShare.length >= 2 && <polyline points={pts(aShare)} fill="none" stroke="#ef4444" strokeWidth={2} />}
      {usStock.length >= 2 && <polyline points={pts(usStock)} fill="none" stroke="#3b82f6" strokeWidth={2} />}
    </svg>
  );
}