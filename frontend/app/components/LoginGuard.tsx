"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

interface LoginGuardProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export function LoginGuard({ children, requireAdmin = false }: LoginGuardProps) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/auth/login");
    } else if (!loading && requireAdmin && user && !user.is_admin) {
      router.push("/");
    }
  }, [user, loading, router, requireAdmin]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-white/50">加载中...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-white/50">请先登录...</div>
      </div>
    );
  }

  if (requireAdmin && !user.is_admin) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-white/50">无权限访问此页面</div>
      </div>
    );
  }

  return <>{children}</>;
}
