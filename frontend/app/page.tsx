import { cookies } from "next/headers";
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

export default async function Dashboard() {
  const cookieStore = await cookies();
  const isMember = cookieStore.get("is_member")?.value === "true";

  const [summary, positions, trades, marketStatus, equityCurve, strategies] = await Promise.all([
    api.portfolio.summary().catch(() => null),
    isMember ? api.portfolio.positions().catch(() => ({ positions: [], total: 0 })) : Promise.resolve({ positions: [], total: 0 }),
    isMember ? api.trades.list(10).catch(() => ({ trades: [], total: 0 })) : Promise.resolve({ trades: [], total: 0 }),
    api.market.status().catch(() => null),
    api.portfolio.equityCurve(90).catch(() => ({ curve: [], count: 0 })),
    api.strategies.list().catch(() => ({ strategies: [] })),
  ]);

  const totalValue = summary?.total_value || 1000000;
  const totalPnl = summary?.total_pnl || 0;
  const pnlPct = totalValue > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;
  const aShare = summary?.markets?.A_SHARE;
  const usStock = summary?.markets?.US_STOCK;

  return (
    <div className="space-y-6">
      {/* 顶部概览 — 所有人可见 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card label="总资产" value={`¥${fmt(totalValue)}`} sub={`${sign(totalPnl)}¥${fmt(totalPnl)} (${sign(pnlPct)}${pnlPct.toFixed(2)}%)`} subClass={pnl(totalPnl)} />
        <Card label="A股" value={`¥${fmt(aShare?.total || 500000)}`} sub={`${sign(aShare?.total_pnl || 0)}¥${fmt(aShare?.total_pnl || 0)}`} subClass={pnl(aShare?.total_pnl || 0)} />
        <Card label="美股" value={`¥${fmt(usStock?.total || 500000)}`} sub={`${sign(usStock?.total_pnl || 0)}¥${fmt(usStock?.total_pnl || 0)}`} subClass={pnl(usStock?.total_pnl || 0)} />
        <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
          <div className="text-sm text-gray-500 mb-3">市场状态</div>
          <div className="flex items-center gap-2 text-sm">
            <Dot on={marketStatus?.a_share?.is_open} /> A股 {marketStatus?.a_share?.is_open ? "交易中" : "休市"}
          </div>
          <div className="flex items-center gap-2 text-sm mt-1">
            <Dot on={marketStatus?.us_stock?.is_open} /> 美股 {marketStatus?.us_stock?.is_open ? "交易中" : "休市"}
          </div>
        </div>
      </div>

      {/* 收益曲线 — 所有人可见 */}
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">收益曲线</h2>
        {equityCurve.curve.length >= 2 ? (
          <Chart data={equityCurve.curve} />
        ) : (
          <div className="h-48 flex items-center justify-center text-gray-400 text-sm">系统启动后将开始记录净值数据</div>
        )}
      </div>

      {/* 策略概览 — 所有人可见（但详情需要会员） */}
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">策略运行状态</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {strategies.strategies.map((s) => (
            <div key={s.id} className={`rounded-xl border p-4 ${s.is_active ? "border-black/10 bg-gray-50/50" : "border-dashed border-gray-200 opacity-60"}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-sm">{s.display_name}</span>
                <div className="flex items-center gap-1.5">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${s.market === "A_SHARE" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
                    {s.market === "A_SHARE" ? "A股" : "美股"}
                  </span>
                  <Dot on={s.is_active} />
                </div>
              </div>
              {isMember && s.performance ? (
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
                  <div>交易 <span className="font-medium text-gray-900">{s.performance.total_trades}笔</span></div>
                  <div>胜率 <span className="font-medium text-gray-900">{(s.performance.win_rate * 100).toFixed(1)}%</span></div>
                  <div>盈亏 <span className={`font-medium ${pnl(s.performance.total_pnl)}`}>{sign(s.performance.total_pnl)}{fmt(s.performance.total_pnl)}</span></div>
                  <div>Sharpe <span className="font-medium text-gray-900">{s.performance.sharpe_ratio?.toFixed(2) ?? "-"}</span></div>
                </div>
              ) : isMember ? (
                <div className="text-xs text-gray-400">等待首次运行</div>
              ) : (
                <div className="text-xs text-gray-400">升级会员查看详情</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 会员内容：持仓 + 交易 */}
      {isMember ? (
        <>
          <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
            <h2 className="text-lg font-semibold mb-4">当前持仓</h2>
            {positions.positions.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b">
                    <th className="text-left py-2 font-medium">策略</th>
                    <th className="text-left py-2 font-medium">代码</th>
                    <th className="text-left py-2 font-medium">名称</th>
                    <th className="text-left py-2 font-medium">市场</th>
                    <th className="text-right py-2 font-medium">持仓</th>
                    <th className="text-right py-2 font-medium">成本</th>
                    <th className="text-right py-2 font-medium">现价</th>
                    <th className="text-right py-2 font-medium">浮盈</th>
                    <th className="text-right py-2 font-medium">市值</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.positions.map((p) => (
                    <tr key={p.id} className="border-b border-black/5 hover:bg-gray-50">
                      <td className="py-2 text-xs text-gray-500">{p.strategy_name}</td>
                      <td className="py-2 font-mono text-xs">{p.symbol}</td>
                      <td className="py-2">{p.name}</td>
                      <td className="py-2"><MarketTag market={p.market} /></td>
                      <td className="py-2 text-right">{p.shares}</td>
                      <td className="py-2 text-right">{p.avg_cost.toFixed(2)}</td>
                      <td className="py-2 text-right">{(p.current_price || p.avg_cost).toFixed(2)}</td>
                      <td className={`py-2 text-right font-medium ${pnl(p.unrealized_pnl)}`}>{sign(p.unrealized_pnl)}{fmt(p.unrealized_pnl)}</td>
                      <td className="py-2 text-right">¥{fmt(p.market_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-center text-gray-400 py-8">暂无持仓</div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
            <h2 className="text-lg font-semibold mb-4">最近交易</h2>
            {trades.trades.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b">
                    <th className="text-left py-2 font-medium">时间</th>
                    <th className="text-left py-2 font-medium">策略</th>
                    <th className="text-left py-2 font-medium">代码</th>
                    <th className="text-left py-2 font-medium">方向</th>
                    <th className="text-right py-2 font-medium">价格</th>
                    <th className="text-right py-2 font-medium">数量</th>
                    <th className="text-right py-2 font-medium">盈亏</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.trades.map((t) => (
                    <tr key={t.id} className="border-b border-black/5 hover:bg-gray-50">
                      <td className="py-2 text-xs text-gray-500">{t.executed_at?.slice(5, 19)}</td>
                      <td className="py-2 text-xs">{t.strategy_name}</td>
                      <td className="py-2 font-mono text-xs">{t.symbol} {t.name}</td>
                      <td className="py-2"><SideTag side={t.side} /></td>
                      <td className="py-2 text-right">{t.price.toFixed(2)}</td>
                      <td className="py-2 text-right">{t.shares}</td>
                      <td className={`py-2 text-right font-medium ${t.pnl != null ? pnl(t.pnl) : ""}`}>
                        {t.pnl != null ? `${sign(t.pnl)}${fmt(t.pnl)}` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-center text-gray-400 py-8">暂无交易记录</div>
            )}
          </div>
        </>
      ) : (
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl border border-amber-200 p-8 text-center">
          <div className="text-lg font-semibold text-amber-800 mb-2">升级会员查看完整数据</div>
          <div className="text-sm text-amber-600 mb-4">会员可查看持仓详情、交易记录、策略管理等高级功能</div>
          <form action={async () => {
            "use server";
            const { cookies } = await import("next/headers");
            (await cookies()).set("is_member", "true", { path: "/", maxAge: 60 * 60 * 24 * 365 });
          }}>
            <button type="submit" className="px-6 py-2 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 transition-colors">
              立即升级
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function Card({ label, value, sub, subClass }: { label: string; value: string; sub: string; subClass?: string }) {
  return (
    <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      <div className={`text-sm mt-1 ${subClass || ""}`}>{sub}</div>
    </div>
  );
}

function Dot({ on }: { on?: boolean }) {
  return <span className={`inline-block w-2 h-2 rounded-full ${on ? "bg-green-500" : "bg-gray-300"}`} />;
}

function MarketTag({ market }: { market: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${market === "A_SHARE" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
      {market === "A_SHARE" ? "A股" : "美股"}
    </span>
  );
}

function SideTag({ side }: { side: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${side === "BUY" ? "bg-red-50 text-red-600" : "bg-green-50 text-green-600"}`}>
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
      {aShare.length >= 2 && <polyline points={pts(aShare)} fill="none" stroke="#ef4444" strokeWidth={2} />}
      {usStock.length >= 2 && <polyline points={pts(usStock)} fill="none" stroke="#3b82f6" strokeWidth={2} />}
      <circle cx={px + 10} cy={py + 5} r={4} fill="#ef4444" />
      <text x={px + 18} y={py + 9} className="text-[11px] fill-gray-600">A股</text>
      <circle cx={px + 60} cy={py + 5} r={4} fill="#3b82f6" />
      <text x={px + 68} y={py + 9} className="text-[11px] fill-gray-600">美股</text>
    </svg>
  );
}
