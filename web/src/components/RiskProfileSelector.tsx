"use client";

import clsx from "clsx";
import { useAppStore } from "@/lib/store";
import type { RiskPreset } from "@/lib/api";
import { Slider } from "@/components/ui";

const PRESET_STYLES: Record<string, string> = {
  conservative: "text-[var(--color-success)] border-[var(--color-success)]/30 bg-[var(--color-success-subtle)] hover:border-[var(--color-success)]/50",
  moderate:     "text-[var(--color-info)] border-[var(--color-info)]/30 bg-[var(--color-info-subtle)] hover:border-[var(--color-info)]/50",
  aggressive:   "text-[var(--color-warning)] border-[var(--color-warning)]/30 bg-[var(--color-warning-subtle)] hover:border-[var(--color-warning)]/50",
  custom:       "text-[var(--color-text-secondary)] border-[var(--color-border)]/30 bg-[var(--color-surface-raised)] hover:border-[var(--color-border)]/50",
};

const SELECTED_RING: Record<string, string> = {
  conservative: "ring-1 ring-[var(--color-success)]/40",
  moderate:     "ring-1 ring-[var(--color-info)]/40",
  aggressive:   "ring-1 ring-[var(--color-warning)]/40",
  custom:       "ring-1 ring-[var(--color-border)]/40",
};

type Props = { presets: RiskPreset[] };

export function RiskProfileSelector({ presets }: Props) {
  const { risk, selectedPresetId, applyPreset, setSelectedPresetId, setRisk } = useAppStore();

  const handlePresetClick = (preset: RiskPreset) => {
    if (preset.id === "custom") {
      setSelectedPresetId("custom");
    } else {
      applyPreset(preset);
    }
  };

  const pct = (v: number) => `${(v * 100).toFixed(0)}%`;
  const x   = (v: number) => `${v.toFixed(1)}×`;

  return (
    <div className="flex flex-col gap-5">
      {/* Preset pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {presets.map((p) => (
          <button
            key={p.id}
            onClick={() => handlePresetClick(p)}
            className={clsx(
              "flex flex-col gap-1 rounded-xl border p-3 text-left transition-all active:scale-[0.98]",
              PRESET_STYLES[p.id] ?? PRESET_STYLES.custom,
              selectedPresetId === p.id
                ? (SELECTED_RING[p.id] ?? "ring-1 ring-slate-500/40")
                : "opacity-60 hover:opacity-100"
            )}
          >
            <span className="text-xs font-bold">{p.label}</span>
            <span className="text-[10px] leading-tight opacity-60 line-clamp-2">{p.description}</span>
          </button>
        ))}
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 rounded-xl bg-[var(--color-surface-raised)] border border-[var(--color-border)]">
        <Slider
          label="Max Portfolio Drawdown"
          value={risk.max_portfolio_drawdown}
          min={0.02} max={0.5} step={0.01}
          onChange={(v) => { setRisk({ max_portfolio_drawdown: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Max Single Position"
          value={risk.max_single_position}
          min={0.01} max={0.5} step={0.01}
          onChange={(v) => { setRisk({ max_single_position: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Daily Loss Limit"
          value={risk.daily_loss_limit}
          min={0.005} max={0.15} step={0.005}
          onChange={(v) => { setRisk({ daily_loss_limit: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Max Gross Leverage"
          value={risk.max_gross_leverage}
          min={0.5} max={3.0} step={0.1}
          onChange={(v) => { setRisk({ max_gross_leverage: v }); setSelectedPresetId("custom"); }}
          format={x}
        />
        <Slider
          label="Stop Loss"
          value={risk.default_stop_loss}
          min={0.005} max={0.15} step={0.005}
          onChange={(v) => { setRisk({ default_stop_loss: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Take Profit"
          value={risk.default_take_profit}
          min={0.01} max={0.30} step={0.01}
          onChange={(v) => { setRisk({ default_take_profit: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />

        {/* Position sizer */}
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label className="text-xs text-[var(--color-text-secondary)]">Position Sizer</label>
          <div className="flex gap-2 flex-wrap">
            {(["equal_weight", "volatility_target", "half_kelly"] as const).map((s) => (
              <button
                key={s}
                onClick={() => { setRisk({ default_position_sizer: s }); setSelectedPresetId("custom"); }}
                className={clsx(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all active:scale-[0.97]",
                  risk.default_position_sizer === s
                    ? "bg-[var(--color-cta)] border-[var(--color-cta)] text-[var(--color-text-inverse)]"
                    : "bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:border-[var(--border-bright)]"
                )}
              >
                {s === "equal_weight" ? "Equal Weight" : s === "volatility_target" ? "Vol Target" : "Half Kelly"}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
