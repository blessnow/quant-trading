"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { sendSMS, registerPhone, authErrorMessage } from "@/lib/auth-api";

export default function RegisterPage() {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [nickname, setNickname] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
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

  const handleRegister = async () => {
    if (!phone || !code) {
      setError("请填写完整信息");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await registerPhone(phone, code, undefined, nickname || undefined);
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
        router.push("/");
      } else {
        setError(authErrorMessage(res, "注册失败"));
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
        <h1 className="text-2xl font-bold text-white text-center mb-8">注册 QuantTrader</h1>

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
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">昵称（可选）</label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="请输入昵称"
              className="w-full px-4 py-3 bg-[#252542] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <button
            onClick={handleRegister}
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 font-bold rounded-lg hover:from-amber-400 hover:to-amber-300 transition-all disabled:opacity-50"
          >
            {loading ? "注册中..." : "注册"}
          </button>
        </div>

        <div className="mt-6 text-center">
          <p className="text-gray-500 text-sm">
            已有账号？
            <a href="/auth/login" className="text-amber-500 hover:underline ml-1">
              立即登录
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
