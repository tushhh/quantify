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
      <nav className="hidden md:flex sticky top-0 left-0 right-0 z-50 h-14 items-center px-6 gap-8 border-b border-slate-700 bg-slate-900/90 backdrop-blur-md">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          <span className="relative w-8 h-8 rounded-lg flex items-center justify-center shadow-sm">
            <span className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm group-hover:bg-blue-500 transition-colors">
              <TrendingUp size={16} className="text-white" />
            </span>
          </span>
          <span className="font-bold tracking-tight text-slate-100 text-sm">Quantify</span>
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
                  ? "text-blue-400 border-b-2 border-blue-500"
                  : "text-slate-400 hover:text-blue-400"
              )}
            >
              {label}
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className="text-[10px] text-slate-400 bg-transparent px-2.5 py-1 rounded-full border border-slate-700">
            Paper Trading
          </span>
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <Link href="/account" className="text-sm text-slate-300 hover:text-white px-3 py-1.5 rounded-md">Account</Link>
          <Link href="/signup" className="ml-2 inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold bg-blue-600 text-white shadow-sm hover:bg-blue-700 transition-colors">
            Sign up
          </Link>
        </div>
      </nav>

      {/* ── Mobile top bar with hamburger ─────────────────── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 justify-between bg-slate-900/90 backdrop-blur-md border-b border-slate-700">
        <Link href="/" className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm">
            <TrendingUp size={16} className="text-white" />
          </span>
          <span className="font-bold text-sm text-slate-100">Quantify</span>
        </Link>
        <button aria-label="Open menu" onClick={() => setOpen(true)} className="p-2 rounded-md bg-transparent text-slate-300">
          <Menu size={20} />
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-60">
          <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="absolute top-0 right-0 h-full w-72 bg-slate-800 border-l border-slate-700 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm">
                  <TrendingUp size={16} className="text-white" />
                </span>
                <span className="font-bold text-slate-100">Quantify</span>
              </div>
              <button aria-label="Close menu" onClick={() => setOpen(false)} className="p-2 rounded-md text-slate-400 hover:text-slate-200">
                <X size={18} />
              </button>
            </div>
            <nav className="flex flex-col gap-3">
              {NAV.map(({ href, label }) => (
                <Link key={href} href={href} onClick={() => setOpen(false)} className="py-2 text-lg text-slate-300 hover:text-blue-400">{label}</Link>
              ))}
              <Link href="/account" onClick={() => setOpen(false)} className="py-2 text-lg text-slate-300 hover:text-blue-400">Account</Link>
            </nav>
            <div className="mt-6">
              <Link href="/signup" onClick={() => setOpen(false)} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-600 text-white font-semibold">Sign up</Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
