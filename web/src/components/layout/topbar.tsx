"use client";

import { Bell, Sun, Moon } from "lucide-react";
import { usePathname } from "next/navigation";
import { useThemeStore, useThemeEffect } from "@/lib/themeStore";

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
    <header className="h-14 px-6 flex items-center justify-between bg-[var(--color-surface)]/80 backdrop-blur-md border-b border-[var(--color-border)] sticky top-0 z-20">
      <div className="flex items-center gap-4">
        <h2 className="text-base font-semibold text-[var(--color-text-primary)]">{inferredTitle}</h2>
      </div>

      <div className="flex items-center gap-3">
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

        <button className="h-9 w-9 rounded-full bg-[var(--color-surface-raised)] border border-[var(--color-border)]" />
      </div>
    </header>
  );
}
