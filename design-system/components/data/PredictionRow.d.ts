import React from "react";

export interface Driver {
  feature: string;
  zscore?: number;
  direction?: "higher" | "lower";
}

/**
 * Props for a single ranked ML signal row.
 */
export interface PredictionRowProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> {
  /** 1-based rank in the day's list. */
  rank: number;
  /** Ticker symbol, e.g. "NVDA". */
  symbol: string;
  /** Signal side. @default "long" */
  side?: "long" | "short";
  /** Predicted next-day return, in percent. */
  predictedReturnPct?: number;
  /** Model strength score (signed). */
  strength?: number;
  /** Up to 3 feature drivers are shown. */
  drivers?: Driver[];
  /** Row click (e.g. pre-fill the trade form). */
  onClick?: () => void;
}

/**
 * One ranked ML signal row — rank, ticker, side badge, predicted return,
 * driver pills and strength. Composes Badge + DriverPill.
 *
 * @startingPoint section="Data" subtitle="Ranked ML signal row with drivers" viewport="700x110"
 */
export function PredictionRow(props: PredictionRowProps): React.JSX.Element;
