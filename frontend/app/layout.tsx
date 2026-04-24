import "./globals.css";
import Link from "next/link";
import { cookies } from "next/headers";

export const metadata = { title: "QuantTrader", description: "A股+美股高频量化交易系统" };

const navItems = [
  { href: "/", label: "看板", icon: "■" },
  { href: "/strategies", label: "策略", icon: "⚡" },
  { href: "/trades", label: "交易", icon: "☰" },
];

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const isMember = cookieStore.get("is_member")?.value === "true";

  return (
    <html lang="zh">
      <body>
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
              {isMember ? (
                <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 font-medium">Q 会员</span>
              ) : (
                <form action={async () => {
                  "use server";
                  const { cookies } = await import("next/headers");
                  (await cookies()).set("is_member", "true", { path: "/", maxAge: 60 * 60 * 24 * 365 });
                }}>
                  <button type="submit" className="text-xs px-3 py-1 rounded-full bg-gradient-to-r from-amber-500 to-amber-400 text-amber-900 font-bold hover:from-amber-400 hover:to-amber-300 transition-all">
                    升级会员
                  </button>
                </form>
              )}
              <span className="text-xs text-white/40">模拟盘</span>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
