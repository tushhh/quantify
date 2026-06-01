"use client";

import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from "recharts";
import type { EquityPoint, DrawdownPoint } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { CardHeader, CardContent } from "@/components/ui/card";

const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

const chartConfig = {
  primary: "var(--color-accent)",
  grid: "var(--color-border)",
  text: "var(--color-text-muted)",
};

function EquityTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm shadow-[var(--shadow-md)]">
      <p className="text-sm text-[var(--color-text-muted)] mb-1 font-mono">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-mono font-semibold text-[var(--color-text-primary)]">
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
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm shadow-[var(--shadow-md)]">
      <p className="text-sm text-[var(--color-text-muted)] mb-1 font-mono">{label}</p>
      <p className="font-mono font-semibold text-[var(--color-danger)]">Drawdown: {payload[0].value.toFixed(2)}%</p>
    </div>
  );
}

export function EquityCurveChart({ data }: { data: EquityPoint[] }) {
  const hasBenchmark = data.some((d) => d.benchmark_pct !== undefined);

  return (
    <Card className="shadow-[var(--shadow-sm)]">
      <CardHeader className="flex items-start justify-between p-5 pb-0">
        <div>
          <h3 className="text-base font-semibold text-[var(--color-text-primary)] tracking-tight">Equity Curve</h3>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">Portfolio vs benchmark (% return from start)</p>
        </div>
      </CardHeader>
      <div className="h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-success)" stopOpacity={0.18} />
                <stop offset="95%" stopColor="var(--color-success)" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="benchmarkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.12} />
                <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartConfig.grid} vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: chartConfig.text }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={fmtPct}
              tick={{ fontSize: 12, fill: chartConfig.text }}
              tickLine={false}
              axisLine={false}
              width={56}
            />
            <Tooltip content={<EquityTooltip />} />
            <ReferenceLine y={0} stroke={chartConfig.grid} strokeWidth={1} />
            {hasBenchmark && (
              <Area
                type="monotone"
                dataKey="benchmark_pct"
                stroke="var(--color-accent)"
                strokeWidth={1.5}
                fill="url(#benchmarkGrad)"
                dot={false}
                strokeDasharray="4 2"
              />
            )}
            <Area
              type="monotone"
              dataKey="pct"
              stroke="var(--color-success)"
              strokeWidth={2}
              fill="url(#portfolioGrad)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {hasBenchmark && (
        <div className="flex gap-5 mt-3 pt-2 border-t border-[var(--color-border-subtle)]">
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-[var(--color-success)] rounded" />
            <span className="text-[10px] text-[var(--color-text-muted)]">Portfolio</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-[var(--color-accent)] rounded opacity-80" style={{ backgroundImage: "repeating-linear-gradient(to right, var(--color-accent) 0, var(--color-accent) 4px, transparent 4px, transparent 8px)" }} />
            <span className="text-[10px] text-[var(--color-text-muted)]">Benchmark</span>
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
    <Card className="shadow-[var(--shadow-sm)]">
      <CardHeader className="flex items-start justify-between p-5 pb-0">
        <div>
          <h3 className="text-base font-semibold text-[var(--color-text-primary)] tracking-tight">Drawdown</h3>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">Underwater percentage from peak equity</p>
        </div>
      </CardHeader>
      <div className="h-44 sm:h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={normalizedData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-danger)" stopOpacity={0.28} />
                <stop offset="95%" stopColor="var(--color-danger)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartConfig.grid} vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: chartConfig.text }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              tick={{ fontSize: 12, fill: chartConfig.text }}
              tickLine={false}
              axisLine={false}
              width={46}
            />
            <Tooltip content={<DrawdownTooltip />} />
            <ReferenceLine y={0} stroke={chartConfig.grid} strokeWidth={1} />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="var(--color-danger)"
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
