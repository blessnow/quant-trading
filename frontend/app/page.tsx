import { cookies } from "next/headers";
import { api } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const revalidate = 30;

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pnlColor(n: number) {
  return n > 0 ? "text-[#e05555]" : n < 0 ? "text-[#22c55e]" : "text-gray-400";
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
  const totalPnl = (summary?.total_pnl || 0) - (summary?.initial_capital || 1000000);
  const pnlPct = summary?.initial_capital ? (totalPnl / summary.initial_capital) * 100 : 0;
  const aShare = summary?.markets?.A_SHARE;
  const usStock = summary?.markets?.US_STOCK;

  return (
    <div className="space-y-5">
      {/* 深色 Hero — 总资产 */}
      <div className="bg-gradient-to-br from-[#1a1a2e] to-[#2d2b55] rounded-2xl p-6 text-white -mx-4 -mt-2 md:mx-0 md:mt-0">
        <div className="text-white/50 text-sm mb-1">总资产 (RMB)</div>
        <div className="text-3xl font-bold mb-3">¥{fmt(totalValue)}</div>
        <div className="flex gap-6 text-sm">
          <span className={totalPnl >= 0 ? "text-[#ff8a8a]" : "text-[#6ee7b7]"}>
            今日 {sign(totalPnl)}¥{fmt(totalPnl)} ({sign(pnlPct)}{pnlPct.toFixed(2)}%)
          </span>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-5 pt-4 border-t border-white/10">
          <div>
            <div className="text-white/40 text-xs mb-1">A股</div>
            <div className="text-lg font-semibold">¥{fmt(aShare?.total || 500000)}</div>
            <div className={`text-xs ${(aShare?.total_pnl || 0) >= 0 ? "text-[#ff8a8a]" : "text-[#6ee7b7]"}`}>
              {sign(aShare?.total_pnl || 0)}¥{fmt(aShare?.total_pnl || 0)}
            </div>
          </div>
          <div>
            <div className="text-white/40 text-xs mb-1">美股</div>
            <div className="text-lg font-semibold">¥{fmt(usStock?.total || 500000)}</div>
            <div className={`text-xs ${(usStock?.total_pnl || 0) >= 0 ? "text-[#ff8a8a]" : "text-[#6ee7b7]"}`}>
              {sign(usStock?.total_pnl || 0)}¥{fmt(usStock?.total_pnl || 0)}
            </div>
          </div>
        </div>
        <div className="flex gap-4 mt-4 pt-3 border-t border-white/10 text-xs text-white/50">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${marketStatus?.a_share?.is_open ? "bg-green-400" : "bg-gray-500"}`} />
            A股 {marketStatus?.a_share?.is_open ? "交易中" : "休市"}
          </div>
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${marketStatus?.us_stock?.is_open ? "bg-green-400" : "bg-gray-500"}`} />
            美股 {marketStatus?.us_stock?.is_open ? "交易中" : "休市"}
          </div>
        </div>
      </div>

      {/* 收益曲线 */}
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">收益曲线</h2>
        {equityCurve.curve && equityCurve.curve.length >= 2 ? (
          <Chart data={equityCurve.curve} />
        ) : (
          <div className="h-48 flex items-center justify-center text-gray-400 text-sm bg-gray-50 rounded-xl">
            收盘后将生成净值曲线
          </div>
        )}
      </div>

      {/* 策略运行状态 */}
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">策略运行状态</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(strategies?.strategies || []).map((s: any) => (
            <div key={s.id} className={`rounded-xl border p-4 ${s.is_active ? "border-black/10 bg-gray-50/50" : "border-dashed border-gray-200 opacity-60"}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold text-white px-2 py-1 rounded-md ${s.market === "A_SHARE" ? "bg-gradient-to-br from-[#e05555] to-[#f07070]" : "bg-gradient-to-br from-[#4f6ef7] to-[#7b93f9]"}`}>
                    {s.market === "A_SHARE" ? "A" : "U"}
                  </span>
                  <span className="font-semibold text-sm text-[#1a1a2e]">{s.display_name}</span>
                </div>
                <span className={`w-2 h-2 rounded-full ${s.is_active ? "bg-green-500" : "bg-gray-300"}`} />
              </div>
              {s.performance ? (
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 mt-2">
                  <div>交易 <span className="font-medium text-gray-900">{s.performance.total_trades}笔</span></div>
                  <div>胜率 <span className="font-medium text-gray-900">{(s.performance.win_rate * 100).toFixed(1)}%</span></div>
                  <div>盈亏 <span className={`font-medium ${pnlColor(s.performance.total_pnl)}`}>{sign(s.performance.total_pnl)}{fmt(s.performance.total_pnl)}</span></div>
                  <div>Sharpe <span className="font-medium text-gray-900">{s.performance.sharpe_ratio?.toFixed(2) ?? "-"}</span></div>
                </div>
              ) : (
                <div className="text-xs text-gray-400 mt-2">等待首次运行</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 会员内容：持仓 + 交易 */}
      {isMember ? (
        <>
          {positions.positions.length > 0 && (
            <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
              <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">当前持仓 <span className="text-sm font-normal text-gray-400">{positions.positions.length}只</span></h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 border-b border-gray-100">
                      <th className="text-left py-2 font-medium">代码</th>
                      <th className="text-left py-2 font-medium">名称</th>
                      <th className="text-left py-2 font-medium">市场</th>
                      <th className="text-right py-2 font-medium">持仓</th>
                      <th className="text-right py-2 font-medium">成本</th>
                      <th className="text-right py-2 font-medium">现价</th>
                      <th className="text-right py-2 font-medium">浮盈</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.positions.map((p: any) => (
                      <tr key={p.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                        <td className="py-2.5 font-mono text-xs text-[#1a1a2e] font-semibold">{p.symbol}</td>
                        <td className="py-2.5 text-gray-700">{p.name}</td>
                        <td className="py-2.5"><MarketTag market={p.market} /></td>
                        <td className="py-2.5 text-right">{p.shares}</td>
                        <td className="py-2.5 text-right text-gray-500">{p.avg_cost.toFixed(2)}</td>
                        <td className="py-2.5 text-right">{(p.current_price || p.avg_cost).toFixed(2)}</td>
                        <td className={`py-2.5 text-right font-semibold ${pnlColor(p.unrealized_pnl)}`}>{sign(p.unrealized_pnl)}{fmt(p.unrealized_pnl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {trades.trades.length > 0 && (
            <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
              <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">最近交易</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 border-b border-gray-100">
                      <th className="text-left py-2 font-medium">时间</th>
                      <th className="text-left py-2 font-medium">代码</th>
                      <th className="text-left py-2 font-medium">方向</th>
                      <th className="text-right py-2 font-medium">价格</th>
                      <th className="text-right py-2 font-medium">数量</th>
                      <th className="text-right py-2 font-medium">盈亏</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.trades.map((t: any) => (
                      <tr key={t.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                        <td className="py-2.5 text-xs text-gray-400">{t.executed_at?.slice(5, 16) || "-"}</td>
                        <td className="py-2.5 font-mono text-xs text-[#1a1a2e] font-semibold">{t.symbol} <span className="text-gray-400 font-normal">{t.name}</span></td>
                        <td className="py-2.5"><SideTag side={t.side} /></td>
                        <td className="py-2.5 text-right">{t.price.toFixed(2)}</td>
                        <td className="py-2.5 text-right">{t.shares}</td>
                        <td className={`py-2.5 text-right font-semibold ${t.pnl != null ? pnlColor(t.pnl) : ""}`}>
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
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl border border-amber-200 p-8 text-center">
          <div className="text-lg font-semibold text-amber-800 mb-2">升级会员查看完整数据</div>
          <div className="text-sm text-amber-600 mb-4">持仓详情、交易记录、策略绩效等高级功能</div>
          <form action={async () => {
            "use server";
            const { cookies } = await import("next/headers");
            (await cookies()).set("is_member", "true", { path: "/", maxAge: 60 * 60 * 24 * 365 });
          }}>
            <button type="submit" className="px-6 py-2 bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 rounded-lg font-bold hover:from-amber-400 hover:to-amber-300 transition-all">
              立即升级
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function MarketTag({ market }: { market: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ${market === "A_SHARE" ? "bg-red-50 text-[#e05555]" : "bg-blue-50 text-[#4f6ef7]"}`}>
      {market === "A_SHARE" ? "A股" : "美股"}
    </span>
  );
}

function SideTag({ side }: { side: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-semibold ${side === "BUY" ? "bg-red-50 text-[#e05555]" : "bg-green-50 text-[#22c55e]"}`}>
      {side === "BUY" ? "买入" : "卖出"}
    </span>
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
            <line x1={px} y1={y} x2={w - px} y2={y} stroke="#f0f0f0" />
            <text x={px - 5} y={y + 4} textAnchor="end" className="text-[10px] fill-gray-400">¥{fmt(minV + p * range)}</text>
          </g>
        );
      })}
      {aShare.length >= 2 && <polyline points={pts(aShare)} fill="none" stroke="#e05555" strokeWidth={2} />}
      {usStock.length >= 2 && <polyline points={pts(usStock)} fill="none" stroke="#4f6ef7" strokeWidth={2} />}
      <circle cx={px + 10} cy={py + 5} r={4} fill="#e05555" />
      <text x={px + 18} y={py + 9} className="text-[11px] fill-gray-600">A股</text>
      <circle cx={px + 55} cy={py + 5} r={4} fill="#4f6ef7" />
      <text x={px + 63} y={py + 9} className="text-[11px] fill-gray-600">美股</text>
    </svg>
  );
}
