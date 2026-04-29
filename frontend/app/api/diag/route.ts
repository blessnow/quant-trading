import { serverBackendBase } from "@/lib/api-base";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

/** 同源 GET，用于排查：504@~55s = 前端代理后端超时（见 app/api/auth）。勿暴露内网 URL。 */

export async function GET() {
  const base = serverBackendBase().replace(/\/$/, "");
  const hasBackendEnv = Boolean(
    process.env.BACKEND_URL?.trim() || process.env.RAILWAY_SERVICE_BACKEND_URL?.trim()
  );

  const ac1 = new AbortController();
  const t1 = setTimeout(() => ac1.abort(), 20_000);
  const tHealth0 = Date.now();
  let healthMs: number | null = null;
  let healthOk: boolean | null = null;
  let healthPreview: string | undefined;
  try {
    const r = await fetch(`${base}/api/health`, {
      cache: "no-store",
      signal: ac1.signal,
    });
    healthMs = Date.now() - tHealth0;
    healthOk = r.ok;
    healthPreview = (await r.text()).slice(0, 240);
  } catch (e) {
    healthMs = Date.now() - tHealth0;
    healthPreview = e instanceof Error ? e.message : String(e);
  } finally {
    clearTimeout(t1);
  }

  const ac2 = new AbortController();
  const t2 = setTimeout(() => ac2.abort(), 20_000);
  const tPost0 = Date.now();
  let postMs: number | null = null;
  let postStatus: number | undefined;
  let postPreview: string | undefined;
  try {
    const r = await fetch(`${base}/api/auth/login-phone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        phone: "19999999999",
        password: "diag_probe_invalid",
      }),
      cache: "no-store",
      signal: ac2.signal,
    });
    postMs = Date.now() - tPost0;
    postStatus = r.status;
    postPreview = (await r.text()).slice(0, 240);
  } catch (e) {
    postMs = Date.now() - tPost0;
    postPreview = e instanceof Error ? e.message : String(e);
  } finally {
    clearTimeout(t2);
  }

  let hint: string | undefined;
  if (!hasBackendEnv) {
    hint = "未设置 BACKEND_URL / RAILWAY_SERVICE_BACKEND_URL，服务端会回退 127.0.0.1:8000（容器内通常错误）。";
  } else if ((healthMs ?? 0) > 15_000 || healthOk === false) {
    hint =
      "GET /api/health 慢或失败：请在前端服务把 BACKEND_URL 设为后端在 Railway「私网」里显示的完整地址，端口必须与后端进程监听的 PORT 一致（勿默认写 :8000，除非后端环境变量 PORT 确为 8000）。";
  } else if ((postMs ?? 0) > 15_000) {
    hint =
      "POST /api/auth/login-phone 探测超时：与登录 504 同源。优先核对私网地址与端口；其次看后端日志是否在处理该请求。";
  } else if (healthOk && postStatus === 400) {
    hint =
      "后端 GET/POST 探测正常。若真实登录仍 504，多为当时负载或公司网络；可对比手机热点或查后端该时段日志。";
  } else if (healthOk && postStatus !== undefined && postStatus >= 500) {
    hint = "后端返回 5xx，请看 login_post_preview。";
  }

  return Response.json(
    {
      hasBackendEnv,
      health_ms: healthMs,
      health_ok: healthOk,
      health_preview: healthPreview,
      login_post_ms: postMs,
      login_post_status: postStatus,
      login_post_preview: postPreview,
      explain:
        "登录接口 504 且约 55 秒：来自前端 Route Handler 内对后端的 fetch 超时（UPSTREAM_MS）。页面 GET 200 只说明 Next 正常，不说明前端容器能连上后端。",
      hint,
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}
