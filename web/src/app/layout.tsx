import type { Metadata } from "next";
import { Cormorant_Garamond, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const cormorant = Cormorant_Garamond({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-heading" });
const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Quantify | Institutional ML Trading",
  description:
    "Exclusive machine learning quantitative platform for elite trading execution.",
  keywords: ["wealth management", "quantitative trading", "institutional", "algorithmic trading"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${cormorant.variable} ${jakarta.variable}`}>
      <body className="antialiased min-h-screen text-[var(--text)] bg-[var(--bg)] font-sans selection:bg-[var(--accent)] selection:text-[#050505]">
        <Navbar />
        <main className="min-h-screen relative z-10 pt-24 pb-12">
          {children}
        </main>
      </body>
    </html>
  );
}
