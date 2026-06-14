import React from "react";

export interface DriverPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Feature name (rendered in mono), e.g. "rsi_14", "mom_12_1". */
  feature: string;
  /** Standardised z-score for the feature. */
  zscore?: number;
  /** Whether a higher value is favorable (▲ green) or lower (▼ red). @default "higher" */
  direction?: "higher" | "lower";
}

/** A single ML feature driver: name, z-score, and favorability arrow. */
export function DriverPill(props: DriverPillProps): React.JSX.Element;
