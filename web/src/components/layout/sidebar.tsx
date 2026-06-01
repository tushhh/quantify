"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BarChart2, Activity, Layers, Settings, List } from "lucide-react";
import { clsx } from "clsx";

export default function Sidebar() {
  const path = usePathname() || "/";
  const sidebarOpen = require("@/lib/store").useAppStore((s: any) => s.sidebarOpen);
  const cls = sidebarOpen ? "w-60" : "w-16";

  const nav = [
    { href: "/", label: "Home", icon: Home },
    { href: "/backtest", label: "Backtest", icon: BarChart2 },
    { href: "/predict", label: "Predict", icon: Activity },
    { href: "/strategies", label: "Strategies", icon: Layers },
    { href: "/trades", label: "Trades", icon: List },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <aside className={`${cls} h-screen bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col justify-between transition-all`}> 
      <div>
        <div className="px-5 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-[var(--radius-md)] bg-[var(--color-accent)] flex items-center justify-center text-[var(--color-accent-foreground)] font-bold">Q</div>
            {sidebarOpen && (
              <div>
                <div className="text-sm font-semibold text-[var(--color-text-primary)]">Quantify</div>
                <div className="text-xs text-[var(--color-text-muted)]">ML Trading</div>
              </div>
            )}
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
                {sidebarOpen && <span>{n.label}</span>}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Removed redundant guest block; user state is shown in topbar */}
    </aside>
  );
}
