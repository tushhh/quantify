"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { TrendingUp, BarChart2, Globe, Zap, Menu, X, LogOut, UserCircle, LayoutDashboard, Sparkles } from "lucide-react";
import clsx from "clsx";
import { useState, useEffect } from "react";

const NAV = [
  { href: "/dashboard",  label: "Dashboard",  icon: LayoutDashboard },
  { href: "/backtest",   label: "Backtest",   icon: TrendingUp },
  { href: "/screener",   label: "Screener",   icon: Sparkles },
  { href: "/strategies", label: "Strategies", icon: BarChart2 },
  { href: "/universe",   label: "Universe",   icon: Globe },
];

export function Navbar() {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(!!localStorage.getItem("token"));
  }, [path]);

  const logout = () => {
    localStorage.removeItem("token");
    setLoggedIn(false);
    router.push("/");
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-center w-full px-4 pt-4 pointer-events-none">
      {/* ── Desktop nav ─────────────────────────────────────── */}
      <nav className="hidden md:flex items-center justify-between w-full max-w-7xl px-5 py-3 rounded-[1.5rem] bg-[rgba(5,7,12,0.82)] border border-[var(--border)] shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-2xl pointer-events-auto">

        {/* Brand */}
        <Link href="/" className="flex items-center gap-3 shrink-0 group mr-5 transition-opacity hover:opacity-80">
          <span className="w-8 h-8 rounded-full gradient-accent flex items-center justify-center shadow-lg shadow-[var(--color-cta)]/20">
            <TrendingUp size={16} strokeWidth={2.5} className="text-[#050505]" />
          </span>
          <span className="text-xl font-heading tracking-wide text-white">Quantify</span>
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
                    ? "bg-[rgba(212,175,55,0.1)] text-[var(--color-cta)]"
                    : "text-slate-400 hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
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
              <Link
                href="/account"
                className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-all duration-300"
              >
                <UserCircle size={18} strokeWidth={1.5} />
              </Link>
              <button
                onClick={logout}
                className="flex items-center gap-2 text-sm text-slate-400 hover:text-[var(--color-danger)] transition-all duration-300"
              >
                <LogOut size={18} strokeWidth={1.5} />
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm font-medium text-slate-400 hover:text-white transition-all duration-300">
                Sign In
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium bg-[var(--color-text)] text-[#050505] hover:bg-white shadow-lg transition-all duration-300"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* ── Mobile top bar ───────────────────────────────────── */}
      <div className="md:hidden flex items-center justify-between w-full rounded-[1.5rem] bg-[rgba(5,7,12,0.82)] border border-[var(--border)] px-4 py-2.5 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,0,0,0.35)] pointer-events-auto">
        <Link href="/" className="flex items-center gap-3">
          <span className="w-8 h-8 rounded-full gradient-accent flex items-center justify-center">
            <TrendingUp size={16} strokeWidth={2.5} className="text-[#050505]" />
          </span>
          <span className="text-lg font-heading text-white tracking-wide">Quantify</span>
        </Link>
        <button
          aria-label="Open menu"
          onClick={() => setOpen(true)}
          className="p-2.5 rounded-full border border-[var(--border)] text-slate-300 hover:text-white hover:border-[var(--border-bright)] hover:bg-white/[0.04] transition-all"
        >
          <Menu size={20} strokeWidth={1.5} />
        </button>
      </div>

      {/* ── Mobile drawer ────────────────────────────────────── */}
      {open && (
        <div className="fixed inset-0 z-60 pointer-events-auto">
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-md transition-opacity"
            onClick={() => setOpen(false)}
          />
          <div className="absolute top-0 right-0 h-full w-80 bg-[var(--surface)] border-l border-[var(--border)] p-8 shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between mb-10">
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full gradient-accent flex items-center justify-center">
                  <TrendingUp size={16} strokeWidth={2.5} className="text-[#050505]" />
                </span>
                <span className="text-xl font-heading text-white tracking-wide">Quantify</span>
              </div>
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="p-2 text-slate-400 hover:text-white transition-colors"
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
                        ? "bg-[rgba(212,175,55,0.1)] text-[var(--color-cta)]"
                        : "text-slate-400 hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
                    )}
                  >
                    <Icon size={18} strokeWidth={1.5} />
                    {label}
                  </Link>
                );
              })}

              <div className="my-6 border-t border-[rgba(255,255,255,0.05)]" />

              {loggedIn ? (
                <>
                  <Link
                    href="/account"
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-4 px-4 py-3.5 rounded-2xl text-base font-medium text-slate-400 hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-all duration-300"
                  >
                    <UserCircle size={18} strokeWidth={1.5} />
                    Account Settings
                  </Link>
                  <button
                    onClick={() => { setOpen(false); logout(); }}
                    className="flex items-center gap-4 px-4 py-3.5 rounded-2xl text-base font-medium text-[var(--color-danger)] hover:bg-[rgba(224,122,95,0.1)] transition-all text-left duration-300"
                  >
                    <LogOut size={18} strokeWidth={1.5} />
                    Sign Out
                  </button>
                </>
              ) : (
                <div className="flex flex-col gap-3 mt-2">
                  <Link href="/login" onClick={() => setOpen(false)} className="flex items-center justify-center px-4 py-3 rounded-full text-sm font-medium text-white border border-[var(--border)] hover:bg-[rgba(255,255,255,0.05)] transition-all duration-300">
                    Sign In
                  </Link>
                  <Link href="/signup" onClick={() => setOpen(false)} className="flex items-center justify-center gap-2 px-4 py-3 rounded-full text-sm font-medium bg-[var(--color-text)] text-[#050505] hover:bg-white transition-all duration-300">
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
