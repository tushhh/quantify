"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, BarChart2, Globe, Settings, Zap } from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/",           label: "Dashboard",  icon: Zap },
  { href: "/backtest",   label: "Backtest",   icon: TrendingUp },
  { href: "/strategies", label: "Strategies", icon: BarChart2 },
  { href: "/universe",   label: "Universe",   icon: Globe },
];

export function Navbar() {
  const path = usePathname();

  return (
    <>
      {/* ── Desktop top nav ───────────────────────────────── */}
      <nav className="hidden md:flex fixed top-0 left-0 right-0 z-50 h-14 items-center px-6 gap-8 border-b border-[#1e2d4a] bg-[#070b14]/90 backdrop-blur-md">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="w-7 h-7 rounded-md bg-blue-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
            <TrendingUp size={15} className="text-white" />
          </span>
          <span className="font-bold tracking-tight text-white text-sm">Quantify</span>
        </Link>

        {/* Links */}
        <div className="flex items-center gap-1">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                path === href
                  ? "bg-blue-500/15 text-blue-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <Icon size={13} />
              {label}
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-slate-500 bg-slate-800/60 px-2.5 py-1 rounded-full border border-[#1e2d4a]">
            Paper Trading
          </span>
          <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/50 animate-pulse" />
        </div>
      </nav>

      {/* ── Mobile bottom nav ─────────────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 h-16 flex items-center justify-around border-t border-[#1e2d4a] bg-[#070b14]/95 backdrop-blur-md">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex flex-col items-center gap-1 px-4 py-1 rounded-lg transition-all",
              path === href ? "text-blue-400" : "text-slate-500"
            )}
          >
            <Icon size={18} />
            <span className="text-[10px] font-medium">{label}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
