"use client";

import clsx from "clsx";
import { useAppStore } from "@/lib/store";
import type { RiskPreset } from "@/lib/api";
import { Slider } from "@/components/ui";

const PRESET_COLORS: Record<string, string> = {
  conservative: "text-emerald-400 border-emerald-500/40 bg-emerald-500/10",
  moderate:     "text-blue-400   border-blue-500/40   bg-blue-500/10",
  aggressive:   "text-amber-400  border-amber-500/40  bg-amber-500/10",
  custom:       "text-slate-400  border-slate-500/40  bg-slate-500/10",
};

const SELECTED_GLOW: Record<string, string> = {
  conservative: "ring-1 ring-emerald-500/50",
  moderate:     "ring-1 ring-blue-500/50",
  aggressive:   "ring-1 ring-amber-500/50",
  custom:       "ring-1 ring-slate-500/50",
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
              "flex flex-col gap-1 rounded-xl border p-3 text-left transition-all hover:scale-[1.02]",
              PRESET_COLORS[p.id] ?? PRESET_COLORS.custom,
              selectedPresetId === p.id
                ? SELECTED_GLOW[p.id]
                : "opacity-70 hover:opacity-100"
            )}
          >
            <span className="text-xs font-bold">{p.label}</span>
            <span className="text-[10px] leading-tight opacity-70 line-clamp-2">{p.description}</span>
          </button>
        ))}
      </div>

      {/* Fine-tune sliders (always visible) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 rounded-xl border border-[#1e2d4a] bg-[#0e1525]">
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
          <label className="text-xs text-slate-400">Position Sizer</label>
          <div className="flex gap-2">
            {(["equal_weight", "volatility_target", "half_kelly"] as const).map((s) => (
              <button
                key={s}
                onClick={() => { setRisk({ default_position_sizer: s }); setSelectedPresetId("custom"); }}
                className={clsx(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all",
                  risk.default_position_sizer === s
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "bg-[#162035] border-[#1e2d4a] text-slate-400 hover:text-white"
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
