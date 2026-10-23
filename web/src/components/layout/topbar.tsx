"use client";

import { Sun, Moon, Menu, UserCircle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useThemeStore, useThemeEffect } from "@/lib/themeStore";
import { useAppStore } from "@/lib/store";

// What each route is called in the interface (routes keep their URLs).
const PAGE_NAMES: Record<string, string> = {
  "/": "Overview",
  "/predict": "Picks",
  "/backtest": "Backtest",
  "/portfolio": "Portfolio",
  "/strategies": "Strategies",
  "/universe": "Universe",
  "/account": "Account",
  "/settings": "Settings",
  "/login": "Log in",
  "/signup": "Create account",
};

export default function Topbar({ title }: { title?: string }) {
  useThemeEffect();
  const path = usePathname() || "/";
  const theme = useThemeStore((s) => s.theme);
  const toggle = useThemeStore((s) => s.toggle);
  const pageName = title || PAGE_NAMES[path] || path.replace("/", "");

  return (
    <header className="h-12 px-4 sm:px-8 flex items-center justify-between gap-3 bg-[var(--color-bg)] border-b border-[var(--color-border)] sticky top-0 z-20">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={() => useAppStore.getState().toggleSidebar()}
          className="p-1.5 -ml-1.5 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          aria-label="Toggle navigation"
        >
          <Menu className="h-4 w-4" />
        </button>
        <Link href="/" aria-label="Quantify overview" className="md:hidden flex items-center gap-2">
          <img src="/logo-emblem.png" alt="" className="h-5 w-5 object-contain" />
        </Link>
        <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">{pageName}</span>
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          className="p-2 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <Link
          href="/account"
          aria-label="Account"
          className="p-2 rounded-[var(--radius-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        >
          <UserCircle className="h-4 w-4" />
        </Link>
      </div>
    </header>
  );
}
