import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { UserNav } from "@/app/components/UserNav";
import { MainNavLinks } from "@/app/components/MainNavLinks";

export const metadata = { title: "QuantTrader", description: "A股+美股高频量化交易系统" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <AuthProvider>
          <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[rgba(10,15,26,0.8)] border-b border-white/10">
            <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <span className="text-white font-bold text-sm">Q</span>
                  </div>
                  <span className="font-bold text-lg text-white tracking-tight">QuantTrader</span>
                </div>
                <MainNavLinks />
              </div>
              <div className="flex items-center gap-4">
                <UserNav />
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
                  <div className="status-dot active" />
                  <span className="text-xs text-white/60">模拟盘运行</span>
                </div>
              </div>
            </div>
          </nav>
          <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
