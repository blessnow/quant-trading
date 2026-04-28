import { clientApiOrigin } from "./api-base";

/** 供页面展示错误文案（避免 unknown 触发 TS 报错） */
export function authErrorMessage(
  res: Record<string, unknown>,
  fallback: string
): string {
  const d = res.detail;
  return typeof d === "string" && d.length > 0 ? d : fallback;
}

async function fetchAuthJson(
  path: string,
  init?: RequestInit
): Promise<Record<string, unknown>> {
  const base = clientApiOrigin();
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, init);
  } catch {
    return { detail: "网络异常，请检查网络或稍后重试" };
  }
  const text = await res.text();
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
