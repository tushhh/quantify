"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { TrendingUp, BarChart2, Globe, Zap, Menu, X, LogOut, UserCircle, LayoutDashboard } from "lucide-react";
import clsx from "clsx";
import { useState, useEffect } from "react";

const NAV = [
  { href: "/dashboard",  label: "Dashboard",  icon: LayoutDashboard },
  { href: "/backtest",   label: "Backtest",   icon: TrendingUp },
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
    <>
      {/* ── Desktop nav ─────────────────────────────────────── */}
      <nav className="hidden md:flex sticky top-0 left-0 right-0 z-50 h-16 items-center px-8 gap-8 border-b border-[var(--border)] bg-[var(--bg)]/95 backdrop-blur-md">

        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group mr-2">
          <span className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center shadow-sm shadow-blue-900/40 group-hover:opacity-90 transition-opacity">
            <TrendingUp size={15} className="text-white" />
          </span>
          <span className="font-bold tracking-tight text-white text-sm">Quantify</span>
        </Link>

        {/* Links */}
        <div className="flex items-center gap-2.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = path === href;
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold tracking-wider transition-all",
                  active
                    ? "bg-blue-500/15 text-blue-200 border border-blue-500/30 shadow-sm shadow-blue-500/10"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                )}
              >
                <Icon size={12} />
                {label}
              </Link>
            );
          })}
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* Status indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[var(--border)] bg-[var(--surface)] text-[10px] text-slate-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Paper Trading
          </div>

          {loggedIn ? (
            <>
              <Link
                href="/account"
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/[0.04] transition-all"
              >
                <UserCircle size={14} />
                Account
              </Link>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-red-400 px-3 py-1.5 rounded-lg hover:bg-red-500/10 transition-all"
              >
                <LogOut size={13} />
                Logout
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg transition-all">
                Log in
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold gradient-accent text-white shadow-sm shadow-blue-900/30 hover:opacity-90 transition-opacity"
              >
                Sign up <Zap size={11} />
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* ── Mobile top bar ───────────────────────────────────── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 justify-between bg-[var(--bg)]/95 backdrop-blur-md border-b border-[var(--border)]">
        <Link href="/" className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
            <TrendingUp size={15} className="text-white" />
          </span>
          <span className="font-bold text-sm text-white">Quantify</span>
        </Link>
        <button
          aria-label="Open menu"
          onClick={() => setOpen(true)}
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.05] transition-all"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* ── Mobile drawer ────────────────────────────────────── */}
      {open && (
        <div className="fixed inset-0 z-60">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="absolute top-0 right-0 h-full w-72 bg-[var(--surface)] border-l border-[var(--border)] p-6 shadow-2xl animate-slide-in-right">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
                  <TrendingUp size={15} className="text-white" />
                </span>
                <span className="font-bold text-white">Quantify</span>
              </div>
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.05] transition-all"
              >
                <X size={18} />
              </button>
            </div>

            <nav className="flex flex-col gap-1">
              {NAV.map(({ href, label, icon: Icon }) => {
                const active = path === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
                    className={clsx(
                      "flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-all",
                      active
                        ? "bg-blue-500/15 text-blue-300 border border-blue-500/20"
                        : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
                    )}
                  >
                    <Icon size={16} />
                    {label}
                  </Link>
                );
              })}

              <div className="my-3 border-t border-[var(--border)]" />

              {loggedIn ? (
                <>
                  <Link
                    href="/account"
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all"
                  >
                    <UserCircle size={16} />
                    Account
                  </Link>
                  <button
                    onClick={() => { setOpen(false); logout(); }}
                    className="flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-all text-left"
                  >
                    <LogOut size={16} />
                    Logout
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login" onClick={() => setOpen(false)} className="flex items-center gap-3 px-3 py-3 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all">
                    Log in
                  </Link>
                  <Link href="/signup" onClick={() => setOpen(false)} className="flex items-center justify-center gap-2 px-3 py-3 rounded-xl text-sm font-semibold gradient-accent text-white mt-1">
                    Sign up <Zap size={12} />
                  </Link>
                </>
              )}
            </nav>
          </div>
        </div>
      )}
    </>
  );
}
