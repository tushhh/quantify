"use client";

import Link from "next/link";
import { ArrowRight, Terminal, BarChart2, Zap, Shield, Globe, Activity } from "lucide-react";

const FEATURES = [
  {
    icon: Terminal,
    title: "Algorithmic Precision",
    desc: "Deploy cross-sectional momentum, mean reversion, and statistical arbitrage strategies with a single click.",
  },
  {
    icon: Activity,
    title: "Ensemble ML Models",
    desc: "Predict asset returns using CatBoost, LightGBM, and XGBoost models trained on 50+ alpha factors.",
  },
  {
    icon: Shield,
    title: "Dynamic Risk Control",
    desc: "Automatically manage drawdowns with volatility-targeted position sizing and sector-neutral constraints.",
  },
  {
    icon: BarChart2,
    title: "Institutional Backtesting",
    desc: "Simulate years of market data in seconds, factoring in bid-ask spreads, slippage, and commission drag.",
  },
  {
    icon: Globe,
    title: "Live Market Execution",
    desc: "Transition seamlessly from paper trading to live execution via Alpaca with zero code changes.",
  },
  {
    icon: Zap,
    title: "Instant Telegram Alerts",
    desc: "Never miss an exit. Receive automated buy and sell signals directly to your mobile device 24/7.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-[#EDEDED] font-sans selection:bg-white/20">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/[0.08] bg-black/50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
              <span className="text-black font-bold text-[10px]">QT</span>
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">Quantify</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/login" className="text-sm font-medium text-[#A1A1AA] hover:text-white transition-colors">
              Log in
            </Link>
            <Link 
              href="/signup" 
              className="text-sm font-medium bg-white text-black px-4 py-1.5 rounded-full hover:bg-[#E5E5E5] transition-colors"
            >
              Start Trading
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero Section ── */}
      <main className="pt-40 pb-24 px-6 relative overflow-hidden">
        {/* Subtle grid background */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none" />
        
        {/* Glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-white/[0.03] rounded-full blur-[100px] pointer-events-none" />

        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/[0.02] text-[#A1A1AA] text-xs font-medium mb-8">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            v1.0 is now live in production
          </div>

          <h1 className="text-5xl md:text-7xl font-medium tracking-tighter text-white mb-6">
            Quantitative trading,
            <br />
            <span className="text-[#A1A1AA]">democratized.</span>
          </h1>

          <p className="text-lg text-[#A1A1AA] max-w-2xl mx-auto mb-10 leading-relaxed font-light">
            An institutional-grade trading platform built for retail investors. Deploy machine learning models, backtest strategies, and automate your portfolio execution in seconds.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link 
              href="/signup" 
              className="flex items-center gap-2 bg-white text-black font-medium px-6 py-3 rounded-full hover:bg-[#E5E5E5] transition-colors w-full sm:w-auto justify-center"
            >
              Start Free Trial <ArrowRight size={16} />
            </Link>
            <Link 
              href="/backtest" 
              className="flex items-center gap-2 bg-white/[0.03] border border-white/10 text-white font-medium px-6 py-3 rounded-full hover:bg-white/[0.08] transition-colors w-full sm:w-auto justify-center"
            >
              Run Backtest
            </Link>
          </div>
        </div>

        {/* ── Mockup / Visual ── */}
        <div className="max-w-6xl mx-auto mt-24 relative z-10">
          <div className="rounded-xl border border-white/10 bg-black/50 backdrop-blur-xl shadow-2xl p-2 overflow-hidden ring-1 ring-white/5">
            <div className="rounded-lg border border-white/10 bg-[#0A0A0A] w-full aspect-[16/9] flex items-center justify-center relative overflow-hidden">
              {/* Fake Dashboard UI */}
              <div className="absolute inset-0 p-6 flex flex-col gap-4 opacity-50">
                <div className="h-8 w-48 rounded bg-white/5" />
                <div className="flex gap-4">
                  <div className="h-32 w-1/4 rounded-xl border border-white/5 bg-white/[0.02]" />
                  <div className="h-32 w-1/4 rounded-xl border border-white/5 bg-white/[0.02]" />
                  <div className="h-32 w-1/4 rounded-xl border border-white/5 bg-white/[0.02]" />
                  <div className="h-32 w-1/4 rounded-xl border border-white/5 bg-white/[0.02]" />
                </div>
                <div className="flex-1 rounded-xl border border-white/5 bg-[linear-gradient(to_bottom,transparent_0%,rgba(255,255,255,0.02)_100%)] flex items-end p-4">
                   {/* Fake chart lines */}
                   <svg viewBox="0 0 100 20" className="w-full h-full preserve-3d" preserveAspectRatio="none">
                     <path d="M0,20 L10,15 L20,18 L30,10 L40,12 L50,5 L60,8 L70,2 L80,6 L90,1 L100,5" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.5" />
                     <path d="M0,20 L10,18 L20,19 L30,15 L40,16 L50,12 L60,14 L70,10 L80,11 L90,7 L100,8" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
                   </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ── Features ── */}
      <section className="py-32 px-6 border-t border-white/[0.08] bg-[#0A0A0A]">
        <div className="max-w-7xl mx-auto">
          <div className="mb-16">
            <h2 className="text-3xl font-medium tracking-tight text-white mb-4">
              Everything you need to automate.
            </h2>
            <p className="text-[#A1A1AA] max-w-xl">
              We abstracted away the complex infrastructure so you can focus on building and deploying winning strategies.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-12">
            {FEATURES.map((f, i) => (
              <div key={i} className="flex flex-col gap-4">
                <div className="w-10 h-10 rounded-lg border border-white/10 bg-white/[0.03] flex items-center justify-center">
                  <f.icon size={18} className="text-[#A1A1AA]" />
                </div>
                <h3 className="text-lg font-medium text-white">{f.title}</h3>
                <p className="text-sm text-[#A1A1AA] leading-relaxed font-light">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-32 px-6 border-t border-white/[0.08] relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-white/[0.02] rounded-full blur-[120px] pointer-events-none" />
        
        <div className="max-w-2xl mx-auto text-center relative z-10">
          <h2 className="text-4xl font-medium tracking-tight text-white mb-6">
            Ready to deploy your edge?
          </h2>
          <p className="text-[#A1A1AA] mb-10 font-light">
            Join the quantitative revolution. Paper trade today, go live tomorrow.
          </p>
          <Link 
            href="/signup" 
            className="inline-flex items-center gap-2 bg-white text-black font-medium px-8 py-4 rounded-full hover:bg-[#E5E5E5] transition-colors"
          >
            Create your account
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="py-8 px-6 border-t border-white/[0.08] text-center md:text-left flex flex-col md:flex-row justify-between items-center max-w-7xl mx-auto">
        <p className="text-[#A1A1AA] text-sm mb-4 md:mb-0">
          © 2026 Quantify Software. All rights reserved.
        </p>
        <p className="text-[#52525B] text-xs">
          Not financial advice. Execution is simulated.
        </p>
      </footer>
    </div>
  );
}
