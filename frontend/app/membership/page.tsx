"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { createNativeOrder, checkPayment, confirmNativeTest } from "@/lib/auth-api";

const showNativeTestConfirm =
  process.env.NODE_ENV === "development";

const PLANS = [
  { id: "monthly", name: "月度会员", price: 49, days: 30 },
  { id: "yearly", name: "年度会员", price: 399, days: 365, recommend: true },
];

const BENEFITS = [
  "实时持仓详情",
  "完整交易记录",
  "策略绩效排行",
  "收益曲线全周期数据",
  "策略启停控制",
];

export default function MembershipPage() {
  const [selectedPlan, setSelectedPlan] = useState("yearly");
  const [loading, setLoading] = useState(false);
  const [paymentSession, setPaymentSession] = useState<{
    sessionId: string;
    qrCodeUrl: string;
    orderNo: string;
    testMode: boolean;
  } | null>(null);
  const [paymentStatus, setPaymentStatus] = useState<"idle" | "pending" | "paid" | "expired">("idle");
  const [error, setError] = useState("");
  const router = useRouter();
  const { user, token, refreshUser } = useAuth();

  // 轮询支付状态
  useEffect(() => {
    if (paymentStatus !== "pending" || !paymentSession) return;

    const interval = setInterval(async () => {
      try {
        const res = await checkPayment(paymentSession.sessionId);
        if (res.status === "paid") {
          setPaymentStatus("paid");
          clearInterval(interval);
          await refreshUser();
          setTimeout(() => router.push("/"), 2000);
        } else if (res.status === "expired") {
          setPaymentStatus("expired");
          clearInterval(interval);
        }
      } catch {
        console.error("检查支付状态失败");
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [paymentStatus, paymentSession, refreshUser, router]);

  const handlePay = async () => {
    if (!token) {
      router.push("/auth/login?redirect=/membership");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await createNativeOrder(selectedPlan, token);
      if (res.session_id) {
        setPaymentSession({
          sessionId: res.session_id,
          qrCodeUrl: res.qr_code_url,
          orderNo: res.order_no,
          testMode: res.test_mode,
        });
        setPaymentStatus("pending");
      } else {
        setError(res.detail || "创建订单失败");
      }
    } catch {
      setError("网络错误");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmTest = async () => {
    if (!paymentSession) return;

    try {
      const res = await confirmNativeTest(paymentSession.sessionId);
      if (res.success) {
        setPaymentStatus("paid");
        await refreshUser();
        setTimeout(() => router.push("/"), 1500);
      } else {
        setError("确认失败");
      }
    } catch {
      setError("网络错误");
    }
  };

  if (paymentStatus === "paid") {
    return (
      <div className="min-h-screen bg-[#0f0f1a] flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-6xl mb-4">✓</div>
          <h1 className="text-2xl font-bold text-white mb-2">支付成功</h1>
          <p className="text-gray-400">会员已激活，正在跳转...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f0f1a] py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white text-center mb-8">QuantTrader 会员服务</h1>

        {/* 会员权益 */}
        <div className="bg-[#1a1a2e] rounded-2xl p-6 mb-8">
          <h2 className="text-lg font-semibold text-white mb-4">会员权益</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {BENEFITS.map((benefit) => (
              <div key={benefit} className="flex items-center gap-2 text-gray-300">
                <span className="text-amber-500">✓</span>
                <span className="text-sm">{benefit}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 套餐选择 */}
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          {PLANS.map((plan) => (
            <button
              key={plan.id}
              onClick={() => setSelectedPlan(plan.id)}
              className={`relative bg-[#1a1a2e] rounded-2xl p-6 text-left transition-all ${
                selectedPlan === plan.id ? "ring-2 ring-amber-500" : "hover:bg-[#252542]"
              }`}
            >
              {plan.recommend && (
                <span className="absolute top-3 right-3 text-xs px-2 py-1 bg-amber-500 text-amber-900 rounded-full font-bold">
                  推荐
                </span>
              )}
              <h3 className="text-lg font-semibold text-white mb-2">{plan.name}</h3>
              <p className="text-3xl font-bold text-amber-500">
                ¥{plan.price}
                <span className="text-sm text-gray-500 font-normal">/{plan.days}天</span>
              </p>
            </button>
          ))}
        </div>

        {/* 支付区域 */}
        {paymentStatus === "pending" && paymentSession ? (
          <div className="bg-[#1a1a2e] rounded-2xl p-6 text-center">
            <h2 className="text-lg font-semibold text-white mb-4">微信扫码支付</h2>
            <div className="inline-block bg-white p-4 rounded-xl mb-4">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(paymentSession.qrCodeUrl)}`}
                alt="支付二维码"
                className="w-48 h-48"
              />
            </div>
            <p className="text-gray-400 mb-4">请使用微信扫描二维码完成支付</p>
            <p className="text-sm text-gray-500">订单号: {paymentSession.orderNo}</p>
            {!paymentSession.testMode && (
              <p className="text-xs text-gray-600 mt-2">支付完成后将自动确认，请勿关闭页面</p>
            )}

            {showNativeTestConfirm && paymentSession.testMode && (
              <button
                type="button"
                onClick={handleConfirmTest}
                className="mt-4 px-6 py-2 bg-amber-500 text-amber-900 font-bold rounded-lg hover:bg-amber-400 transition-colors"
              >
                本地开发：模拟确认支付
              </button>
            )}
          </div>
        ) : (
          <div className="text-center">
            {user?.is_member ? (
              <div className="bg-[#1a1a2e] rounded-2xl p-6 mb-4">
                <p className="text-gray-300">
                  您已是会员，有效期至{" "}
                  <span className="text-amber-500">{user.member_expire_at}</span>
                </p>
              </div>
            ) : null}

            {error && <p className="text-red-400 mb-4">{error}</p>}

            <button
              onClick={handlePay}
              disabled={loading}
              className="px-8 py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 font-bold rounded-lg hover:from-amber-400 hover:to-amber-300 transition-all disabled:opacity-50"
            >
              {loading ? "处理中..." : `立即开通 ¥${PLANS.find((p) => p.id === selectedPlan)?.price}`}
            </button>

            {!token && (
              <p className="text-gray-500 text-sm mt-4">
                <a href="/auth/login?redirect=/membership" className="text-amber-500 hover:underline">
                  登录
                </a>
                后开通会员
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
