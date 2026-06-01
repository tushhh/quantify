"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BarChart2, Activity, Layers, Settings, List } from "lucide-react";
import { clsx } from "clsx";

export default function Sidebar() {
  const path = usePathname() || "/";

  const nav = [
    { href: "/", label: "Home", icon: Home },
    { href: "/backtest", label: "Backtest", icon: BarChart2 },
    { href: "/predict", label: "Predict", icon: Activity },
    { href: "/strategies", label: "Strategies", icon: Layers },
    { href: "/trades", label: "Trades", icon: List },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <aside className="w-60 h-screen bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col justify-between">
      <div>
        <div className="px-5 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-[var(--radius-md)] bg-[var(--color-accent)] flex items-center justify-center text-[var(--color-accent-foreground)] font-bold">Q</div>
            <div>
              <div className="text-sm font-semibold text-[var(--color-text-primary)]">Quantify</div>
              <div className="text-xs text-[var(--color-text-muted)]">ML Trading</div>
            </div>
          </Link>
        </div>

        <nav className="px-3 py-2 flex flex-col gap-1">
          {nav.map((n) => {
            const active = path === n.href;
            const Icon = n.icon;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2 rounded-[var(--radius-md)] text-sm transition-colors duration-150",
                  active
                    ? "bg-[var(--color-accent-subtle)] text-[var(--color-accent)] font-medium"
                    : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)]"
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{n.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="px-4 py-4 border-t border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-full bg-[var(--color-surface-raised)] border border-[var(--color-border)]" />
          <div className="flex-1">
            <div className="text-sm font-medium text-[var(--color-text-primary)]">Guest</div>
            <div className="text-xs text-[var(--color-text-muted)]">Sign in</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
