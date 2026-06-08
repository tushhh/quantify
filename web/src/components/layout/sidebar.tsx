"use client";

import { useLayoutEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home, BarChart2, Activity, Layers,
  LayoutDashboard, UserCircle,
} from "lucide-react";
import { clsx } from "clsx";
import { useAppStore } from "@/lib/store";

const NAV_GROUPS = [
  {
    label: "Main",
    items: [
      { href: "/", label: "Home", icon: Home },
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "Research",
    items: [
      { href: "/backtest", label: "Backtest", icon: BarChart2 },
      { href: "/predict", label: "Predict", icon: Activity },
      { href: "/strategies", label: "Strategies", icon: Layers },
    ],
  },
];

const BOTTOM_NAV = [
  { href: "/account", label: "Account", icon: UserCircle },
];

export default function Sidebar() {
  const path = usePathname() || "/";
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);

  useLayoutEffect(() => {
    const syncSidebar = () => setSidebarOpen(window.innerWidth >= 768);
    syncSidebar();
    window.addEventListener("resize", syncSidebar);
    return () => window.removeEventListener("resize", syncSidebar);
  }, [setSidebarOpen]);

  function NavItem({ href, label, icon: Icon }: { href: string; label: string; icon: React.ElementType }) {
    const active = path === href;
    return (
      <Link
        href={href}
        onClick={() => setSidebarOpen(false)}
        title={!sidebarOpen ? label : undefined}
        className={clsx(
          "flex items-center gap-3 px-3 py-2 rounded-[var(--radius-md)] text-sm transition-colors duration-150 min-h-11",
          active
            ? "bg-[var(--color-accent-subtle)] text-[var(--color-accent)] font-medium"
            : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)]"
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {sidebarOpen && <span>{label}</span>}
      </Link>
    );
  }

  return (
    <>
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-[1px] md:hidden"
        />
      )}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col justify-between shadow-xl transition-transform duration-200 md:sticky md:top-0 md:shadow-none md:transition-[width] md:translate-x-0",
          sidebarOpen ? "translate-x-0 md:w-60 w-64" : "-translate-x-full md:w-16"
        )}
      >
        <div className="flex flex-col flex-1 min-h-0">
          <div className="px-4 py-4 md:px-5 shrink-0">
            <Link href="/" className="flex items-center gap-3">
              <div className="h-9 w-9 shrink-0 rounded-[var(--radius-md)] bg-[var(--color-accent)] flex items-center justify-center text-[var(--color-accent-foreground)] font-bold">
                Q
              </div>
              {sidebarOpen && (
                <div>
                  <div className="text-sm font-semibold text-[var(--color-text-primary)]">Quantify</div>
                  <div className="text-xs text-[var(--color-text-muted)]">ML Trading</div>
                </div>
              )}
            </Link>
          </div>

          <nav className="flex-1 px-3 py-2 flex flex-col gap-4 overflow-y-auto">
            {NAV_GROUPS.map((group) => (
              <div key={group.label}>
                {sidebarOpen && (
                  <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
                    {group.label}
                  </p>
                )}
                <div className="flex flex-col gap-0.5">
                  {group.items.map((item) => (
                    <NavItem key={item.href} {...item} />
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </div>

        <div className="px-3 py-3 border-t border-[var(--color-border)] shrink-0">
          {BOTTOM_NAV.map((item) => (
            <NavItem key={item.href} {...item} />
          ))}
        </div>
      </aside>
    </>
  );
}
