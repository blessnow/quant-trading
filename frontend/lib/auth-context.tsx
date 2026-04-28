"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface User {
  id: number;
  nickname: string;
  phone?: string;
  avatar_url?: string;
  is_member: boolean;
  is_admin: boolean;
  member_expire_at?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 从localStorage读取token
    const storedToken = localStorage.getItem("token");
    if (storedToken) {
      setToken(storedToken);
      fetchUser(storedToken);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUser = async (t: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_BACKEND_URL || "";
      const res = await fetch(`${apiBase}/api/wechat/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
        document.cookie = `is_member=${data.is_member ? "true" : "false"}; path=/; max-age=${60 * 60 * 24 * 365}`;
        document.cookie = `is_admin=${data.is_admin ? "true" : "false"}; path=/; max-age=${60 * 60 * 24 * 365}`;
      } else {
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
        document.cookie = "auth_token=; path=/; max-age=0";
      }
    } catch (e) {
      console.error("获取用户信息失败", e);
      localStorage.removeItem("token");
      setToken(null);
      setUser(null);
      document.cookie = "auth_token=; path=/; max-age=0";
    } finally {
      setLoading(false);
    }
  };

  const login = (newToken: string, newUser: User) => {
    localStorage.setItem("token", newToken);
    setToken(newToken);
    setUser(newUser);
    document.cookie = `auth_token=${newToken}; path=/; max-age=${60 * 60 * 24 * 365}`;
    document.cookie = `is_member=${newUser.is_member ? "true" : "false"}; path=/; max-age=${60 * 60 * 24 * 365}`;
    document.cookie = `is_admin=${newUser.is_admin ? "true" : "false"}; path=/; max-age=${60 * 60 * 24 * 365}`;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    document.cookie = "auth_token=; path=/; max-age=0";
    document.cookie = "is_member=; path=/; max-age=0";
    document.cookie = "is_admin=; path=/; max-age=0";
  };

  const refreshUser = async () => {
    if (token) {
      await fetchUser(token);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
