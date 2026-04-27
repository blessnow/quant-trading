"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";

const channels = [
  { id: "telegram", name: "Telegram", icon: "📱" },
  { id: "wechat", name: "微信企业号", icon: "💬" },
  { id: "email", name: "邮件", icon: "📧" },
];

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

export default function NotificationSettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [configs, setConfigs] = useState<Record<string, any>>({
    telegram: { bot_token: "", chat_id: "", enabled: false },
    wechat: { webhook_url: "", enabled: false },
    email: {
      smtp_server: "smtp.gmail.com",
      smtp_port: 587,
      smtp_user: "",
      smtp_password: "",
      to_email: "",
      enabled: false,
    },
  });
  const [saving, setSaving] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [loadingConfigs, setLoadingConfigs] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/auth/login");
    }
  }, [user, loading, router]);

  const showToast = (message: string, type: "success" | "error" | "info" = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  };

  useEffect(() => {
    if (!user) return;
    const loadConfigs = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch("/api/notifications/config", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          const loadedConfigs = { ...configs };
          for (const cfg of data.configs || []) {
            if (loadedConfigs[cfg.channel]) {
              loadedConfigs[cfg.channel] = {
                ...loadedConfigs[cfg.channel],
                ...cfg.config,
                enabled: cfg.is_enabled,
              };
            }
          }
          setConfigs(loadedConfigs);
        }
      } catch (e) {
        console.error("加载配置失败:", e);
      } finally {
        setLoadingConfigs(false);
      }
    };
    loadConfigs();
  }, [user]);

  const validateConfig = (channel: string, config: any): string | null => {
    if (channel === "telegram") {
      if (!config.bot_token || config.bot_token.length < 10) {
        return "请输入有效的 Bot Token";
      }
      if (!config.chat_id || !/^-?\d+$/.test(config.chat_id)) {
        return "请输入有效的 Chat ID（纯数字）";
      }
    }

    if (channel === "wechat") {
      if (!config.webhook_url || !config.webhook_url.startsWith("https://")) {
        return "请输入有效的 Webhook URL（以 https:// 开头）";
      }
    }

    if (channel === "email") {
      if (!config.smtp_server) {
        return "请输入 SMTP 服务器";
      }
      if (!config.to_email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.to_email)) {
        return "请输入有效的邮箱地址";
      }
    }

    return null;
  };

  const handleSave = async (channel: string) => {
    const config = configs[channel];
    const error = validateConfig(channel, config);
    if (error) {
      showToast(error, "error");
      return;
    }

    setSaving(channel);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/notifications/config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          channel,
          config,
          is_enabled: config.enabled,
        }),
      });
      if (res.ok) {
        showToast(`${channel} 配置已保存`, "success");
      } else {
        const data = await res.json();
        showToast(data.detail || "保存失败", "error");
      }
    } catch (e) {
      showToast("保存失败: " + e, "error");
    } finally {
      setSaving(null);
    }
  };

  const handleTest = async (channel: string) => {
    setTesting(channel);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/notifications/test/${channel}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (data.status === "ok") {
        showToast(`${channel} 测试成功！`, "success");
      } else {
        showToast(`${channel} 测试失败`, "error");
      }
    } catch (e) {
      showToast("测试失败: " + e, "error");
    } finally {
      setTesting(null);
    }
  };

  if (loading || loadingConfigs) {
    return <div className="text-white/50 p-6">加载中...</div>;
  }

  if (!user) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="text-lg font-semibold text-white mb-2">请先登录</div>
        <div className="text-sm text-white/50">通知设置需要登录后才能使用</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">通知设置</h1>

      {channels.map((channel) => (
        <div key={channel.id} className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{channel.icon}</span>
              <h2 className="text-lg font-semibold text-white">{channel.name}</h2>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={configs[channel.id]?.enabled || false}
                onChange={(e) =>
                  setConfigs({
                    ...configs,
                    [channel.id]: { ...configs[channel.id], enabled: e.target.checked },
                  })
                }
                className="w-4 h-4 rounded border-white/20 bg-white/10"
              />
              <span className="text-sm text-white/60">启用</span>
            </label>
          </div>

          {channel.id === "telegram" && (
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Bot Token"
                value={configs.telegram?.bot_token || ""}
                onChange={(e) =>
                  setConfigs({
                    ...configs,
                    telegram: { ...configs.telegram, bot_token: e.target.value },
                  })
                }
                className="dark-input w-full"
              />
              <input
                type="text"
                placeholder="Chat ID（纯数字）"
                value={configs.telegram?.chat_id || ""}
                onChange={(e) =>
                  setConfigs({
                    ...configs,
                    telegram: { ...configs.telegram, chat_id: e.target.value },
                  })
                }
                className="dark-input w-full"
              />
            </div>
          )}

          {channel.id === "wechat" && (
            <input
              type="text"
              placeholder="企业微信 Webhook URL（以 https:// 开头）"
              value={configs.wechat?.webhook_url || ""}
              onChange={(e) =>
                setConfigs({
                  ...configs,
                  wechat: { ...configs.wechat, webhook_url: e.target.value },
                })
              }
              className="dark-input w-full"
            />
          )}

          {channel.id === "email" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="SMTP 服务器"
                  value={configs.email?.smtp_server || ""}
                  onChange={(e) =>
                    setConfigs({
                      ...configs,
                      email: { ...configs.email, smtp_server: e.target.value },
                    })
                  }
                  className="dark-input"
                />
                <input
                  type="number"
                  placeholder="端口"
                  value={configs.email?.smtp_port || 587}
                  onChange={(e) =>
                    setConfigs({
                      ...configs,
                      email: { ...configs.email, smtp_port: parseInt(e.target.value) },
                    })
                  }
                  className="dark-input"
                />
              </div>
              <input
                type="text"
                placeholder="SMTP 用户名"
                value={configs.email?.smtp_user || ""}
                onChange={(e) =>
                  setConfigs({
                    ...configs,
                    email: { ...configs.email, smtp_user: e.target.value },
                  })
                }
                className="dark-input w-full"
              />
              <input
                type="password"
                placeholder="SMTP 密码"
                value={configs.email?.smtp_password || ""}
                onChange={(e) =>
                  setConfigs({
                    ...configs,
                    email: { ...configs.email, smtp_password: e.target.value },
                  })
                }
                className="dark-input w-full"
              />
              <input
                type="email"
                placeholder="收件人邮箱"
                value={configs.email?.to_email || ""}
                onChange={(e) =>
                  setConfigs({
                    ...configs,
                    email: { ...configs.email, to_email: e.target.value },
                  })
                }
                className="dark-input w-full"
              />
            </div>
          )}

          <div className="flex gap-3 mt-4">
            <button
              onClick={() => handleSave(channel.id)}
              disabled={saving === channel.id}
              className="btn-primary"
            >
              {saving === channel.id ? "保存中..." : "保存"}
            </button>
            <button
              onClick={() => handleTest(channel.id)}
              disabled={testing === channel.id}
              className="btn-secondary"
            >
              {testing === channel.id ? "测试中..." : "测试"}
            </button>
          </div>
        </div>
      ))}

      {/* Toast 容器 */}
      <div className="fixed bottom-4 right-4 space-y-2 z-50">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`px-4 py-3 rounded-lg shadow-lg backdrop-blur-xl ${
              toast.type === "success"
                ? "bg-green-500/20 border border-green-500/30 text-green-400"
                : toast.type === "error"
                ? "bg-red-500/20 border border-red-500/30 text-red-400"
                : "bg-white/10 border border-white/20 text-white"
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
}