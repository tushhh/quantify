"use client";

import { useLayoutEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ListOrdered, LineChart, Wallet, Layers, Globe, UserCircle } from "lucide-react";
import { clsx } from "clsx";
import { useAppStore } from "@/lib/store";

// Ordered by how often a trader needs them: this month's picks first.
const NAV = [
  { href: "/predict", label: "Picks", icon: ListOrdered },
  { href: "/backtest", label: "Backtest", icon: LineChart },
  { href: "/portfolio", label: "Portfolio", icon: Wallet },
  { href: "/strategies", label: "Strategies", icon: Layers },
  { href: "/universe", label: "Universe", icon: Globe },
];

// Module scope, so it isn't a new component type (and remount) on every Sidebar render.
function NavItem({
  href, label, icon: Icon, active, expanded,
}: { href: string; label: string; icon: React.ElementType; active: boolean; expanded: boolean }) {
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  return (
    <Link
      href={href}
      // Close the overlay drawer on mobile only; on desktop the sidebar stays as the user left it.
      onClick={() => { if (window.innerWidth < 768) setSidebarOpen(false); }}
      title={!expanded ? label : undefined}
      aria-current={active ? "page" : undefined}
      className={clsx(
        "relative flex items-center gap-3 h-9 pl-4 pr-3 text-[13px] transition-colors",
        active
          ? "text-[var(--color-text-primary)] font-medium"
          : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
      )}
    >
      {active && <span aria-hidden className="absolute left-0 top-2 bottom-2 w-0.5 bg-[var(--color-accent)]" />}
      <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
      {expanded && <span>{label}</span>}
    </Link>
  );
}

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

  return (
    <>
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
        />
      )}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 bg-[var(--color-bg)] border-r border-[var(--color-border)] flex flex-col transition-transform duration-200 md:sticky md:top-0 md:h-screen md:transition-[width] md:translate-x-0",
          sidebarOpen ? "translate-x-0 w-56" : "-translate-x-full md:w-14"
        )}
      >
        <Link href="/" className="h-12 flex items-center gap-2.5 px-4 border-b border-[var(--color-border)] shrink-0">
          <img src="/logo-emblem.png" alt="" className="h-5 w-5 object-contain shrink-0" />
          {sidebarOpen && <span className="text-sm font-semibold tracking-tight text-[var(--color-text-primary)]">Quantify</span>}
        </Link>

        <nav aria-label="Main" className="flex-1 py-3 flex flex-col overflow-y-auto">
          {NAV.map((item) => (
            <NavItem key={item.href} {...item} active={path === item.href} expanded={sidebarOpen} />
          ))}
        </nav>

        <div className="py-3 border-t border-[var(--color-border)] shrink-0">
          <NavItem href="/account" label="Account" icon={UserCircle} active={path === "/account"} expanded={sidebarOpen} />
        </div>
      </aside>
    </>
  );
}
