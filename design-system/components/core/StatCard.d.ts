import React from "react";

/**
 * Props for the Quantify StatCard KPI tile.
 */
export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Metric label (e.g. "Sharpe Ratio"). */
  label: string;
  /** Formatted metric value (e.g. "1.84", "+12.4%", "$128,400"). */
  value: string | number;
  /** Optional period-over-period delta in percent; sign drives color + arrow. */
  change?: number;
  /** Caption beside the delta. @default "vs last period" */
  changeLabel?: string;
  /** Optional trailing icon node, shown in an accent tile. */
  icon?: React.ReactNode;
}

/**
 * Labelled KPI tile with tabular value and optional signed delta.
 *
 * @startingPoint section="Core" subtitle="KPI tile with label, value and delta" viewport="700x150"
 */
export function StatCard(props: StatCardProps): React.JSX.Element;
