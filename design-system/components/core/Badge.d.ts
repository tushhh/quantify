import React from "react";

export type BadgeVariant = "default" | "success" | "danger" | "warning" | "info" | "accent";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Status color. @default "default" */
  variant?: BadgeVariant;
  children?: React.ReactNode;
}

/** Small status / category pill — LONG/SHORT signals, strategy tags, live status. */
export function Badge(props: BadgeProps): React.JSX.Element;
