"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, BarChart2, Globe, Zap, UserCircle } from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: Zap },
  { href: "/backtest",   label: "Backtest",   icon: TrendingUp },
  { href: "/strategies", label: "Strategies", icon: BarChart2 },
  { href: "/universe",   label: "Universe",   icon: Globe },
];

export function Navbar() {
  const path = usePathname();

  // Hide navbar on the landing page
  if (path === "/") return null;

  return (
    <>
      {/* ── Desktop top nav ───────────────────────────────── */}
      <nav className="hidden md:flex fixed top-0 left-0 right-0 z-50 h-14 items-center px-6 gap-8 border-b border-[#1e2d4a] bg-[#070b14]/90 backdrop-blur-md">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/25 group-hover:shadow-blue-500/40 transition-shadow">
            <TrendingUp size={16} className="text-white" />
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
          <Link
            href="/account"
            className={clsx(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
              path === "/account"
                ? "bg-blue-500/15 text-blue-400"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
            )}
          >
            <UserCircle size={15} />
            Account
          </Link>
        </div>
      </nav>

      {/* ── Mobile bottom nav ─────────────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 h-16 flex items-center justify-around border-t border-[#1e2d4a] bg-[#070b14]/95 backdrop-blur-md">
        {[...NAV, { href: "/account", label: "Account", icon: UserCircle }].map(({ href, label, icon: Icon }) => (
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
