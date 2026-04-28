import { cookies } from "next/headers";
import { serverBackendBase } from "@/lib/api-base";
import { api } from "@/lib/api-client";
import { RealtimeLogs } from "./components/RealtimeLogs";
import { LoginGuard } from "@/app/components/LoginGuard";

export const dynamic = "force-dynamic";

async function getSchedulerJobs() {
  const base = serverBackendBase();
  try {
    const res = await fetch(`${base}/api/scheduler/jobs`, {
      cache: "no-store",
    });
    return res.json();
  } catch {
    return { total: 0, jobs: [] };
  }
}

async function getHealth() {
  const base = serverBackendBase();
  try {
    const res = await fetch(`${base}/api/health`, {
      cache: "no-store",
    });
    return res.json();
  } catch {
    return { status: "unknown", checks: {} };
  }
}

async function getStrategyLogs() {
  const base = serverBackendBase();
  try {
    const res = await fetch(`${base}/api/strategies/logs?limit=50`, {
      cache: "no-store",
    });
    return res.json();
  } catch {
    return { logs: [], total: 0 };
  }
}

export default async function MonitorPage() {
  const cookieStore = await cookies();
  const isAdmin = cookieStore.get("is_admin")?.value === "true";

  if (!isAdmin) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="text-lg font-semibold text-white mb-2">无权限访问</div>
        <div className="text-sm text-white/50">系统监控仅对管理员开放</div>
      </div>
    );
  }

  const [health, scheduler, logs] = await Promise.all([
    getHealth(),
    getSchedulerJobs(),
    getStrategyLogs(),
  ]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">系统监控</h1>

      {/* 系统状态 */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4">系统状态</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="data-card p-4">
            <div className="text-white/50 text-sm mb-1">数据库</div>
            <div className={`text-lg font-semibold ${health.checks?.database === "ok" ? "text-green-400" : "text-red-400"}`}>
              {health.checks?.database === "ok" ? "正常" : health.checks?.database || "未知"}
            </div>
            {health.checks?.database === "ok" && (
              <div className="status-dot active mt-2" />
            )}
          </div>
          <div className="data-card p-4">
            <div className="text-white/50 text-sm mb-1">调度器</div>
            <div className={`text-lg font-semibold ${health.checks?.scheduler?.status === "running" ? "text-green-400" : "text-red-400"}`}>
              {health.checks?.scheduler?.status === "running" ? "运行中" : "已停止"}
            </div>
            <div className="text-xs text-white/40 mt-1">{health.checks?.scheduler?.jobs_count || 0} 个任务</div>
          </div>
          <div className="data-card p-4">
            <div className="text-white/50 text-sm mb-1">整体状态</div>
            <div className={`text-lg font-semibold ${health.status === "healthy" ? "text-green-400" : "text-yellow-400"}`}>
              {health.status === "healthy" ? "健康" : "降级运行"}
            </div>
          </div>
        </div>
      </div>

      {/* 调度任务 */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">调度任务</h2>
          <span className="text-sm text-white/40">{scheduler.total} 个</span>
        </div>
        <div className="overflow-x-auto">
          <table className="dark-table">
            <thead>
              <tr>
                <th>任务ID</th>
                <th>触发器</th>
                <th>下次运行</th>
              </tr>
            </thead>
            <tbody>
              {scheduler.jobs?.slice(0, 10).map((job: any) => (
                <tr key={job.id}>
                  <td className="font-mono text-white text-xs">{job.id}</td>
                  <td className="text-white/60 text-xs">{job.trigger}</td>
                  <td className="text-white/70 text-xs">{job.next_run || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 策略日志 */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">策略日志</h2>
          <span className="text-sm text-white/40">{logs.total} 条</span>
        </div>
        {logs.logs?.length > 0 ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {logs.logs.map((log: any) => (
              <div
                key={log.id}
                className={`p-3 rounded-lg text-sm border ${
                  log.level === "error"
                    ? "bg-red-500/10 border-red-500/20 text-red-400"
                    : log.level === "warn"
                    ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-400"
                    : "bg-white/5 border-white/10 text-white/70"
                }`}
              >
                <div className="flex justify-between items-start">
                  <span className="font-medium text-white">{log.strategy_name}</span>
                  <span className="text-xs opacity-60">{log.created_at}</span>
                </div>
                <div className="mt-1">{log.message}</div>
                {log.detail && <div className="mt-1 text-xs opacity-70">{log.detail}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-white/40 text-center py-8">暂无日志</div>
        )}
      </div>

      {/* 实时日志 */}
      <div className="glass-card p-6">
        <RealtimeLogs />
      </div>
    </div>
  );
}