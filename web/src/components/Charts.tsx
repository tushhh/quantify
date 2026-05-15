"use client";

import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from "recharts";
import type { EquityPoint, DrawdownPoint } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui";

const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

function EquityTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 text-xs shadow-2xl">
      <p className="text-slate-400 mb-2 font-mono">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-mono font-semibold">
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
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 text-xs shadow-2xl">
      <p className="text-slate-400 mb-1 font-mono">{label}</p>
      <p className="font-mono font-semibold text-red-400">Drawdown: {payload[0].value.toFixed(2)}%</p>
    </div>
  );
}

export function EquityCurveChart({ data }: { data: EquityPoint[] }) {
  const hasBenchmark = data.some((d) => d.benchmark_pct !== undefined);

  return (
    <Card>
      <CardHeader title="Equity Curve" subtitle="Portfolio vs benchmark (% return from start)" />
      <div className="h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="benchmarkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.35} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "var(--text-dim)" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={fmtPct}
              tick={{ fontSize: 10, fill: "var(--text-dim)" }}
              tickLine={false}
              axisLine={false}
              width={56}
            />
            <Tooltip content={<EquityTooltip />} />
            <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1} />
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
        <div className="flex gap-5 mt-3 pt-2 border-t border-[var(--border)]">
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-blue-500 rounded" />
            <span className="text-[10px] text-slate-500">Portfolio</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-indigo-500 rounded opacity-70" style={{ backgroundImage: "repeating-linear-gradient(to right, #6366f1 0, #6366f1 4px, transparent 4px, transparent 8px)" }} />
            <span className="text-[10px] text-slate-500">Benchmark</span>
          </div>
        </div>
      )}
    </Card>
  );
}

export function DrawdownChart({ data }: { data: DrawdownPoint[] }) {
  const normalizedData = data.map((d) => ({
    ...d,
    drawdown: -Math.abs(d.drawdown),
  }));

  return (
    <Card>
      <CardHeader title="Drawdown" subtitle="Underwater percentage from peak equity" />
      <div className="h-44 sm:h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={normalizedData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.35} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "var(--text-dim)" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              tick={{ fontSize: 10, fill: "var(--text-dim)" }}
              tickLine={false}
              axisLine={false}
              width={46}
            />
            <Tooltip content={<DrawdownTooltip />} />
            <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1} />
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
