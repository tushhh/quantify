import React from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "link";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

/**
 * Props for the Quantify Button.
 */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style. @default "primary" */
  variant?: ButtonVariant;
  /** Control height/padding. @default "md" */
  size?: ButtonSize;
  /** Show a spinner and disable interaction. */
  loading?: boolean;
  /** Optional leading icon node (e.g. a Lucide element). */
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * Primary action control for Quantify. Accent fill for the main action,
 * raised-surface secondary, transparent ghost, and destructive danger.
 *
 * @startingPoint section="Core" subtitle="Accent / secondary / ghost / danger buttons" viewport="700x160"
 */
export function Button(props: ButtonProps): React.JSX.Element;
