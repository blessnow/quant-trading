// 登录相关API通过Next.js proxy访问后端
// 本地开发时直接访问后端，生产环境走proxy
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "";

export async function sendSMS(phone: string) {
  const res = await fetch(`${API_BASE}/api/auth/send-sms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone }),
  });
  return res.json();
}

export async function registerPhone(phone: string, code: string, password?: string, nickname?: string) {
  const res = await fetch(`${API_BASE}/api/auth/register-phone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code, password, nickname }),
  });
  return res.json();
}

export async function loginPhone(phone: string, code?: string, password?: string) {
  const res = await fetch(`${API_BASE}/api/auth/login-phone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code, password }),
  });
  return res.json();
}

export async function getQRCode() {
  const res = await fetch(`${API_BASE}/api/auth/qrcode`);
  return res.json();
}

export async function checkLoginStatus(sessionId: string) {
  const res = await fetch(`${API_BASE}/api/auth/check-login?session_id=${sessionId}`);
  return res.json();
}

export async function confirmTestLogin(sessionId: string) {
  const res = await fetch(`${API_BASE}/api/auth/confirm-test-login?session_id=${sessionId}`, {
    method: "POST",
  });
  return res.json();
}

export async function getMe(token: string) {
  const res = await fetch(`${API_BASE}/api/wechat/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

export async function createNativeOrder(plan: string, token: string) {
  const res = await fetch(`${API_BASE}/api/pay/create-native-order`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ plan }),
  });
  return res.json();
}

export async function checkPayment(sessionId: string) {
  const res = await fetch(`${API_BASE}/api/pay/check-payment?session_id=${sessionId}`);
  return res.json();
}

export async function confirmNativeTest(sessionId: string) {
  const res = await fetch(`${API_BASE}/api/pay/confirm-native-test?session_id=${sessionId}`, {
    method: "POST",
  });
  return res.json();
}