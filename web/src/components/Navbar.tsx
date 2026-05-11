"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, BarChart2, Globe, Zap, UserCircle, Menu, X } from "lucide-react";
import clsx from "clsx";
import { useState } from "react";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: Zap },
  { href: "/backtest",   label: "Backtest",   icon: TrendingUp },
  { href: "/strategies", label: "Strategies", icon: BarChart2 },
  { href: "/universe",   label: "Universe",   icon: Globe },
];

export function Navbar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* ── Desktop top nav ───────────────────────────────── */}
      <nav className="hidden md:flex sticky top-0 left-0 right-0 z-50 h-14 items-center px-6 gap-8 border-b border-white/10 bg-[rgba(255,255,255,0.04)] backdrop-blur-md">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          <span className="relative w-8 h-8 rounded-lg flex items-center justify-center shadow-lg transition-shadow">
            <span className="absolute -left-2 -top-2 w-2.5 h-2.5 rounded-full bg-[var(--color-accent)] shadow-[0_0_12px_rgba(0,212,255,0.25)]" />
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-secondary)] flex items-center justify-center shadow-lg shadow-[rgba(0,212,255,0.12)] group-hover:shadow-[0_0_20px_rgba(0,212,255,0.18)] transition-shadow">
              <TrendingUp size={16} className="text-white" />
            </span>
          </span>
          <span className="font-bold tracking-tight text-white text-sm">Quantify</span>
        </Link>

        {/* Links */}
        <div className="flex items-center gap-3 uppercase tracking-widest text-xs">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                "px-3 py-1 rounded-md font-medium transition-all",
                path === href
                  ? "text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]"
                  : "text-slate-300 hover:text-[var(--color-accent)]"
              )}
            >
              {label}
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className="text-[10px] text-slate-300 bg-transparent px-2.5 py-1 rounded-full border border-white/6">
            Paper Trading
          </span>
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/40 animate-pulse" />
          <Link href="/account" className="text-sm text-slate-300 hover:text-white px-3 py-1.5 rounded-md">Account</Link>
          <Link href="/signup" className="ml-2 inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold bg-[var(--color-accent)] text-[#02121a] shadow-md hover:shadow-[0_8px_30px_rgba(0,212,255,0.12)]">
            Sign up
          </Link>
        </div>
      </nav>

      {/* ── Mobile top bar with hamburger ─────────────────── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 justify-between bg-[rgba(255,255,255,0.02)] backdrop-blur-md border-b border-white/6">
        <Link href="/" className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-secondary)] flex items-center justify-center shadow-sm">
            <TrendingUp size={16} className="text-white" />
          </span>
          <span className="font-bold text-sm">Quantify</span>
        </Link>
        <button aria-label="Open menu" onClick={() => setOpen(true)} className="p-2 rounded-md bg-transparent">
          <Menu size={20} className="text-slate-300" />
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-60">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <div className="absolute top-0 right-0 h-full w-72 glass p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-secondary)] flex items-center justify-center shadow-sm">
                  <TrendingUp size={16} className="text-white" />
                </span>
                <span className="font-bold">Quantify</span>
              </div>
              <button aria-label="Close menu" onClick={() => setOpen(false)} className="p-2 rounded-md">
                <X size={18} className="text-slate-300" />
              </button>
            </div>
            <nav className="flex flex-col gap-3">
              {NAV.map(({ href, label }) => (
                <Link key={href} href={href} onClick={() => setOpen(false)} className="py-2 text-lg text-slate-100">{label}</Link>
              ))}
              <Link href="/account" onClick={() => setOpen(false)} className="py-2 text-lg text-slate-100">Account</Link>
            </nav>
            <div className="mt-6">
              <Link href="/signup" onClick={() => setOpen(false)} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--color-accent)] text-[#02121a]">Sign up</Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
