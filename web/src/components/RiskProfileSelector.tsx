"use client";

import clsx from "clsx";
import { ChevronDown } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { RiskPreset } from "@/lib/api";
import { Slider } from "@/components/ui";

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
      {/* Presets: one segmented control; the selected preset's description sits below it. */}
      <div>
        <div role="radiogroup" aria-label="Risk preset" className="grid grid-cols-2 sm:grid-cols-4 rounded-[var(--radius-sm)] border border-[var(--color-border)] overflow-hidden">
          {presets.map((p) => (
            <button
              key={p.id}
              role="radio"
              aria-checked={selectedPresetId === p.id}
              onClick={() => handlePresetClick(p)}
              className={clsx(
                "h-9 px-2 text-[13px] whitespace-nowrap border-r border-[var(--color-border)] last:border-r-0 [&:nth-child(2)]:max-sm:border-r-0 max-sm:[&:nth-child(-n+2)]:border-b",
                selectedPresetId === p.id
                  ? "bg-[var(--color-accent-subtle)] text-[var(--color-text-primary)] font-medium"
                  : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
          {presets.find((p) => p.id === selectedPresetId)?.description}
        </p>
      </div>

      {/* Limits and sizing start collapsed (CLAUDE.md: advanced controls are opt-in). */}
      <details className="group rounded-[var(--radius-sm)] border border-[var(--color-border)]">
        <summary className="cursor-pointer select-none list-none px-3 h-9 flex items-center gap-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] [&::-webkit-details-marker]:hidden">
          <ChevronDown aria-hidden className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          Adjust limits and position sizing
        </summary>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-3 border-t border-[var(--color-border)]">
        <Slider
          label="Max portfolio drawdown"
          value={risk.max_portfolio_drawdown}
          min={0.02} max={0.5} step={0.01}
          onChange={(v) => { setRisk({ max_portfolio_drawdown: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Max single position"
          value={risk.max_single_position}
          min={0.01} max={0.5} step={0.01}
          onChange={(v) => { setRisk({ max_single_position: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Daily loss limit"
          value={risk.daily_loss_limit}
          min={0.005} max={0.15} step={0.005}
          onChange={(v) => { setRisk({ daily_loss_limit: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Max gross leverage"
          value={risk.max_gross_leverage}
          min={0.5} max={3.0} step={0.1}
          onChange={(v) => { setRisk({ max_gross_leverage: v }); setSelectedPresetId("custom"); }}
          format={x}
        />
        <Slider
          label="Stop loss"
          value={risk.default_stop_loss}
          min={0.005} max={0.15} step={0.005}
          onChange={(v) => { setRisk({ default_stop_loss: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />
        <Slider
          label="Take profit"
          value={risk.default_take_profit}
          min={0.01} max={0.30} step={0.01}
          onChange={(v) => { setRisk({ default_take_profit: v }); setSelectedPresetId("custom"); }}
          format={pct}
        />

        {/* Position sizer */}
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label className="text-xs text-[var(--color-text-secondary)]">Position sizing</label>
          <div className="flex gap-2 flex-wrap">
            {(["equal_weight", "volatility_target", "half_kelly"] as const).map((s) => (
              <button
                key={s}
                onClick={() => { setRisk({ default_position_sizer: s }); setSelectedPresetId("custom"); }}
                aria-pressed={risk.default_position_sizer === s}
                className={clsx(
                  "h-8 px-3 rounded-[var(--radius-sm)] text-xs border",
                  risk.default_position_sizer === s
                    ? "bg-[var(--color-accent-subtle)] border-[var(--color-accent)]/50 text-[var(--color-text-primary)] font-medium"
                    : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
                )}
              >
                {s === "equal_weight" ? "Equal weight" : s === "volatility_target" ? "Volatility target" : "Half Kelly"}
              </button>
            ))}
          </div>
        </div>
      </div>
      </details>
    </div>
  );
}
