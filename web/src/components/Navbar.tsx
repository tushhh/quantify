"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { TrendingUp, BarChart2, Globe, Zap, Menu, X, LogOut, UserCircle, Home, Sparkles } from "lucide-react";
import clsx from "clsx";
import { useState, useEffect } from "react";

const NAV = [
  { href: "/",  label: "Home",  icon: Home },
  { href: "/backtest",   label: "Backtest",   icon: TrendingUp },
  { href: "/screener",   label: "Screener",   icon: Sparkles },
  { href: "/strategies", label: "Strategies", icon: BarChart2 },
  { href: "/universe",   label: "Universe",   icon: Globe },
];

export function Navbar() {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loggedIn, setLoggedIn] = useState<boolean>(() =>
    typeof window !== "undefined" ? !!localStorage.getItem("token") : false
  );
  const [initial, setInitial] = useState<string | null>(null);

  function extractInitialFromToken(): string | null {
    try {
      if (typeof window === "undefined") return null;
      const token = localStorage.getItem("token");
      if (!token) return null;
      const parts = token.split(".");
      if (parts.length < 2) return null;
      const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      const json = JSON.parse(decodeURIComponent(escape(atob(payload))));
      const name = json.username || json.name || json.sub || json.email;
      if (!name) return null;
      return String(name).trim().charAt(0).toUpperCase();
    } catch (e) {
      return null;
    }
  }

  useEffect(() => {
    // initialize from storage
    setLoggedIn(!!(typeof window !== "undefined" && localStorage.getItem("token")));
    setInitial(extractInitialFromToken());

    const onAuth = () => {
      setLoggedIn(!!localStorage.getItem("token"));
      setInitial(extractInitialFromToken());
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === "token") onAuth();
    };
    window.addEventListener("auth", onAuth);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("auth", onAuth);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const logout = () => {
    localStorage.removeItem("token");
    setLoggedIn(false);
    router.push("/");
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-center w-full px-4 pt-4 pointer-events-none">
      {/* ── Desktop nav ─────────────────────────────────────── */}
      <nav className="hidden md:flex items-center justify-between w-full max-w-7xl px-5 py-3 rounded-[1.5rem] bg-[var(--color-overlay)] border border-[var(--border)] shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-2xl pointer-events-auto">

        {/* Brand */}
        <Link href="/" className="flex items-center gap-3 shrink-0 group mr-5 transition-opacity hover:opacity-80">
          <span className="w-8 h-8 rounded-full gradient-accent flex items-center justify-center shadow-lg shadow-[var(--color-cta)]/20">
            <TrendingUp size={16} strokeWidth={2.5} className="text-[var(--color-accent-foreground)]" />
          </span>
          <span className="text-xl font-heading tracking-wide text-[var(--color-text-inverse)]">Quantify</span>
        </Link>

        {/* Links */}
        <div className="flex items-center gap-1.5">
          {NAV.map(({ href, label }) => {
            const active = path === href;
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "px-5 py-2 rounded-full text-sm font-medium tracking-wide transition-all duration-500",
                  active
                    ? "bg-[var(--color-cta)]/10 text-[var(--color-cta)]"
                    : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:bg-[var(--color-surface)]/10"
                )}
              >
                {label}
              </Link>
            );
          })}
        </div>

        <div className="ml-auto flex items-center gap-4 pl-5 border-l border-[var(--border)]">

          {loggedIn ? (
            <>
              <Link href="/account" className="flex items-center" aria-label="Account">
                <div className="h-9 w-9 rounded-full bg-[var(--color-surface-raised)] border border-[var(--border)] flex items-center justify-center text-[var(--color-text-inverse)] font-semibold">
                  {initial ?? "U"}
                </div>
              </Link>
              <button
                onClick={logout}
                className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-danger)] transition-all duration-300"
              >
                <LogOut size={18} strokeWidth={1.5} />
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] transition-all duration-300">
                Sign In
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium bg-[var(--color-text)] text-[var(--color-on-text)] hover:bg-[var(--color-surface)] shadow-lg transition-all duration-300"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* ── Mobile top bar ───────────────────────────────────── */}
      <div className="md:hidden flex items-center justify-between w-full rounded-[1.5rem] bg-[var(--color-overlay)] border border-[var(--border)] px-4 py-2.5 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,0,0,0.35)] pointer-events-auto">
        <Link href="/" className="flex items-center gap-3">
          <span className="w-8 h-8 rounded-full gradient-accent flex items-center justify-center">
            <TrendingUp size={16} strokeWidth={2.5} className="text-[var(--color-accent-foreground)]" />
          </span>
          <span className="text-lg font-heading text-[var(--color-text-inverse)] tracking-wide">Quantify</span>
        </Link>
        <button
          aria-label="Open menu"
          onClick={() => setOpen(true)}
          className="p-2.5 rounded-full border border-[var(--border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-inverse)] hover:border-[var(--border-bright)] hover:bg-[var(--color-surface)]/10 transition-all"
        >
          <Menu size={20} strokeWidth={1.5} />
        </button>
      </div>

      {/* ── Mobile drawer ────────────────────────────────────── */}
      {open && (
        <div className="fixed inset-0 z-60 pointer-events-auto">
          <div
            className="absolute inset-0 bg-[var(--color-overlay)] backdrop-blur-md transition-opacity"
            onClick={() => setOpen(false)}
          />
          <div className="absolute top-0 right-0 h-full w-80 bg-[var(--color-surface)] border-l border-[var(--color-border)] p-8 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between mb-10">
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full gradient-accent flex items-center justify-center">
                  <TrendingUp size={16} strokeWidth={2.5} className="text-[var(--color-accent-foreground)]" />
                </span>
                <span className="text-xl font-heading text-[var(--color-text-inverse)] tracking-wide">Quantify</span>
              </div>
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="p-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] transition-colors"
              >
                <X size={20} strokeWidth={1.5} />
              </button>
            </div>

            <nav className="flex flex-col gap-2">
              {NAV.map(({ href, label, icon: Icon }) => {
                const active = path === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
                    className={clsx(
                      "flex items-center gap-4 px-4 py-3.5 rounded-2xl text-base font-medium transition-all duration-300",
                      active
                        ? "bg-[var(--color-cta)]/10 text-[var(--color-cta)]"
                        : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:bg-[var(--color-surface)]/10"
                    )}
                  >
                    <Icon size={18} strokeWidth={1.5} />
                    {label}
                  </Link>
                );
              })}

              <div className="my-6 border-t border-[var(--color-border-subtle)]" />

              {loggedIn ? (
                <>
                  <Link
                    href="/account"
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-4 px-4 py-3.5 rounded-2xl text-base font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:bg-[var(--color-surface)]/10 transition-all duration-300"
                  >
                    <UserCircle size={18} strokeWidth={1.5} />
                    Account Settings
                  </Link>
                  <button
                    onClick={() => { setOpen(false); logout(); }}
                    className="flex items-center gap-4 px-4 py-3.5 rounded-2xl text-base font-medium text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 transition-all text-left duration-300"
                  >
                    <LogOut size={18} strokeWidth={1.5} />
                    Sign Out
                  </button>
                </>
              ) : (
                <div className="flex flex-col gap-3 mt-2">
                  <Link href="/login" onClick={() => setOpen(false)} className="flex items-center justify-center px-4 py-3 rounded-full text-sm font-medium text-[var(--color-text-inverse)] border border-[var(--border)] hover:bg-[var(--color-surface)]/10 transition-all duration-300">
                    Sign In
                  </Link>
                  <Link href="/signup" onClick={() => setOpen(false)} className="flex items-center justify-center gap-2 px-4 py-3 rounded-full text-sm font-medium bg-[var(--color-text)] text-[var(--color-on-text)] hover:bg-[var(--color-surface)] transition-all duration-300">
                    Get Started <Zap size={14} />
                  </Link>
                </div>
              )}
            </nav>
          </div>
        </div>
      )}
    </div>
  );
}
