import React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Field label rendered above the input. */
  label?: string;
  /** Helper text below the field. */
  hint?: string;
  /** Error message; turns the border red and replaces the hint. */
  error?: string;
  /** Inline leading prefix (e.g. "$" for prices), shown in mono. */
  prefix?: string;
}

/** Text input with label, hint, error and optional mono prefix. Accent focus ring. */
export function Input(props: InputProps): React.JSX.Element;
