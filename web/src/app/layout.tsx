import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/sidebar";
import Topbar from "@/components/layout/topbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-mono" });
export const metadata: Metadata = {
  title: "Quantify | Monthly trend picks with a public record",
  description:
    "Fifteen S&P 500 trend picks a month, each with a next-month forecast, backtested since 2017 and scored against SPY.",
  keywords: ["stock picks", "momentum", "backtest", "quantitative trading"],
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The inline script below sets data-theme from storage before hydration, on purpose.
    <html lang="en" className={`${inter.variable} ${plexMono.variable}`} data-theme="dark" suppressHydrationWarning>
      <body className="antialiased min-h-screen text-[var(--color-text-primary)] bg-[var(--color-bg)] selection:bg-[var(--color-accent)] selection:text-[var(--color-text-inverse)] overflow-x-hidden">
        <script
          dangerouslySetInnerHTML={{
            __html: `(() => {
              try {
                const stored = localStorage.getItem('theme');
                if (stored) document.documentElement.setAttribute('data-theme', stored);
              } catch (e) {
                // ignore
              }
            })();`,
          }}
        />
        <div className="flex min-h-screen bg-[var(--color-bg)] overflow-x-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 overflow-x-hidden">
            <Topbar />
            <main className="flex-1 px-4 py-6 sm:px-8 sm:py-8">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
