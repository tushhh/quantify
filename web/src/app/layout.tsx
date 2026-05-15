import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Quantify — ML-Powered Trading Platform",
  description:
    "Trade smarter with machine learning intelligence. 6 production-grade strategies, ensemble ML predictions, and automated Telegram alerts.",
  keywords: ["quantitative trading", "machine learning trading", "backtesting", "algorithmic trading", "ML analysis"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased min-h-screen" style={{ backgroundColor: "var(--bg)" }}>
        <Navbar />
        <main className="min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
