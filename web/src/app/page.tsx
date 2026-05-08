"use client";

import Link from "next/link";
import { ArrowRight, Terminal, BarChart2, Zap, Shield, Globe, Activity, ChevronRight } from "lucide-react";

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
    <div className="min-h-screen bg-black text-white font-sans selection:bg-blue-500/30">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 w-full z-[100] border-b border-white/5 bg-black/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center shadow-[0_0_15px_rgba(255,255,255,0.1)]">
              <span className="text-black font-black text-xs">QT</span>
            </div>
            <span className="font-bold text-lg tracking-tight">Quantify</span>
          </div>
          <div className="flex items-center gap-8">
            <Link href="/login" className="text-sm font-medium text-zinc-400 hover:text-white transition-colors">
              Log in
            </Link>
            <Link 
              href="/signup" 
              className="text-sm font-bold bg-white text-black px-5 py-2 rounded-full hover:bg-zinc-200 transition-all active:scale-95 shadow-[0_0_20px_rgba(255,255,255,0.1)]"
            >
              Sign Up
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero Section ── */}
      <section className="relative pt-40 md:pt-64 pb-20 md:pb-32 px-6 overflow-hidden">
        {/* Subtle decorative elements */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-full bg-[radial-gradient(circle_at_50%_-10%,rgba(59,130,246,0.2),transparent_60%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay" />

        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-zinc-400 text-xs font-semibold mb-10 animate-fade-in shadow-xl">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            Next-gen quantitative engine now live
          </div>

          <h1 className="text-6xl md:text-9xl font-black tracking-tight mb-8 leading-[0.9] bg-gradient-to-b from-white to-zinc-500 bg-clip-text text-transparent">
            Trade with
            <br />
            precision.
          </h1>

          <p className="text-lg md:text-2xl text-zinc-400 max-w-2xl mx-auto mb-12 leading-relaxed font-medium">
            The world&apos;s most advanced algorithmic trading infrastructure. Institutional-grade tools, democratized for everyone.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link 
              href="/signup" 
              className="group flex items-center gap-2 bg-white text-black font-bold px-8 py-4 rounded-full hover:bg-zinc-200 transition-all w-full sm:w-auto justify-center shadow-2xl"
            >
              Start Free Trial <ChevronRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <Link 
              href="/backtest" 
              className="flex items-center gap-2 bg-zinc-900 border border-white/10 text-white font-bold px-8 py-4 rounded-full hover:bg-zinc-800 transition-all w-full sm:w-auto justify-center"
            >
              View Backtests
            </Link>
          </div>
        </div>
      </section>

      {/* ── Mockup / Visual ── */}
      <section className="px-6 pb-48 relative">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />
        
        <div className="max-w-6xl mx-auto relative group">
          <div className="absolute -inset-px bg-gradient-to-r from-blue-500 to-purple-600 rounded-[2rem] opacity-20 group-hover:opacity-40 blur transition-opacity duration-1000" />
          <div className="relative rounded-[2rem] border border-white/10 bg-[#050505] p-3 shadow-2xl overflow-hidden">
            <div className="rounded-2xl border border-white/5 bg-zinc-900/50 aspect-video relative overflow-hidden">
               {/* Visual abstraction of a dashboard */}
               <div className="absolute inset-0 p-8 flex flex-col gap-8">
                 <div className="flex justify-between items-center border-b border-white/5 pb-6">
                   <div className="h-6 w-48 bg-white/10 rounded-full" />
                   <div className="flex gap-3">
                     <div className="h-2 w-2 rounded-full bg-red-500/50" />
                     <div className="h-2 w-2 rounded-full bg-yellow-500/50" />
                     <div className="h-2 w-2 rounded-full bg-green-500/50" />
                   </div>
                 </div>
                 <div className="grid grid-cols-4 gap-6">
                   {[1,2,3,4].map(i => (
                     <div key={i} className="h-24 rounded-2xl bg-white/[0.02] border border-white/5 animate-pulse" style={{ animationDelay: `${i * 100}ms` }} />
                   ))}
                 </div>
                 <div className="flex-1 rounded-2xl bg-gradient-to-br from-white/[0.02] to-transparent border border-white/5 relative overflow-hidden group/chart">
                    <svg viewBox="0 0 100 40" className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
                      <path d="M0,40 C20,35 40,38 60,15 S80,5 100,10" fill="none" stroke="url(#glow)" strokeWidth="1" className="animate-draw" />
                      <defs>
                        <linearGradient id="glow" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor="#3b82f6" />
                          <stop offset="100%" stopColor="#8b5cf6" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="absolute inset-0 bg-gradient-to-t from-blue-500/5 to-transparent" />
                 </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features Grid ── */}
      <section className="py-32 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl mb-24">
            <h2 className="text-4xl font-bold tracking-tight mb-6">
              Institutional power.
              <br />
              <span className="text-zinc-500">Retail simplicity.</span>
            </h2>
            <p className="text-zinc-400 text-lg leading-relaxed">
              We&apos;ve condensed millions of dollars in infrastructure into a single, cohesive trading platform.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-12">
            {FEATURES.map((f, i) => (
              <div key={i} className="group relative">
                <div className="mb-6 w-12 h-12 rounded-xl bg-zinc-900 border border-white/10 flex items-center justify-center group-hover:border-blue-500/50 transition-colors">
                  <f.icon size={20} className="text-white" />
                </div>
                <h3 className="text-xl font-bold mb-3">{f.title}</h3>
                <p className="text-zinc-400 text-sm leading-relaxed">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Section ── */}
      <section className="py-40 px-6 border-t border-white/5 relative">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.1),transparent_70%)]" />
        <div className="max-w-3xl mx-auto text-center relative z-10">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tight mb-8">
            Deploy your edge today.
          </h2>
          <p className="text-zinc-400 text-lg mb-12">
            Join thousands of traders using Quantify to navigate the markets.
          </p>
          <Link 
            href="/signup" 
            className="inline-flex items-center gap-2 bg-white text-black font-black px-10 py-5 rounded-full hover:bg-zinc-200 transition-all shadow-[0_0_30px_rgba(255,255,255,0.1)] active:scale-95"
          >
            Create Account <ArrowRight size={20} />
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="py-12 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-white rounded-md flex items-center justify-center">
              <span className="text-black font-black text-[10px]">QT</span>
            </div>
            <span className="font-bold text-sm tracking-tight">Quantify</span>
          </div>
          <div className="flex gap-8 text-sm text-zinc-500">
            <p>© 2026 Quantify Software</p>
            <p className="hidden md:block text-zinc-700">Not financial advice.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
