"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Activity, BrainCircuit, Bot, ChartCandlestick, ChevronRight, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/lib/api";

const FEATURES = [
  {
    icon: BrainCircuit,
    title: "ML ensemble predictions",
    desc: "LightGBM, XGBoost and CatBoost vote on each stock's next move. Each pick shows its direction, confidence and the drivers behind it.",
  },
  {
    icon: ChartCandlestick,
    title: "Backtest before you trade",
    desc: "Run the same strategies through an event-driven backtest with trading costs. Advanced controls stay collapsed until you need them.",
  },
  {
    icon: Activity,
    title: "Six strategies, one engine",
    desc: "Momentum, mean reversion, quality/value and the ML return model share one execution path, so backtests match how signals are made.",
  },
  {
    icon: ShieldCheck,
    title: "Risk limits built in",
    desc: "Drawdown limits, sector caps, leverage and position sizing apply to every run, with presets for conservative to aggressive.",
  },
  {
    icon: Bot,
    title: "Telegram alerts",
    desc: "Link your Telegram username to get prediction and portfolio alerts without keeping the app open.",
  },
];

const METRICS = [
  { label: "Strategies", value: "6" },
  { label: "Models in the ensemble", value: "3" },
  { label: "Risk presets", value: "3" },
  { label: "Model retraining", value: "Daily" },
];

const ENSEMBLE = ["LightGBM", "XGBoost", "CatBoost"];

type ApiStatus = "checking" | "online" | "offline";

/** Live API status from /health, so the page never claims "live" during an outage. */
function ApiStatusPill() {
  const [status, setStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    let active = true;
    api.health()
      .then((res) => { if (active) setStatus(res?.status === "ok" ? "online" : "offline"); })
      .catch(() => { if (active) setStatus("offline"); });
    return () => { active = false; };
  }, []);

  if (status === "checking") {
    return <span className="h-4 w-24 rounded-full bg-[var(--color-surface-raised)] animate-pulse" aria-label="Checking API status" />;
  }
  return status === "online" ? (
    <span className="inline-flex items-center gap-1.5 text-[var(--color-success)]">
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)]" /> API online
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-[var(--color-warning)]">
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-warning)]" /> API unreachable, try again shortly
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen pt-12 sm:pt-16 pb-12 sm:pb-16 md:pb-10 animate-fade-in text-[var(--color-text-primary)] selection:bg-[var(--color-accent)]/20 relative">

      <main className="pt-0 pb-0">
        <section className="max-w-7xl mx-auto px-4 sm:px-6 grid lg:grid-cols-2 gap-8 lg:gap-10 items-center">
          <div className="space-y-6 animate-fade-in-up">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 text-xs text-[var(--color-accent)]">
              <BrainCircuit size={14} />
              ML ensemble + event-driven backtests
            </div>

            <div className="space-y-4">
              <h1 className="text-3xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight">
                ML stock picks you can
                <span className="block text-[var(--color-accent)]">
                  backtest before you trade.
                </span>
              </h1>
              <p className="max-w-xl text-[var(--color-text-secondary)] text-lg md:text-xl leading-relaxed mt-2">
                Quantify ranks stocks with a three-model ensemble retrained every day, shows why each pick was made, and lets you test the strategy behind it with real trading costs before any capital is at risk.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/predict" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full bg-[var(--color-accent)] text-[var(--color-accent-foreground)] font-semibold shadow-sm hover:bg-[var(--color-accent-hover)] transition-colors">
                <Sparkles size={18} /> See today&apos;s picks
              </Link>
              <Link href="/backtest" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full border border-[var(--color-border)] text-[var(--color-text-secondary)] font-semibold hover:bg-[var(--color-surface-raised)] transition-colors">
                Run a backtest <ChevronRight size={18} />
              </Link>
            </div>

            <div className="pt-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 border border-[var(--color-border)] rounded-2xl p-1 bg-[var(--color-surface-raised)]/80">
                {METRICS.map((item, i) => (
                  <div
                    key={item.label}
                    className={`text-center px-3 py-4 sm:px-4 stat-card ${i < METRICS.length - 1 ? 'sm:border-r border-[var(--color-border)]' : ''}`}
                  >
                    <div className="stat-value font-mono text-[var(--color-text-primary)] text-lg sm:text-xl font-semibold">{item.value}</div>
                    <div className="stat-label mt-1 text-[var(--color-text-muted)] text-[11px] sm:text-xs">{item.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="relative animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
            <div className="relative bg-[var(--color-surface)]/90 rounded-[28px] p-4 sm:p-6 md:p-8 border border-[var(--color-border)] shadow-xl overflow-hidden">
              <div className="flex items-center justify-between mb-4 text-xs text-[var(--color-text-muted)]">
                <span>How a pick is made</span>
                <ApiStatusPill />
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 p-5 min-h-36">
                <div className="text-xs text-[var(--color-text-muted)]">1. Three models vote</div>
                <div className="mt-3 space-y-2">
                  {ENSEMBLE.map((model) => (
                    <div key={model} className="flex items-center gap-3 text-sm text-[var(--color-text-secondary)]">
                      <BrainCircuit size={16} className="text-[var(--color-accent)]" />
                      <span className="font-mono">{model}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 p-5 min-h-36">
                <div className="text-xs text-[var(--color-text-muted)]">2. You see the reasoning</div>
                <div className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Direction, confidence, drivers</div>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                  Each pick lists the factors that moved the prediction, in plain language.
                </p>
              </div>

              <div className="sm:col-span-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)]/80 p-6">
                <div className="mb-4">
                  <div className="text-xs text-[var(--color-text-muted)]">3. Test it, then track it</div>
                  <div className="text-lg font-semibold text-[var(--color-text-primary)]">Backtest, paper track, get alerts</div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    "Backtest with costs",
                    "Track positions",
                    "Telegram alerts",
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
            <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-accent)]">What&apos;s inside</p>
            <h2 className="text-3xl md:text-4xl font-bold mt-2 text-[var(--color-text-primary)]">Research, test and track in one place.</h2>
          </div>
          <p className="hidden md:block max-w-xl text-sm text-[var(--color-text-secondary)]">
              Predictions, strategies, risk controls and backtests share the same engine, so what you test is what generates the signal.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
            {FEATURES.map((feature) => (
              <div key={feature.title} className="border border-[var(--color-border)] bg-[var(--color-surface)]/90 rounded-2xl p-5">
                <div className="w-11 h-11 rounded-xl gradient-accent flex items-center justify-center mb-4">
                  <feature.icon size={20} className="text-[var(--color-accent-foreground)]" />
                </div>
                <h3 className="text-lg font-semibold mb-2 text-[var(--color-text-primary)]">{feature.title}</h3>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-4 md:px-6 mt-16 md:mt-24">
          <div className="bg-[var(--color-surface)]/90 rounded-[32px] p-8 md:p-12 border border-[var(--color-border)] flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8 ">
            <div className="max-w-2xl relative z-10">
              <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-accent)]">Get started</p>
              <h2 className="text-3xl md:text-4xl font-bold mt-3 leading-tight text-[var(--color-text-primary)]">
                Check today&apos;s picks, then backtest the strategy before you commit capital.
              </h2>
              <p className="mt-4 text-[var(--color-text-secondary)] text-base md:text-lg leading-relaxed">
                Create an account to track positions on your portfolio page and get alerts in Telegram.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto relative z-10">
              <Link href="/signup" className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-[var(--color-accent)] text-[var(--color-accent-foreground)] font-semibold hover:bg-[var(--color-accent-hover)] transition-colors w-full sm:w-auto">
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
