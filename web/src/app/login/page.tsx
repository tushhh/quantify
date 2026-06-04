"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TrendingUp, ArrowLeft, Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.auth.login({ username: form.username, password: form.password });
      localStorage.setItem("token", res.access_token);
      // notify other components (persistent layout) about auth change
      try { window.dispatchEvent(new Event('auth')); } catch {}
      router.push("/dashboard");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[100svh] flex items-start justify-center px-4 pt-16 pb-16">
      <div className="absolute top-16 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[var(--color-accent)]/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md mt-2">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-inverse)] transition-colors mb-6">
          <ArrowLeft size={14} />
          Back to home
        </Link>

        <div className="rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] p-8 shadow-2xl shadow-black/40">
          <div className="flex justify-center mb-6">
            <div className="w-14 h-14 rounded-2xl bg-[var(--color-accent)] flex items-center justify-center shadow-lg shadow-[var(--color-accent)]/30">
              <TrendingUp size={28} className="text-[var(--color-text-inverse)]" />
            </div>
          </div>

          <h1 className="text-2xl font-black text-center text-[var(--color-text-inverse)] mb-1">Welcome Back</h1>
          <p className="text-center text-[var(--color-text-muted)] text-sm mb-8">Log in to your trading home</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Username</label>
              <input
                required
                type="text"
                autoComplete="username"
                placeholder="Enter your username"
                className="w-full mt-1.5 bg-[var(--color-surface-raised)] border border-[var(--color-border)] rounded-xl px-4 py-3 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]/50 focus:ring-1 focus:ring-[var(--color-accent)]/25 transition-all"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Password</label>
              <div className="relative mt-1.5">
                <input
                  required
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  className="w-full bg-[var(--color-surface-raised)] border border-[var(--color-border)] rounded-xl px-4 py-3 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]/50 focus:ring-1 focus:ring-[var(--color-accent)]/25 transition-all pr-12"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text-inverse)] transition-colors"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-[var(--color-danger)] text-sm bg-[var(--color-danger-subtle)] p-3 rounded-xl border border-[var(--color-danger)]/20">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-[var(--color-text-inverse)] font-semibold py-3.5 rounded-xl transition-colors disabled:opacity-50"
            >
              {loading ? "Logging in..." : "Log In"}
            </button>
          </form>

          <p className="text-center text-sm text-[var(--color-text-muted)] mt-6">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="text-[var(--color-accent)] hover:text-[var(--color-accent-hover)] font-medium transition-colors">
              Sign up free
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
