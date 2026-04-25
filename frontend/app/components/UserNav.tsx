"use client";

import { useAuth } from "@/lib/auth-context";
import Link from "next/link";

export function UserNav() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <span className="text-xs text-gray-400">加载中...</span>;
  }

  if (user) {
    return (
      <div className="flex items-center gap-3">
        {user.is_member ? (
          <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 font-medium">
            Q 会员
          </span>
        ) : (
          <Link
            href="/membership"
            className="text-xs px-3 py-1 rounded-full bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 font-bold hover:from-amber-400 hover:to-amber-300 transition-all"
          >
            升级会员
          </Link>
        )}
        <span className="text-sm text-gray-300">{user.nickname}</span>
        <button
          onClick={logout}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          登出
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <Link
        href="/auth/login"
        className="text-xs px-3 py-1 rounded-full border border-gray-600 text-gray-300 hover:border-amber-500 hover:text-amber-500 transition-colors"
      >
        登录
      </Link>
      <Link
        href="/membership"
        className="text-xs px-3 py-1 rounded-full bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 font-bold hover:from-amber-400 hover:to-amber-300 transition-all"
      >
        升级会员
      </Link>
    </div>
  );
}
