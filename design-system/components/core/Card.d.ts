import React from "react";

/**
 * Props for the Quantify Card surface container.
 */
export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** `compact` adds 16px internal padding; `default` leaves padding to sub-parts. @default "default" */
  variant?: "default" | "compact";
  /** Brighten border + lift shadow on hover. @default false */
  interactive?: boolean;
  children?: React.ReactNode;
}
export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  /** Right-aligned actions slot (buttons, badges). */
  actions?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * Surface container: hairline border, soft shadow, 14px radius. Compose with
 * CardHeader / CardContent / CardFooter.
 *
 * @startingPoint section="Core" subtitle="Surface container with header / content / footer" viewport="700x260"
 */
export function Card(props: CardProps): React.JSX.Element;
export function CardHeader(props: CardHeaderProps): React.JSX.Element;
export function CardContent(props: React.HTMLAttributes<HTMLDivElement>): React.JSX.Element;
export function CardFooter(props: React.HTMLAttributes<HTMLDivElement>): React.JSX.Element;
