"use client";

import Link from "next/link";
import { TrendingUp, Zap, Shield, BarChart2, ArrowRight, Bot, LineChart, Brain, ChevronRight } from "lucide-react";

const FEATURES = [
  {
    icon: Brain,
    title: "AI-Powered Predictions",
    desc: "Ensemble ML models using CatBoost, XGBoost & LightGBM analyze 50+ features to find optimal entry points.",
    color: "from-blue-500 to-cyan-400",
  },
  {
    icon: BarChart2,
    title: "Professional Backtesting",
    desc: "Test 6 production-grade strategies with realistic transaction costs, slippage modeling, and benchmark comparison.",
    color: "from-violet-500 to-purple-400",
  },
  {
    icon: Shield,
    title: "Risk Management",
    desc: "Configurable stop-losses, position sizing (Equal Weight, Volatility Target, Half-Kelly), and sector exposure limits.",
    color: "from-emerald-500 to-teal-400",
  },
  {
    icon: Bot,
    title: "Telegram Alerts",
    desc: "Get real-time notifications when it's time to sell. Connect your Telegram to receive automated trade alerts 24/7.",
    color: "from-orange-500 to-amber-400",
  },
  {
    icon: LineChart,
    title: "6 Trading Strategies",
    desc: "Cross-sectional momentum, pairs mean reversion, trend following, quality value, volatility regime & ML predictor.",
    color: "from-rose-500 to-pink-400",
  },
  {
    icon: Zap,
    title: "One-Click Trading",
    desc: "Run AI analysis, pick the top stocks, and log your trades in seconds. Track everything from a single dashboard.",
    color: "from-indigo-500 to-blue-400",
  },
];

const STATS = [
  { label: "Strategies", value: "6" },
  { label: "ML Features", value: "50+" },
  { label: "Avg Sharpe", value: "1.2+" },
  { label: "Markets", value: "US Equities" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#070b14] text-white overflow-hidden">
      {/* ── Floating Nav ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 md:px-12 bg-[#070b14]/80 backdrop-blur-xl border-b border-white/5">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/25 group-hover:shadow-blue-500/40 transition-shadow">
            <TrendingUp size={18} className="text-white" />
          </span>
          <span className="font-bold tracking-tight text-lg">Quantify</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-slate-400 hover:text-white transition-colors px-4 py-2">
            Log in
          </Link>
          <Link href="/signup" className="text-sm font-semibold bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white px-5 py-2.5 rounded-xl transition-all hover:shadow-lg hover:shadow-blue-500/25 active:scale-95">
            Sign Up Free
          </Link>
        </div>
      </nav>

      {/* ── Hero Section ── */}
      <section className="relative pt-32 pb-20 md:pt-44 md:pb-32 px-6 md:px-12">
        {/* Background glow effects */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-blue-600/15 via-violet-600/10 to-transparent rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-40 left-1/4 w-[300px] h-[300px] bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-60 right-1/4 w-[250px] h-[250px] bg-violet-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 text-blue-400 text-xs font-medium mb-8 animate-fade-in">
            <Zap size={12} />
            Powered by Machine Learning
          </div>

          <h1 className="text-4xl md:text-6xl lg:text-7xl font-black leading-[1.1] tracking-tight animate-fade-in">
            Trade Smarter with{" "}
            <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">
              AI-Driven
            </span>{" "}
            Intelligence
          </h1>

          <p className="mt-6 text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed animate-fade-in">
            Quantify combines 6 production-grade trading strategies with ensemble machine learning to find the best trades in the US equity market — and tells you exactly when to buy and sell.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-10 animate-fade-in">
            <Link
              href="/signup"
              className="group flex items-center gap-2 bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white font-bold text-base px-8 py-4 rounded-2xl transition-all hover:shadow-2xl hover:shadow-blue-500/25 active:scale-95"
            >
              Get Started Free
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              href="/backtest"
              className="flex items-center gap-2 text-slate-400 hover:text-white font-medium text-base px-8 py-4 rounded-2xl border border-white/10 hover:border-white/20 hover:bg-white/5 transition-all"
            >
              <BarChart2 size={18} />
              Try Backtesting
            </Link>
          </div>
        </div>
      </section>

      {/* ── Stats Bar ── */}
      <section className="relative max-w-5xl mx-auto px-6 md:px-12 mb-20">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-6 rounded-2xl border border-white/5 bg-white/[0.02] backdrop-blur-sm">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-2xl md:text-3xl font-black text-white">{s.value}</p>
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features Grid ── */}
      <section className="relative max-w-6xl mx-auto px-6 md:px-12 pb-24">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-black">
            Everything You Need to{" "}
            <span className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
              Trade Professionally
            </span>
          </h2>
          <p className="mt-4 text-slate-400 max-w-xl mx-auto">
            From signal generation to risk management to automated alerts — Quantify handles the entire pipeline.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="group relative p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10 transition-all duration-300"
            >
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center shadow-lg mb-4 group-hover:scale-110 transition-transform`}>
                <f.icon size={22} className="text-white" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA Section ── */}
      <section className="relative max-w-4xl mx-auto px-6 md:px-12 pb-32">
        <div className="relative rounded-3xl border border-white/10 bg-gradient-to-b from-blue-600/10 to-violet-600/5 p-12 md:p-16 text-center overflow-hidden">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[400px] h-[200px] bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />
          <div className="relative">
            <h2 className="text-3xl md:text-4xl font-black mb-4">
              Ready to Start Trading?
            </h2>
            <p className="text-slate-400 max-w-md mx-auto mb-8">
              Create your free account in 30 seconds and let AI find the best trades for you.
            </p>
            <Link
              href="/signup"
              className="group inline-flex items-center gap-2 bg-white text-[#070b14] font-bold text-base px-8 py-4 rounded-2xl transition-all hover:shadow-2xl hover:shadow-white/10 active:scale-95"
            >
              Create Free Account
              <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 py-8 px-6 md:px-12">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-md bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
              <TrendingUp size={12} className="text-white" />
            </span>
            <span className="text-sm font-semibold text-slate-500">Quantify</span>
          </div>
          <p className="text-xs text-slate-600">
            Paper trading only. Not financial advice. Past performance does not guarantee future results.
          </p>
        </div>
      </footer>
    </div>
  );
}
