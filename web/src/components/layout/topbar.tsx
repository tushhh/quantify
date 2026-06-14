"use client";

import { Bell, Sun, Moon, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useThemeStore, useThemeEffect } from "@/lib/themeStore";
import { useAppStore } from "@/lib/store";

export default function Topbar({ title }: { title?: string }) {
  useThemeEffect();
  const path = usePathname() || "/";
  const theme = useThemeStore((s) => s.theme);
  const toggle = useThemeStore((s) => s.toggle);

  const sentenceCase = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);
  const inferredTitle =
    title ||
    (path === "/"
      ? "Home"
      : sentenceCase(path.replace("/", "").replace(/-/g, " ")));

  return (
    <header className="h-12 sm:h-14 px-4 sm:px-6 flex items-center justify-between gap-3 bg-[var(--color-surface)]/80 backdrop-blur-md border-b border-[var(--color-border)] sticky top-0 z-20">
      <div className="flex items-center gap-2 sm:gap-4 min-w-0">
        <button
          onClick={() => useAppStore.getState().toggleSidebar()}
          className="p-2 rounded-[var(--radius-md)] hover:bg-[var(--color-surface-raised)] shrink-0"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5 text-[var(--color-text-secondary)]" />
        </button>
        <h2 className="text-sm sm:text-base font-semibold text-[var(--color-text-primary)] truncate">{inferredTitle}</h2>
      </div>

      {/* Centered brand logo — absolutely positioned so it stays optically
          centered regardless of the left/right content widths. */}
      <Link
        href="/"
        aria-label="Quantify home"
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2 transition-opacity hover:opacity-80"
      >
        <img
          src="/logo-emblem.png"
          alt="Quantify"
          className="h-7 w-7 sm:h-8 sm:w-8 object-contain"
        />
        <span className="hidden sm:inline text-sm font-semibold tracking-wide text-[var(--color-text-primary)]">
          Quantify
        </span>
      </Link>

      <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
        <button className="p-2 rounded-[var(--radius-md)] hover:bg-[var(--color-surface-raised)]">
          <Bell className="h-5 w-5 text-[var(--color-text-secondary)]" />
        </button>

        <button
          onClick={toggle}
          aria-label="Toggle theme"
          className="p-2 rounded-[var(--radius-md)] hover:bg-[var(--color-surface-raised)] flex items-center justify-center"
        >
          {theme === "dark" ? <Sun className="h-5 w-5 text-[var(--color-text-secondary)]" /> : <Moon className="h-5 w-5 text-[var(--color-text-secondary)]" />}
        </button>

        <Link
          href="/account"
          aria-label="Account"
          className="h-8 w-8 sm:h-9 sm:w-9 rounded-full bg-[var(--color-surface-raised)] border border-[var(--color-border)] flex items-center justify-center hover:border-[var(--color-accent)] transition-colors"
        >
          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">U</span>
        </Link>
      </div>
    </header>
  );
}
