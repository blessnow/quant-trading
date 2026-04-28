"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { sendSMS, loginPhone, authErrorMessage } from "@/lib/auth-api";

function LoginForm() {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loginMode, setLoginMode] = useState<"code" | "password">("password");
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const handleSendSMS = async () => {
    if (!phone || phone.length !== 11) {
      setError("请输入正确的手机号");
      return;
    }
    if (countdown > 0) return;

    try {
      const res = await sendSMS(phone);
      if (res.success) {
        setCountdown(60);
        const timer = setInterval(() => {
          setCountdown((c) => {
            if (c <= 1) {
              clearInterval(timer);
              return 0;
            }
            return c - 1;
          });
        }, 1000);
        setError("");
      } else {
        setError(authErrorMessage(res, "发送失败"));
      }
    } catch {
      setError("网络错误");
    }
  };

  const handleLogin = async () => {
    if (!phone || phone.length !== 11) {
      setError("请输入正确的手机号");
      return;
    }
    if (loginMode === "code" && !code) {
      setError("请输入验证码");
      return;
    }
    if (loginMode === "password" && !password) {
      setError("请输入密码");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await loginPhone(phone, loginMode === "code" ? code : undefined, loginMode === "password" ? password : undefined);
      const token = typeof res.token === "string" ? res.token : undefined;
      if (token) {
        login(token, {
          id: Number(res.user_id),
          nickname: typeof res.nickname === "string" ? res.nickname : "用户",
          is_member: Boolean(res.is_member),
          is_admin: Boolean(res.is_admin),
          member_expire_at:
            typeof res.member_expire_at === "string" ? res.member_expire_at : undefined,
        });
        const redirect = searchParams.get("redirect") || "/";
        router.push(redirect);
      } else {
        setError(authErrorMessage(res, "登录失败"));
      }
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f0f1a] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-[#1a1a2e] rounded-2xl p-8 shadow-xl">
        <h1 className="text-2xl font-bold text-white text-center mb-6">登录 QuantTrader</h1>

        <div className="flex bg-[#252542] rounded-lg p-1 mb-6">
          <button
            onClick={() => { setLoginMode("password"); setError(""); }}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${loginMode === "password" ? "bg-amber-500 text-amber-900" : "text-gray-400 hover:text-white"}`}
          >
            密码登录
          </button>
          <button
            onClick={() => { setLoginMode("code"); setError(""); }}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${loginMode === "code" ? "bg-amber-500 text-amber-900" : "text-gray-400 hover:text-white"}`}
          >
            验证码登录
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">手机号</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
              placeholder="请输入手机号"
              className="w-full px-4 py-3 bg-[#252542] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
            />
          </div>

          {loginMode === "password" ? (
            <div>
              <label className="block text-sm text-gray-400 mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                className="w-full px-4 py-3 bg-[#252542] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm text-gray-400 mb-1">验证码</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="请输入验证码"
                  className="flex-1 px-4 py-3 bg-[#252542] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
                />
                <button
                  onClick={handleSendSMS}
                  disabled={countdown > 0}
                  className="px-4 py-3 bg-[#252542] border border-gray-700 rounded-lg text-gray-300 hover:border-amber-500 hover:text-amber-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                >
                  {countdown > 0 ? `${countdown}s` : "发送验证码"}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">测试模式验证码: 123456</p>
            </div>
          )}

          {loginMode === "password" && (
            <p className="text-xs text-gray-500">测试管理员：10000000001 / 123456</p>
          )}

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 font-bold rounded-lg hover:from-amber-400 hover:to-amber-300 transition-all disabled:opacity-50"
          >
            {loading ? "登录中..." : "登录"}
          </button>
        </div>

        <div className="mt-6 text-center">
          <p className="text-gray-500 text-sm">
            还没有账号？
            <a href="/auth/register" className="text-amber-500 hover:underline ml-1">
              立即注册
            </a>
          </p>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-700 text-center">
          <a href="/" className="text-gray-500 text-sm hover:text-gray-400">
            返回首页
          </a>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#0f0f1a] flex items-center justify-center"><p className="text-gray-400">加载中...</p></div>}>
      <LoginForm />
    </Suspense>
  );
}
