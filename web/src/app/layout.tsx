import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/sidebar";
import Topbar from "@/components/layout/topbar";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });
export const metadata: Metadata = {
  title: "Quantify | Institutional ML Trading",
  description:
    "Exclusive machine learning quantitative platform for elite trading execution.",
  keywords: ["wealth management", "quantitative trading", "institutional", "algorithmic trading"],
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable}`} data-theme="light">
      <body className="antialiased min-h-screen text-[var(--color-text-primary)] bg-[var(--color-bg)] selection:bg-[var(--color-accent)] selection:text-[var(--color-text-inverse)] overflow-hidden">
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
        <div className="flex h-screen bg-[var(--color-bg)] overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 overflow-auto">
            <Topbar />
            <main className="flex-1 p-6">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
