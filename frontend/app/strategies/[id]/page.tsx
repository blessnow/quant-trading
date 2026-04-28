import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { serverBackendBase } from "@/lib/api-base";
import { StrategyEquityChart } from "@/app/components/StrategyEquityChart";
import { TradesList, PositionsList } from "@/app/components/LoadMoreList";

export const dynamic = "force-dynamic";

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
  ChenXiaoqunShort: { desc: "短线情绪博弈，追涨杀跌", schedule: "每5分钟 9:30-14:00 CST" },
  YuGeValue: { desc: "价值投资，长期持有", schedule: "每日 09:00 CST" },
};

async function fetchData(strategyId: number, backendUrl: string, authToken?: string) {
  const headers: Record<string, string> = {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const [strategy, equityCurve, positions, trades, logs] = await Promise.all([
    fetch(`${backendUrl}/api/strategies/${strategyId}`, { cache: "no-store", headers }).then(r => r.json()).catch(() => null),
    fetch(`${backendUrl}/api/strategies/${strategyId}/equity-curve?days=90`, { cache: "no-store", headers }).then(r => r.json()).catch(() => ({ curve: [] })),
    fetch(`${backendUrl}/api/strategies/${strategyId}/positions`, { cache: "no-store", headers }).then(r => r.json()).catch(() => ({ positions: [] })),
    fetch(`${backendUrl}/api/strategies/${strategyId}/trades?limit=100`, { cache: "no-store", headers }).then(r => r.json()).catch(() => ({ trades: [] })),
    fetch(`${backendUrl}/api/strategies/logs?strategy_id=${strategyId}&limit=50`, { cache: "no-store", headers }).then(r => r.json()).catch(() => ({ logs: [] })),
  ]);
  return { strategy, equityCurve, positions, trades, logs };
}

export default async function StrategyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const strategyId = parseInt(id);

  const cookieStore = await cookies();
  const isLoggedIn = cookieStore.get("is_member")?.value !== undefined || cookieStore.get("is_admin")?.value !== undefined;
  const isMember = cookieStore.get("is_member")?.value === "true" || cookieStore.get("is_admin")?.value === "true";

  if (!isLoggedIn) {
    redirect("/auth/login?redirect=/strategies/" + id);
  }

  if (!isMember) {
    return (
      <div className="space-y-5">
        <Link href="/strategies" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          ← 返回策略列表
        </Link>
        <div className="glass-card p-8 text-center glow-blue">
          <div className="text-lg font-semibold text-white mb-2">会员专属内容</div>
          <div className="text-sm text-white/50 mb-6">策略详情、持仓、交易记录等为会员专属功能</div>
          <div className="flex gap-4 justify-center">
            <a href="/membership" className="btn-primary inline-block">
              立即升级
            </a>
            <Link href="/strategies" className="inline-block px-6 py-2.5 rounded-lg border border-white/20 text-white/60 hover:text-white hover:border-white/40 transition-colors">
              返回列表
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const backendUrl = serverBackendBase();
  const authToken = cookieStore.get("auth_token")?.value;
  const { strategy, equityCurve, positions, trades, logs } = await fetchData(strategyId, backendUrl, authToken);

  if (!strategy || strategy.error) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="text-lg font-semibold text-white mb-2">策略不存在</div>
        <Link href="/strategies" className="text-sm text-white/50 hover:text-white">返回策略列表</Link>
      </div>
    );
  }

  const meta = STRATEGY_META[strategy.name] || { desc: strategy.description || "", schedule: "-" };
  const perf = strategy.performance;
  const wins = trades.trades?.filter((t: any) => t.side === "SELL" && (t.pnl ?? 0) > 0).length || 0;
  const totalSells = trades.trades?.filter((t: any) => t.side === "SELL").length || 0;

  return (
    <div className="space-y-5">
      {/* 返回链接 */}
      <Link href="/strategies" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        ← 返回策略列表
      </Link>

      {/* 策略头部 */}
      <div className="bg-gradient-to-br from-[#1a1a2e] to-[#2d2b55] rounded-2xl p-6 text-white -mx-4 md:mx-0">
        <div className="flex items-center gap-3 mb-3">
          <span className={`text-sm font-bold px-3 py-1.5 rounded-lg ${strategy.market === "A_SHARE" ? "bg-gradient-to-br from-[#e05555] to-[#f07070]" : "bg-gradient-to-br from-[#4f6ef7] to-[#7b93f9]"}`}>
            {strategy.market === "A_SHARE" ? "A股" : "美股"}
          </span>
          <h1 className="text-2xl font-bold">{strategy.display_name}</h1>
          <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded ${strategy.is_active ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-400"}`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${strategy.is_active ? "bg-green-400" : "bg-gray-400"}`} />
            {strategy.is_active ? "运行中" : "已暂停"}
          </span>
        </div>
        <p className="text-white/60 mb-2">{meta.desc}</p>
        <p className="text-white/40 text-sm">调度: {meta.schedule}</p>
      </div>

      {/* 绩效指标 */}
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">绩效指标</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <MetricCard label="总交易" value={`${perf?.total_trades ?? 0}笔`} />
          <MetricCard label="胜率" value={perf ? `${(perf.win_rate * 100).toFixed(1)}%` : totalSells > 0 ? `${((wins / totalSells) * 100).toFixed(1)}%` : "-"} />
          <MetricCard label="总盈亏" value={`${sign(perf?.total_pnl ?? 0)}¥${fmt(perf?.total_pnl ?? 0)}`} className={pnlColor(perf?.total_pnl ?? 0)} />
          <MetricCard label="Sharpe" value={perf?.sharpe_ratio?.toFixed(2) ?? "-"} />
          <MetricCard label="最大回撤" value={perf ? `${(perf.max_drawdown_pct * 100).toFixed(1)}%` : "-"} />
        </div>
      </div>

      {/* 收益曲线 */}
      <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
        <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">收益曲线</h2>
        {equityCurve.curve && equityCurve.curve.length >= 1 ? (
          <StrategyEquityChart data={equityCurve.curve} color={strategy.market === "A_SHARE" ? "#e05555" : "#4f6ef7"} />
        ) : (
          <div className="h-48 flex items-center justify-center text-gray-400 text-sm bg-gray-50 rounded-xl">
            暂无数据
          </div>
        )}
      </div>

      {/* 当前持仓 */}
      <PositionsList strategyId={strategyId} initialPositions={positions.positions || []} />

      {/* 历史交易 */}
      <TradesList strategyId={strategyId} initialTrades={trades.trades || []} />

      {/* 执行日志 */}
      {logs.logs && logs.logs.length > 0 && (
        <div className="bg-white rounded-2xl border border-black/5 p-5 shadow-sm">
          <h2 className="text-lg font-bold text-[#1a1a2e] mb-4">执行日志</h2>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {logs.logs.map((l: any) => (
              <div key={l.id} className="flex items-start gap-2 text-sm">
                <span className="text-xs text-gray-300 shrink-0 mt-0.5 w-16">{l.created_at?.slice(5, 16)}</span>
                <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded font-medium ${
                  l.level === "error" ? "bg-red-50 text-red-500" :
                  l.level === "warn" ? "bg-amber-50 text-amber-600" :
                  "bg-blue-50 text-blue-500"
                }`}>{l.level}</span>
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

function MetricCard({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-lg font-bold mt-1 ${className || "text-[#1a1a2e]"}`}>{value}</div>
    </div>
  );
}
