"use client";

import { create } from "zustand";
import { useEffect } from "react";
import { safeGetItem, safeSetItem } from "./safeStorage";

type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

function applyTheme(t: Theme) {
  if (typeof document !== "undefined") document.documentElement.setAttribute("data-theme", t);
}

// Always start as "dark", the theme the server renders. Reading storage here
// would make the first client render differ from the server HTML (a hydration
// error for anyone with a stored light theme). useThemeEffect syncs the stored
// preference after mount; the inline script in layout.tsx sets data-theme
// before paint so there's no flash.
export const useThemeStore = create<ThemeState>((set) => ({
  theme: "dark",
  setTheme: (t: Theme) => {
    set({ theme: t });
    safeSetItem("theme", t);
    applyTheme(t);
  },
  toggle: () => {
    set((s) => {
      const next: Theme = s.theme === "dark" ? "light" : "dark";
      safeSetItem("theme", next);
      applyTheme(next);
      return { theme: next };
    });
  },
}));

// Sync the stored preference into the store after mount, and keep data-theme in step.
export function useThemeEffect() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  useEffect(() => {
    const stored = safeGetItem("theme");
    if ((stored === "light" || stored === "dark") && stored !== theme) {
      setTheme(stored);
      return;
    }
    if (typeof document !== "undefined" && document.documentElement.getAttribute("data-theme") !== theme) {
      applyTheme(theme);
    }
    // Only on mount: later changes go through setTheme/toggle, which persist.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
