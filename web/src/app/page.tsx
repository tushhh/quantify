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
    title: "Modern home surface",
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
    <div className="min-h-screen pt-12 sm:pt-16 pb-12 sm:pb-16 md:pb-10 animate-fade-in text-[var(--color-text-primary)] selection:bg-[var(--color-accent)]/20 relative">

      <main className="pt-0 pb-0">
        <section className="max-w-7xl mx-auto px-4 sm:px-6 grid lg:grid-cols-2 gap-8 lg:gap-10 items-center">
          <div className="space-y-6 animate-fade-in-up">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 text-xs text-[var(--color-accent)]">
              <span className="w-2 h-2 rounded-full bg-[var(--color-accent)] animate-pulse" />
              Modern trading platform, rebuilt
            </div>

            <div className="space-y-4">
              <h1 className="text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold leading-tight tracking-tight">
                Faster research.
                <span className="block text-[var(--color-accent)]">
                  Cleaner execution.
                </span>
              </h1>
              <p className="max-w-xl text-[var(--color-text-muted)] text-lg md:text-xl leading-relaxed mt-2">
                Quantify combines portfolio tracking, Telegram automation, strategy research, and backtesting in a sharper interface with working controls, clearer feedback, and a simplified backtest flow.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/backtest" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full bg-[var(--color-accent)] text-[var(--color-text-inverse)] font-semibold shadow-sm hover:bg-[var(--color-accent-hover)] transition-colors">
                Open Backtest Lab <ChevronRight size={18} />
              </Link>
              <Link href="/dashboard" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full border border-[var(--color-border)] text-[var(--color-text-secondary)] font-semibold hover:bg-[var(--color-surface-raised)] transition-colors">
                View Portfolio Tools
              </Link>
            </div>

            <div className="pt-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 border border-[var(--color-border)] rounded-2xl p-1 bg-[var(--color-surface-raised)]/80">
                {METRICS.map((item, i) => (
                  <div 
                    key={item.label} 
                    className={`text-center px-3 py-4 sm:px-4 stat-card animate-fade-in-up ${i < METRICS.length - 1 ? 'sm:border-r border-[var(--color-border)]' : ''}`}
                    style={{ animationDelay: `${300 + i * 60}ms` }}
                  >
                    <div className="stat-value text-[var(--color-text-primary)] text-lg sm:text-xl font-semibold">{item.value}</div>
                    <div className="stat-label mt-1 text-[var(--color-text-muted)] text-[11px] sm:text-xs">{item.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="relative animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
            <div className="relative bg-[var(--color-surface)]/90 rounded-[28px] p-4 sm:p-6 md:p-8 border border-[var(--color-border)] shadow-xl overflow-hidden">
              <div className="flex items-center justify-between mb-4 text-xs text-[var(--color-text-muted)]">
                <span>System overview</span>
                <span className="text-[var(--color-success)]">Live + Paper ready</span>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 p-5 min-h-36">
                <div className="text-xs text-[var(--color-text-muted)]">Active modules</div>
                <div className="mt-3 space-y-2">
                  {FEATURES.slice(0, 3).map((feature) => (
                    <div key={feature.title} className="flex items-center gap-3 text-sm text-[var(--color-text-secondary)]">
                      <feature.icon size={16} className="text-[var(--color-accent)]" />
                      <span>{feature.title}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 p-5 min-h-36 flex flex-col justify-between">
                <div>
                  <div className="text-xs text-[var(--color-text-muted)]">Backtest mode</div>
                  <div className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Simple by default</div>
                  <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                    Advanced controls stay collapsed until users intentionally open them.
                  </p>
                </div>
                <div className="mt-4 h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                  <div className="h-full w-[68%] bg-[var(--color-accent)] rounded-full" />
                </div>
              </div>

              <div className="sm:col-span-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <div className="text-xs text-[var(--color-text-muted)]">Automation</div>
                    <div className="text-lg font-semibold text-[var(--color-text-primary)]">Portfolio alerts + Telegram</div>
                  </div>
                  <div className="px-3 py-1 rounded-full text-xs bg-[var(--color-success)]/10 text-[var(--color-success)] border border-[var(--color-success)]/20">
                    Working
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    "Trade logging",
                    "Hold reminders",
                    "Telegram sync",
                  ].map((item) => (
                    <div key={item} className="rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] p-3 text-xs text-[var(--color-text-secondary)]">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            </div>
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-4 md:px-6 mt-16 md:mt-24">
            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 md:gap-6 mb-8">
            <div>
            <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-accent)]">What changed</p>
            <h2 className="text-3xl md:text-4xl font-bold mt-2 text-[var(--color-text-primary)]">A sharper interface for the parts that already work.</h2>
          </div>
          <p className="hidden md:block max-w-xl text-sm text-[var(--color-text-muted)]">
              The platform now leans into the workflows that matter: portfolio customization, backtesting, and automated alerts.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
            {FEATURES.map((feature, index) => (
              <div key={feature.title} className="border border-[var(--color-border)] bg-[var(--color-surface)]/90 rounded-2xl p-5 hover-lift animate-fade-in-up cursor-pointer" style={{ animationDelay: `${index * 60}ms` }}>
                <div className="w-11 h-11 rounded-xl gradient-accent flex items-center justify-center mb-4">
                  <feature.icon size={20} className="text-[var(--color-text-inverse)]" />
                </div>
                <h3 className="text-lg font-semibold mb-2 text-[var(--color-text-primary)]">{feature.title}</h3>
                <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-4 md:px-6 mt-16 md:mt-24">
          <div className="bg-[var(--color-surface)]/90 rounded-[32px] p-8 md:p-12 border border-[var(--color-border)] flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8 ">
            <div className="max-w-2xl relative z-10">
              <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-accent)]">Next step</p>
              <h2 className="text-3xl md:text-5xl font-black mt-3 leading-tight text-[var(--color-text-primary)]">
                Start from the homepage, then go straight into backtests or portfolio tools.
              </h2>
              <p className="mt-4 text-[var(--color-text-muted)] text-base md:text-lg leading-relaxed">
                The landing page now reflects the new visual direction, and the backtest page exposes advanced controls only when requested.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto relative z-10">
              <Link href="/signup" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-[var(--color-accent)] text-[var(--color-text-inverse)] font-semibold hover-lift w-full sm:w-auto">
                Create account <ArrowRight size={18} />
              </Link>
              <Link href="/login" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] font-semibold hover:bg-[var(--color-surface-raised)] transition-colors w-full sm:w-auto">
                Log in
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
