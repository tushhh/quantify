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
    <>
      {/* ── Desktop nav ─────────────────────────────────────── */}
      <nav className="hidden md:flex sticky top-0 left-0 right-0 z-50 h-16 items-center px-8 gap-8 border-b-2 border-[var(--color-cta)] bg-black font-mono">

        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group mr-2">
          <span className="w-8 h-8 gradient-accent flex items-center justify-center border border-[var(--color-cta)]">
            <TrendingUp size={15} className="text-black" />
          </span>
          <span className="font-bold tracking-widest text-[var(--color-cta)] text-sm font-heading">QUANTIFY</span>
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
                  "flex items-center gap-2 px-4 py-2 text-xs font-bold tracking-widest transition-all uppercase border",
                  active
                    ? "bg-[var(--color-cta)] text-black border-[var(--color-cta)]"
                    : "text-slate-400 border-transparent hover:text-[var(--color-cta)] hover:border-[var(--color-cta)]"
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
          <div className="flex items-center gap-2 px-3 py-1 border border-[var(--border)] bg-black text-[10px] text-slate-400 font-bold tracking-widest uppercase">
            <span className="w-1.5 h-1.5 bg-[var(--color-cta)] animate-pulse" />
            Paper Trading
          </div>

          {loggedIn ? (
            <>
              <Link
                href="/account"
                className="flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-[var(--color-cta)] px-3 py-1.5 uppercase tracking-widest transition-all"
              >
                <UserCircle size={14} />
                ACCOUNT
              </Link>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-[var(--color-danger)] px-3 py-1.5 uppercase tracking-widest transition-all"
              >
                <LogOut size={13} />
                LOGOUT
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-xs font-bold text-slate-400 hover:text-white px-3 py-1.5 uppercase tracking-widest transition-all">
                LOG IN
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold gradient-accent text-black uppercase tracking-widest border border-[var(--color-cta)] transition-all hover:bg-black hover:text-[var(--color-cta)]"
              >
                INIT <Zap size={11} />
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* ── Mobile top bar ───────────────────────────────────── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 justify-between bg-black border-b-2 border-[var(--color-cta)]">
        <Link href="/" className="flex items-center gap-2">
          <span className="w-8 h-8 gradient-accent flex items-center justify-center border border-[var(--color-cta)]">
            <TrendingUp size={15} className="text-black" />
          </span>
          <span className="font-bold text-sm text-[var(--color-cta)] font-heading tracking-widest">QUANTIFY</span>
        </Link>
        <button
          aria-label="Open menu"
          onClick={() => setOpen(true)}
          className="p-2 text-[var(--color-cta)] hover:bg-[var(--color-cta)] hover:text-black transition-all border border-transparent hover:border-[var(--color-cta)]"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* ── Mobile drawer ────────────────────────────────────── */}
      {open && (
        <div className="fixed inset-0 z-60 font-mono">
          <div
            className="absolute inset-0 bg-black/90 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="absolute top-0 right-0 h-full w-72 bg-black border-l-2 border-[var(--color-cta)] p-6 animate-slide-in-right">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 gradient-accent flex items-center justify-center border border-[var(--color-cta)]">
                  <TrendingUp size={15} className="text-black" />
                </span>
                <span className="font-bold text-[var(--color-cta)] font-heading tracking-widest">QUANTIFY</span>
              </div>
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="p-1.5 text-[var(--color-cta)] hover:bg-[var(--color-cta)] hover:text-black transition-all border border-transparent hover:border-[var(--color-cta)]"
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
                      "flex items-center gap-3 px-3 py-3 text-sm font-bold transition-all uppercase tracking-widest border",
                      active
                        ? "bg-[var(--color-cta)] text-black border-[var(--color-cta)]"
                        : "text-slate-400 border-transparent hover:text-[var(--color-cta)] hover:border-[var(--color-cta)]"
                    )}
                  >
                    <Icon size={16} />
                    {label}
                  </Link>
                );
              })}

              <div className="my-4 border-t-2 border-[var(--border)]" />

              {loggedIn ? (
                <>
                  <Link
                    href="/account"
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-3 px-3 py-3 text-sm font-bold text-slate-400 hover:text-[var(--color-cta)] hover:border hover:border-[var(--color-cta)] transition-all uppercase tracking-widest"
                  >
                    <UserCircle size={16} />
                    ACCOUNT
                  </Link>
                  <button
                    onClick={() => { setOpen(false); logout(); }}
                    className="flex items-center gap-3 px-3 py-3 text-sm font-bold text-[var(--color-danger)] border border-transparent hover:border-[var(--color-danger)] hover:bg-black transition-all text-left uppercase tracking-widest"
                  >
                    <LogOut size={16} />
                    LOGOUT
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login" onClick={() => setOpen(false)} className="flex items-center gap-3 px-3 py-3 text-sm font-bold text-slate-400 hover:text-[var(--color-cta)] hover:border hover:border-[var(--color-cta)] transition-all uppercase tracking-widest">
                    LOG IN
                  </Link>
                  <Link href="/signup" onClick={() => setOpen(false)} className="flex items-center justify-center gap-2 px-3 py-3 text-sm font-bold gradient-accent text-black mt-2 uppercase tracking-widest border border-[var(--color-cta)] hover:bg-black hover:text-[var(--color-cta)]">
                    INIT <Zap size={12} />
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
