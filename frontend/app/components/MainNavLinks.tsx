"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

const navItems = [
  { href: "/", label: "看板", requireLogin: false, requireAdmin: false },
  { href: "/strategies", label: "策略", requireLogin: true, requireAdmin: false },
  { href: "/trades", label: "交易", requireLogin: true, requireAdmin: false },
  { href: "/chat", label: "问财", requireLogin: true, requireAdmin: false },
  { href: "/monitor", label: "监控", requireLogin: false, requireAdmin: true },
  { href: "/settings/notifications", label: "设置", requireLogin: true, requireAdmin: false },
];

/**
 * 顶栏需登录入口必须用客户端状态判断：服务端 cookies() 在客户端登录写 cookie 后不会立刻重算，
 * router.refresh() 在部分部署下也不可靠；token/user 来自 AuthProvider，登录后立即更新。
 */
export function MainNavLinks() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const { user, token } = useAuth();
  const isLoggedIn = Boolean(token || user);
  const isAdmin = Boolean(user?.is_admin);

  if (!mounted) {
    return (
      <div className="flex gap-1">
        <Link href="/" className="nav-link">
          看板
        </Link>
      </div>
    );
  }

  return (
    <div className="flex gap-1">
      {navItems.map((item) => {
        if (item.requireAdmin && !isAdmin) {
          return null;
        }
        if (item.requireLogin && !isLoggedIn) {
          return null;
        }
        return (
          <Link key={item.href} href={item.href} className="nav-link">
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
