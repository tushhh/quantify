import type { Metadata } from "next";
import { Outfit, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Quantify — Premium ML Trading Platform",
  description:
    "Trade smarter with machine learning intelligence. 6 production-grade strategies, ensemble ML predictions, and automated Telegram alerts.",
  keywords: ["quantitative trading", "machine learning trading", "backtesting", "algorithmic trading", "ML analysis"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${outfit.variable} ${inter.variable} ${jetbrains.variable}`}>
      <body className="antialiased min-h-screen text-[var(--text)] bg-[var(--bg)] font-sans">
        <Navbar />
        <main className="min-h-screen relative z-10">
          {children}
        </main>
      </body>
    </html>
  );
}
