import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Quantify — AI-Powered Trading Platform",
  description:
    "Trade smarter with AI-driven intelligence. 6 production-grade strategies, ensemble machine learning predictions, and automated Telegram alerts.",
  keywords: ["quantitative trading", "AI trading", "backtesting", "algorithmic trading", "machine learning"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased min-h-screen bg-[#070b14]">
        <Navbar />
        <main className="min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
