"use client";

import { create } from "zustand";
import { useEffect } from "react";

type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const initialTheme: Theme = typeof window !== "undefined" ? ((localStorage.getItem("theme") as Theme) || "dark") : "dark";

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initialTheme,
  setTheme: (t: Theme) => {
    set({ theme: t });
    try { localStorage.setItem("theme", t); } catch {};
    if (typeof document !== "undefined") document.documentElement.setAttribute("data-theme", t);
  },
  toggle: () => {
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      try { localStorage.setItem("theme", next); } catch {};
      if (typeof document !== "undefined") document.documentElement.setAttribute("data-theme", next);
      return { theme: next };
    });
  },
}));

// Ensure the attribute is set on first render when used in client components
export function useThemeEffect() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  useEffect(() => {
    if (typeof document !== "undefined") {
      // initialize from persisted preference if present
      try {
        const stored = localStorage.getItem("theme") as Theme | null;
        if (stored && stored !== theme) {
          setTheme(stored);
          return;
        }
      } catch {}
      if (document.documentElement.getAttribute("data-theme") !== theme) {
        document.documentElement.setAttribute("data-theme", theme);
      }
    }
  }, [theme, setTheme]);
}
