import React from "react";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Status color + default glyph. @default "info" */
  variant?: "info" | "success" | "danger" | "warning";
  /** Optional bold title line. */
  title?: string;
  /** Override the default status glyph with a custom node. */
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

/** Inline status banner — trade-logged confirmations, validation errors, dip alerts. */
export function Alert(props: AlertProps): React.JSX.Element;
