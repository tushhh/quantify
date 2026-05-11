"use client";

import Link from "next/link";
import { ArrowRight, Activity, BrainCircuit, Bot, ChartCandlestick, ChevronRight, Radar, ShieldCheck, Sparkles } from "lucide-react";

const FEATURES = [
  {
    icon: ChartCandlestick,
    title: "Backtest without clutter",
    desc: "A fast, simplified simulation flow with advanced strategy controls hidden until you need them.",
  },
  {
    icon: BrainCircuit,
    title: "Strategy engine",
    desc: "Momentum, mean reversion, quality/value, and ML-return models wired into a single execution path.",
  },
  {
    icon: ShieldCheck,
    title: "Risk first",
    desc: "Portfolio drawdown, leverage, position sizing, and stop logic stay visible and configurable.",
  },
  {
    icon: Bot,
    title: "Telegram automation",
    desc: "The live notifications pipeline keeps working while the rest of the platform evolves.",
  },
  {
    icon: Activity,
    title: "Portfolio customization",
    desc: "Track holdings, holdings periods, and user-specific trade settings in one place.",
  },
  {
    icon: Radar,
    title: "Modern dashboard surface",
    desc: "A bold visual system built around glass panels, gradients, and clear feedback states.",
  },
];

const METRICS = [
  { label: "Strategies", value: "6" },
  { label: "Risk presets", value: "3" },
  { label: "Telegram bot", value: "Live" },
  { label: "Backtest mode", value: "Simplified" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen text-white selection:bg-cyan-400/30 relative">
      <div className="mesh-animated -z-10" />

      <main className="pt-24 md:pt-28 pb-20">
        <section className="max-w-7xl mx-auto px-4 md:px-6 grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-7 animate-fade-in-up">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass text-xs text-cyan-200 border-cyan-500/20">
              <span className="w-2 h-2 rounded-full bg-[var(--color-accent)] animate-pulse" />
              Modern trading platform, rebuilt
            </div>

            <div className="space-y-4">
              <h1 className="text-5xl md:text-7xl font-black leading-[0.92] tracking-tight">
                Faster research.
                <span className="block bg-gradient-to-r from-cyan-300 via-white to-violet-300 bg-clip-text text-transparent">
                  Cleaner execution.
                </span>
              </h1>
              <p className="max-w-xl text-slate-300 text-lg md:text-xl leading-relaxed">
                Quantify combines portfolio tracking, Telegram automation, strategy research, and backtesting in a sharper interface with working controls, clearer feedback, and a simplified backtest flow.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/backtest" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full bg-[var(--color-accent)] text-[#02121a] font-semibold shadow-lg hover:shadow-[0_12px_40px_rgba(0,212,255,0.12)]">
                Open Backtest Lab <ChevronRight size={18} />
              </Link>
              <Link href="/dashboard" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full border border-[var(--color-accent)] text-[var(--color-accent)] font-semibold hover:bg-[var(--color-accent)] hover:text-[#02121a]">
                View Portfolio Tools
              </Link>
            </div>

            <div className="pt-6">
              <div className="glass rounded-2xl p-1 stats-row">
                {METRICS.map((item, i) => (
                  <div key={item.label} className={`stat-card ${i < METRICS.length - 1 ? 'border-r border-white/6' : ''}`}>
                    <div className="stat-value">{item.value}</div>
                    <div className="stat-label mt-1">{item.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="relative animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
            <div className="absolute -inset-6 bg-gradient-to-br from-cyan-500/20 via-transparent to-violet-500/20 blur-3xl" />
            <div className="relative glass-dark rounded-[28px] p-4 md:p-6 border-white/10 shadow-2xl overflow-hidden">
              <div className="flex items-center justify-between mb-4 text-xs text-slate-400">
                <span>System overview</span>
                <span className="text-emerald-300">Live + Paper ready</span>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="rounded-2xl glass p-4 min-h-36">
                  <div className="text-xs text-slate-400">Active modules</div>
                  <div className="mt-3 space-y-2">
                    {FEATURES.slice(0, 3).map((feature) => (
                      <div key={feature.title} className="flex items-center gap-3 text-sm text-slate-200">
                        <feature.icon size={16} className="text-cyan-300" />
                        <span>{feature.title}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl glass p-4 min-h-36 flex flex-col justify-between">
                  <div>
                    <div className="text-xs text-slate-400">Backtest mode</div>
                    <div className="mt-2 text-xl font-semibold">Simple by default</div>
                    <p className="mt-2 text-sm text-slate-400">
                      Advanced controls stay collapsed until users intentionally open them.
                    </p>
                  </div>
                  <div className="mt-4 h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div className="h-full w-[68%] gradient-accent rounded-full" />
                  </div>
                </div>

                <div className="sm:col-span-2 rounded-2xl glass p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="text-xs text-slate-400">Automation</div>
                      <div className="text-lg font-semibold">Portfolio alerts + Telegram</div>
                    </div>
                    <div className="px-3 py-1 rounded-full text-xs bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                      Working
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      "Trade logging",
                      "Hold reminders",
                      "Telegram sync",
                    ].map((item) => (
                      <div key={item} className="rounded-xl bg-white/5 border border-white/5 p-3 text-xs text-slate-300">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-4 md:px-6 mt-20 md:mt-28">
          <div className="flex items-end justify-between gap-6 mb-8">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-cyan-300">What changed</p>
              <h2 className="text-3xl md:text-4xl font-bold mt-2">A sharper interface for the parts that already work.</h2>
            </div>
            <p className="hidden md:block max-w-xl text-sm text-slate-400">
              The platform now leans into the workflows that matter: portfolio customization, backtesting, and automated alerts.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
            {FEATURES.map((feature, index) => (
              <div key={feature.title} className="glass rounded-2xl p-5 hover-lift animate-fade-in-up" style={{ animationDelay: `${index * 70}ms` }}>
                <div className="w-11 h-11 rounded-xl gradient-accent flex items-center justify-center mb-4">
                  <feature.icon size={20} className="text-white" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-4 md:px-6 mt-20 md:mt-28">
          <div className="glass-dark rounded-[32px] p-8 md:p-12 border-white/10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8 cta-glow">
            <div className="max-w-2xl">
              <p className="text-xs uppercase tracking-[0.22em] text-violet-300">Next step</p>
              <h2 className="text-3xl md:text-5xl font-black mt-3 leading-tight">
                Start from the homepage, then go straight into backtests or portfolio tools.
              </h2>
              <p className="mt-4 text-slate-300 text-base md:text-lg leading-relaxed">
                The landing page now reflects the new visual direction, and the backtest page exposes advanced controls only when requested.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto">
              <Link href="/signup" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl gradient-accent font-semibold hover-lift">
                Create account <ArrowRight size={18} />
              </Link>
              <Link href="/login" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl glass font-semibold hover:border-cyan-500/30">
                Log in
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
