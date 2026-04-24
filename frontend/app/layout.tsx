import "./globals.css";
import Link from "next/link";
import { cookies } from "next/headers";

export const metadata = { title: "量化交易系统", description: "A股+美股高频量化交易系统" };

const navItems = [
  { href: "/", label: "看板" },
  { href: "/strategies", label: "策略", member: true },
  { href: "/trades", label: "交易", member: true },
  { href: "/backtest", label: "回测", member: true },
];

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const isMember = cookieStore.get("is_member")?.value === "true";

  return (
    <html lang="zh">
      <body>
        <nav className="border-b border-black/5 bg-white/90 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-8">
              <span className="font-bold text-lg">QuantTrader</span>
              <div className="flex gap-1">
                {navItems.map((item) => {
                  if (item.member && !isMember) return null;
                  return (
                    <Link key={item.href} href={item.href} className="px-3 py-1.5 rounded-lg text-sm hover:bg-black/5 transition-colors">
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isMember ? (
                <span className="text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 font-medium">会员</span>
              ) : (
                <form action={async () => {
                  "use server";
                  const { cookies } = await import("next/headers");
                  (await cookies()).set("is_member", "true", { path: "/", maxAge: 60 * 60 * 24 * 365 });
                }}>
                  <button type="submit" className="text-xs px-3 py-1 rounded-full bg-amber-500 text-white font-medium hover:bg-amber-600 transition-colors">
                    升级会员
                  </button>
                </form>
              )}
              <span className="text-xs text-gray-400">模拟盘</span>
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
