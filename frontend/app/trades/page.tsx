import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { createApiClient } from "@/lib/api-client";

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
  const cookieStore = await cookies();
  const isLoggedIn = cookieStore.get("is_member")?.value !== undefined || cookieStore.get("is_admin")?.value !== undefined;
  const isMember = cookieStore.get("is_member")?.value === "true" || cookieStore.get("is_admin")?.value === "true";

  if (!isLoggedIn) {
    redirect("/auth/login?redirect=/trades");
  }

  if (!isMember) {
    return (
      <div className="space-y-5">
        <div className="glass-card p-6 -mx-4 -mt-2 md:mx-0 md:mt-0">
          <h1 className="text-xl font-bold text-white mb-1">交易记录</h1>
        </div>
        <div className="glass-card p-8 text-center glow-blue">
          <div className="text-lg font-semibold text-white mb-2">会员专属内容</div>
          <div className="text-sm text-white/50 mb-6">完整交易记录为会员专属功能</div>
          <div className="flex gap-4 justify-center">
            <a href="/membership" className="btn-primary inline-block">
              立即升级
            </a>
            <Link href="/" className="inline-block px-6 py-2.5 rounded-lg border border-white/20 text-white/60 hover:text-white hover:border-white/40 transition-colors">
              返回首页
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const authToken = cookieStore.get("auth_token")?.value;
  const api = createApiClient(authToken);
  const data = await api.trades.list(100).catch(() => ({ trades: [] as any[], total: 0 }));

  return (
    <div className="space-y-5">
      {/* 深色 Hero */}
      <div className="glass-card p-6 -mx-4 -mt-2 md:mx-0 md:mt-0">
        <h1 className="text-xl font-bold text-white mb-1">交易记录</h1>
        <p className="text-white/40 text-sm">共 {data.total} 笔交易</p>
      </div>

      <div className="glass-card p-5">
        {data.trades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-white/50 border-b border-white/10">
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
                  <tr key={t.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-2.5 text-xs text-white/40">{t.executed_at?.slice(5, 16) || "-"}</td>
                    <td className="py-2.5 text-xs text-white/50">{t.strategy_name || "-"}</td>
                    <td className="py-2.5 font-mono text-xs font-semibold text-white">{t.symbol}</td>
                    <td className="py-2.5 text-xs text-white/50">{t.name || "-"}</td>
                    <td className="py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded font-semibold ${t.side === "BUY" ? "bg-red-500/20 text-red-400" : "bg-green-500/20 text-green-400"}`}>
                        {t.side === "BUY" ? "买入" : "卖出"}
                      </span>
                    </td>
                    <td className="py-2.5 text-right font-mono text-white">{t.price?.toFixed(2) || "-"}</td>
                    <td className="py-2.5 text-right text-white">{t.shares || "-"}</td>
                    <td className="py-2.5 text-right text-white/50">¥{fmt(t.notional)}</td>
                    <td className={`py-2.5 text-right font-bold ${t.pnl != null ? pnlColor(t.pnl) : ""}`}>
                      {t.pnl != null ? `${sign(t.pnl)}¥${fmt(t.pnl)}` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">📈</div>
            <p className="text-white/40 mb-1">暂无交易记录</p>
            <p className="text-white/20 text-sm">策略运行后将自动产生交易记录</p>
          </div>
        )}
      </div>
    </div>
  );
}
