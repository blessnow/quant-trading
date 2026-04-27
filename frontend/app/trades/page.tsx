import { api } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const revalidate = 30;

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pnlColor(n: number) {
  return n > 0 ? "text-[#e05555]" : n < 0 ? "text-[#22c55e]" : "text-gray-500";
}
function sign(n: number) {
  return n > 0 ? "+" : "";
}

export default async function TradesPage() {
  const data = await api.trades.list(100).catch(() => ({ trades: [] as any[], total: 0 }));

  return (
    <div className="space-y-5">
      {/* 深色 Hero */}
      <div className="bg-gradient-to-br from-[#1a1a2e] to-[#2d2b55] rounded-2xl p-6 text-white -mx-4 -mt-2 md:mx-0 md:mt-0">
        <h1 className="text-xl font-bold mb-1">交易记录</h1>
        <p className="text-white/40 text-sm">共 {data.total} 笔交易</p>
      </div>

      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        {data.trades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 border-b border-gray-100">
                  <th className="text-left py-2 font-medium">时间</th>
                  <th className="text-left py-2 font-medium">策略</th>
                  <th className="text-left py-2 font-medium">代码</th>
                  <th className="text-left py-2 font-medium">名称</th>
                  <th className="text-left py-2 font-medium">方向</th>
                  <th className="text-right py-2 font-medium">价格</th>
                  <th className="text-right py-2 font-medium">数量</th>
                  <th className="text-right py-2 font-medium">金额</th>
                  <th className="text-right py-2 font-medium">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t: any) => (
                  <tr key={t.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="py-2.5 text-xs text-gray-400">{t.executed_at?.slice(5, 16) || "-"}</td>
                    <td className="py-2.5 text-xs text-gray-500">{t.strategy_name || "-"}</td>
                    <td className="py-2.5 font-mono text-xs font-semibold text-[#1a1a2e]">{t.symbol}</td>
                    <td className="py-2.5 text-xs text-gray-500">{t.name || "-"}</td>
                    <td className="py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded font-semibold ${t.side === "BUY" ? "bg-red-50 text-[#e05555]" : "bg-green-50 text-[#22c55e]"}`}>
                        {t.side === "BUY" ? "买入" : "卖出"}
                      </span>
                    </td>
                    <td className="py-2.5 text-right font-mono text-[#1a1a2e]">{t.price?.toFixed(2) || "-"}</td>
                    <td className="py-2.5 text-right text-[#1a1a2e]">{t.shares || "-"}</td>
                    <td className="py-2.5 text-right text-gray-500">¥{fmt(t.notional)}</td>
                    <td className={`py-2.5 text-right font-bold ${t.pnl != null ? pnlColor(t.pnl) : ""}`}>
                      {t.pnl != null ? `${sign(t.pnl)}¥${fmt(t.pnl)}` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-300 py-12">暂无交易记录</div>
        )}
      </div>
    </div>
  );
}
