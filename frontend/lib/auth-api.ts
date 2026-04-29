/** 供页面展示错误文案（避免 unknown 触发 TS 报错） */
export function authErrorMessage(
  res: Record<string, unknown>,
  fallback: string
): string {
  const d = res.detail;
  return typeof d === "string" && d.length > 0 ? d : fallback;
}

const AUTH_FETCH_TIMEOUT_MS = 45_000;

/** 始终走同源 `/api`，避免 NEXT_PUBLIC 在构建时被内联成 localhost 打进线上包 */
async function fetchAuthJson(
  path: string,
  init?: RequestInit,
  timeoutMs: number = AUTH_FETCH_TIMEOUT_MS
): Promise<Record<string, unknown>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const merged: RequestInit = {
    ...init,
    signal: controller.signal,
    cache: "no-store",
  };

  let res: Response;
  try {
    res = await fetch(path, merged);
  } catch (e) {
    clearTimeout(timer);
    const aborted = e instanceof DOMException && e.name === "AbortError";
    return {
      detail: aborted ? "请求超时，请检查网络或稍后重试" : "网络异常，请检查网络或稍后重试",
    };
  }
  clearTimeout(timer);

  let text: string;
  try {
    text = await res.text();
  } catch {
    return { detail: res.ok ? "响应读取失败" : `服务暂时不可用（${res.status}）` };
  }
  let data: Record<string, unknown> = {};
  try {
    data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {
    return {
      detail: res.ok
        ? "响应格式异常"
        : `服务暂时不可用（${res.status}）`,
    };
  }
  if (!res.ok && typeof data.detail !== "string") {
    data.detail = `请求失败（${res.status}）`;
  }
  return data;
}

export async function sendSMS(phone: string) {
  return fetchAuthJson("/api/auth/send-sms", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone }),
  });
}

export async function registerPhone(
  phone: string,
  code: string,
  password?: string,
  nickname?: string
) {
  return fetchAuthJson("/api/auth/register-phone", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code, password, nickname }),
  });
}

export async function loginPhone(
  phone: string,
  code?: string,
  password?: string
) {
  return fetchAuthJson("/api/auth/login-phone", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code, password }),
  });
}

export async function getQRCode() {
  return fetchAuthJson("/api/auth/qrcode");
}

export async function checkLoginStatus(sessionId: string) {
  return fetchAuthJson(`/api/auth/check-login?session_id=${encodeURIComponent(sessionId)}`);
}

export async function confirmTestLogin(sessionId: string) {
  return fetchAuthJson(
    `/api/auth/confirm-test-login?session_id=${encodeURIComponent(sessionId)}`,
    { method: "POST" }
  );
}

export async function getMe(token: string) {
  return fetchAuthJson("/api/wechat/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function createNativeOrder(plan: string, token: string) {
  return fetchAuthJson("/api/pay/create-native-order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ plan }),
  });
}

export async function checkPayment(sessionId: string) {
  return fetchAuthJson(
    `/api/pay/check-payment?session_id=${encodeURIComponent(sessionId)}`
  );
}

export async function confirmNativeTest(sessionId: string) {
  return fetchAuthJson(
    `/api/pay/confirm-native-test?session_id=${encodeURIComponent(sessionId)}`,
    { method: "POST" }
  );
}
