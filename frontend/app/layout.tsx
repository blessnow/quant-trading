import "./globals.css";
import Link from "next/link";
import { AuthProvider } from "@/lib/auth-context";
import { UserNav } from "@/app/components/UserNav";

export const metadata = { title: "QuantTrader", description: "A股+美股高频量化交易系统" };

const navItems = [
  { href: "/", label: "看板", icon: "■" },
  { href: "/strategies", label: "策略", icon: "⚡" },
  { href: "/trades", label: "交易", icon: "☰" },
  { href: "/chat", label: "问财", icon: "💬" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <AuthProvider>
          <nav className="bg-[#1a1a2e] text-white sticky top-0 z-50 shadow-lg">
            <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
              <div className="flex items-center gap-8">
                <span className="font-bold text-lg tracking-tight">QuantTrader</span>
                <div className="flex gap-1">
                  {navItems.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="px-3 py-1.5 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <UserNav />
                <span className="text-xs text-white/40">模拟盘</span>
              </div>
            </div>
          </nav>
          <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
