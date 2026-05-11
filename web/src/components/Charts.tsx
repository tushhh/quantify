"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import type { EquityPoint, DrawdownPoint } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui";

// ── Formatters ─────────────────────────────────────────────────────────────

const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

// ── Custom Tooltip ──────────────────────────────────────────────────────────

function EquityTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#1e2d4a] bg-[#0e1525] p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-2">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-mono">
          {p.dataKey === "pct" ? "Portfolio" : "Benchmark"}: {fmtPct(p.value)}
        </p>
      ))}
    </div>
  );
}

function DrawdownTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#1e2d4a] bg-[#0e1525] p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className="font-mono text-red-400">Drawdown: {payload[0].value.toFixed(2)}%</p>
    </div>
  );
}

// ── Equity Curve ────────────────────────────────────────────────────────────

export function EquityCurveChart({ data }: { data: EquityPoint[] }) {
  const hasBenchmark = data.some((d) => d.benchmark_pct !== undefined);

  return (
    <Card>
      <CardHeader title="Equity Curve" subtitle="Portfolio vs benchmark (% return from start)" />
      <div className="h-64 sm:h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="benchmarkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#64748b" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={fmtPct}
              tick={{ fontSize: 10, fill: "#64748b" }}
              tickLine={false}
              axisLine={false}
              width={55}
            />
            <Tooltip content={<EquityTooltip />} />
            <ReferenceLine y={0} stroke="#1e2d4a" />
            {hasBenchmark && (
              <Area
                type="monotone"
                dataKey="benchmark_pct"
                stroke="#6366f1"
                strokeWidth={1.5}
                fill="url(#benchmarkGrad)"
                dot={false}
                strokeDasharray="4 2"
              />
            )}
            <Area
              type="monotone"
              dataKey="pct"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#portfolioGrad)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {hasBenchmark && (
        <div className="flex gap-4 mt-3">
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-blue-500" />
            <span className="text-[10px] text-slate-500">Portfolio</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-indigo-500 border-dashed border-b border-indigo-500" />
            <span className="text-[10px] text-slate-500">Benchmark (SPY)</span>
          </div>
        </div>
      )}
    </Card>
  );
}

// ── Drawdown Chart ──────────────────────────────────────────────────────────

export function DrawdownChart({ data }: { data: DrawdownPoint[] }) {
  return (
    <Card>
      <CardHeader title="Drawdown" subtitle="Portfolio underwater percentage from peak" />
      <div className="h-48 sm:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#64748b" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              tick={{ fontSize: 10, fill: "#64748b" }}
              tickLine={false}
              axisLine={false}
              width={45}
            />
            <Tooltip content={<DrawdownTooltip />} />
            <ReferenceLine y={0} stroke="#1e2d4a" />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ef4444"
              strokeWidth={1.5}
              fill="url(#ddGrad)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
