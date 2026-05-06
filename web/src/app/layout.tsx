import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Quantify — Quantitative Trading Platform",
  description:
    "A modular quantitative trading system with 6 production-ready strategies, realistic backtesting, and risk management — now accessible from any device.",
  keywords: ["quantitative trading", "backtesting", "algorithmic trading", "momentum", "pairs trading"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased min-h-screen bg-[#070b14]">
        <Navbar />
        {/* Page offset for nav bars */}
        <main className="pt-14 pb-20 md:pb-4 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
