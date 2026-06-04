"use client";

import { clsx } from "clsx";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={clsx("animate-pulse rounded-[var(--radius-md)] bg-[var(--color-surface-raised)]", className)} />
  );
}
