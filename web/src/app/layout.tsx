import type { Metadata } from "next";
import { Chakra_Petch, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const chakra = Chakra_Petch({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-heading" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "QUANTIFY // SYS",
  description:
    "High-frequency machine learning trading terminal. Production-grade strategies, ensemble ML predictions.",
  keywords: ["quantitative trading", "terminal", "machine learning", "algorithmic trading", "cybernetic"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${chakra.variable} ${jetbrains.variable}`}>
      <body className="antialiased min-h-screen text-[var(--text)] bg-[var(--bg)] font-mono selection:bg-[var(--accent)] selection:text-black">
        <Navbar />
        <main className="min-h-screen relative z-10">
          {children}
        </main>
      </body>
    </html>
  );
}
