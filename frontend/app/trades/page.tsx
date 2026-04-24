import { api } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const revalidate = 30;

function formatMoney(n: number) {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default async function TradesPage() {
  const data = await api.trades.list(100).catch(() => ({ trades: [], total: 0 }));

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">交易记录</h2>
          <span className="text-sm text-gray-500">共 {data.total} 笔</span>
        </div>
        {data.trades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b">
                  <th className="text-left py-2 font-medium">时间</th>
                  <th className="text-left py-2 font-medium">策略</th>
                  <th className="text-left py-2 font-medium">代码</th>
                  <th className="text-left py-2 font-medium">市场</th>
                  <th className="text-left py-2 font-medium">方向</th>
                  <th className="text-right py-2 font-medium">价格</th>
                  <th className="text-right py-2 font-medium">数量</th>
                  <th className="text-right py-2 font-medium">金额</th>
                  <th className="text-right py-2 font-medium">手续费</th>
                  <th className="text-right py-2 font-medium">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t) => (
                  <tr key={t.id} className="border-b border-black/5 hover:bg-gray-50">
                    <td className="py-2 text-xs text-gray-500">{t.executed_at}</td>
                    <td className="py-2 text-xs">{t.strategy_name || "-"}</td>
                    <td className="py-2 font-mono">{t.symbol} {t.name}</td>
                    <td className="py-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${t.market === "A_SHARE" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
                        {t.market === "A_SHARE" ? "A股" : "美股"}
                      </span>
                    </td>
                    <td className="py-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${t.side === "BUY" ? "bg-red-50 text-red-600" : "bg-green-50 text-green-600"}`}>
                        {t.side === "BUY" ? "买入" : "卖出"}
                      </span>
                    </td>
                    <td className="py-2 text-right">{t.price.toFixed(2)}</td>
                    <td className="py-2 text-right">{t.shares}</td>
                    <td className="py-2 text-right">{formatMoney(t.notional)}</td>
                    <td className="py-2 text-right text-gray-500">{t.commission.toFixed(2)}</td>
                    <td className={`py-2 text-right font-medium ${t.pnl != null ? (t.pnl > 0 ? "text-red-500" : t.pnl < 0 ? "text-green-600" : "text-gray-500") : ""}`}>
                      {t.pnl != null ? `${t.pnl > 0 ? "+" : ""}${formatMoney(t.pnl)}` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-400 py-12">暂无交易记录</div>
        )}
      </div>
    </div>
  );
}
