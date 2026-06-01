"use client";

import { useState } from "react";
import clsx from "clsx";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { StrategyInfo } from "@/lib/api";
import { Slider } from "@/components/ui";

type Props = { strategies: StrategyInfo[] };

export function StrategyConfigurator({ strategies }: Props) {
  const { strategies: configs, setStrategy } = useAppStore();
  const [expanded, setExpanded] = useState<string | null>(null);

  const totalAllocation = Object.values(configs)
    .filter((c) => c.enabled)
    .reduce((s, c) => s + c.allocation, 0);

  const enabledCount = Object.values(configs).filter((c) => c.enabled).length;

  const allocationWarning = enabledCount > 0 && Math.abs(totalAllocation - 1) > 0.02;

  return (
    <div className="flex flex-col gap-2">
      {/* Allocation summary bar */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-[var(--color-text-muted)]">Total Allocation</span>
        <span
          className={clsx(
            "text-xs font-mono font-bold",
            allocationWarning ? "text-[var(--color-warning)]" : "text-[var(--color-success)]"
          )}
        >
          {(totalAllocation * 100).toFixed(0)}%
          {allocationWarning && " ⚠ should sum to 100%"}
        </span>
      </div>

      {/* Strategy rows */}
      {strategies.map((info) => {
        const cfg = configs[info.name] ?? { enabled: true, allocation: info.default_allocation, params: {} };
        const isOpen = expanded === info.name;

        return (
          <div
            key={info.name}
            className={clsx(
              "rounded-lg glass transition-all overflow-hidden",
              cfg.enabled
                ? "border-[var(--color-cta)]/30"
                : "border-[var(--color-border)]/30 opacity-50"
            )}
          >
            {/* Header row */}
            <div className="flex items-center gap-3 p-3 hover:bg-[var(--color-cta)]/10 transition-colors">
              {/* Enable toggle */}
              <button
                onClick={() => setStrategy(info.name, { enabled: !cfg.enabled })}
                className={clsx(
                  "w-9 h-5 rounded-full transition-colors shrink-0 relative",
                  cfg.enabled ? "bg-[var(--color-cta)]" : "bg-[var(--color-surface-raised)]"
                )}
                aria-label={`${cfg.enabled ? "Disable" : "Enable"} ${info.label}`}
                aria-pressed={cfg.enabled}
                role="switch"
              >
                <span
                  className={clsx(
                    "absolute top-0.5 w-4 h-4 rounded-full bg-[var(--color-surface)] shadow transition-all",
                    cfg.enabled ? "left-4" : "left-0.5"
                  )}
                />
              </button>

              {/* Name */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--color-text-inverse)] truncate">{info.label}</p>
                <p className="text-[10px] text-[var(--color-text-muted)] line-clamp-1">{info.description}</p>
              </div>

              {/* Allocation */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs font-mono text-[var(--color-cta)]">
                  {(cfg.allocation * 100).toFixed(0)}%
                </span>
                <button
                  onClick={() => setExpanded(isOpen ? null : info.name)}
                  className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] transition-colors"
                  disabled={!cfg.enabled}
                >
                  {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
            </div>

            {/* Expanded params */}
            {isOpen && cfg.enabled && (
              <div className="px-4 pb-4 pt-1 flex flex-col gap-3 border-t border-[var(--color-border)]/30">
                {/* Allocation slider */}
                <Slider
                  label="Allocation"
                  value={cfg.allocation}
                  min={0.0} max={1.0} step={0.05}
                  onChange={(v) => setStrategy(info.name, { allocation: v })}
                  format={(v) => `${(v * 100).toFixed(0)}%`}
                />

                {/* Strategy-specific params */}
                {info.params.map((p) => {
                  const currentVal = (cfg.params[p.key] ?? p.default) as number | boolean | string;

                  if (p.type === "bool") {
                    return (
                      <div key={p.key} className="flex items-center justify-between">
                        <label className="text-xs text-[var(--color-text-secondary)]">{p.label}</label>
                        <button
                          onClick={() =>
                            setStrategy(info.name, {
                              params: { ...cfg.params, [p.key]: !currentVal },
                            })
                          }
                          className={clsx(
                            "w-8 h-4 rounded-full transition-colors relative",
                            currentVal ? "bg-[var(--color-cta)]" : "bg-[var(--color-surface-raised)]"
                          )}
                        >
                          <span
                            className={clsx(
                              "absolute top-0.5 w-3 h-3 rounded-full bg-[var(--color-surface)] shadow transition-all",
                              currentVal ? "left-4" : "left-0.5"
                            )}
                          />
                        </button>
                      </div>
                    );
                  }

                  if (p.type === "select" && p.options) {
                    return (
                      <div key={p.key} className="flex flex-col gap-1.5">
                        <label className="text-xs text-[var(--color-text-secondary)]">{p.label}</label>
                        <div className="flex gap-1.5 flex-wrap">
                          {p.options.map((opt) => (
                            <button
                              key={opt}
                              onClick={() =>
                                setStrategy(info.name, {
                                  params: { ...cfg.params, [p.key]: opt },
                                })
                              }
                              className={clsx(
                                "px-2.5 py-1 rounded text-[10px] font-semibold border transition-all",
                                currentVal === opt
                                  ? "bg-[var(--color-cta)] border-[var(--color-cta)] text-[var(--color-text-inverse)]"
                                  : "bg-[var(--color-surface-raised)]/30 border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:border-[var(--border-bright)]"
                              )}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  }

                  // int | float
                  return (
                    <Slider
                      key={p.key}
                      label={p.label}
                      value={currentVal as number}
                      min={p.min ?? 0}
                      max={p.max ?? 100}
                      step={p.step ?? 1}
                      onChange={(v) =>
                        setStrategy(info.name, {
                          params: { ...cfg.params, [p.key]: v },
                        })
                      }
                    />
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
