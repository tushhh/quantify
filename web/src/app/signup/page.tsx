"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TrendingUp, Send, ArrowLeft, Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";

export default function SignUpPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", password: "", telegram: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [showPopup, setShowPopup] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Register
      await api.auth.register({
        username: form.username,
        password: form.password,
        telegram_username: form.telegram || null,
      });
      // Auto-login
      const res = await api.auth.login({ username: form.username, password: form.password });
      localStorage.setItem("token", res.access_token);
      
      if (form.telegram) {
        setShowPopup(true);
      } else {
        router.push("/portfolio");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[100svh] flex items-start justify-center px-4 pt-16 pb-16">
      <div className="absolute top-16 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[var(--color-cta)]/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md mt-2">
        {/* Back to home */}
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] transition-colors mb-6">
          <ArrowLeft size={14} />
          Back to home
        </Link>

        <div className="rounded-2xl bg-[var(--color-surface)] border border-[var(--border)] p-8 shadow-2xl shadow-[var(--color-bg)]/20">
          {/* Logo */}
          <div className="flex justify-center mb-6">
            <div className="w-14 h-14 rounded-2xl bg-[var(--color-cta)] flex items-center justify-center shadow-lg shadow-[var(--color-cta)]/30">
              <TrendingUp size={28} className="text-[var(--color-text-inverse)]" />
            </div>
          </div>

          <h1 className="text-2xl font-black text-center text-[var(--color-text-inverse)] mb-1">Create Your Account</h1>
          <p className="text-center text-[var(--color-text-muted)] text-sm mb-8">Start trading with ML-powered predictions</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Username</label>
              <input
                required
                type="text"
                autoComplete="username"
                placeholder="Choose a username"
                className="w-full mt-1.5 bg-[var(--color-surface-raised)] border border-[var(--border)] rounded-xl px-4 py-3 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]/50 focus:ring-1 focus:ring-[var(--color-accent)]/25 transition-all"
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
                  autoComplete="new-password"
                  placeholder="Create a password"
                  className="w-full bg-[var(--color-surface-raised)] border border-[var(--border)] rounded-xl px-4 py-3 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]/50 focus:ring-1 focus:ring-[var(--color-accent)]/25 transition-all pr-12"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider flex items-center gap-2">
                <Send size={10} className="text-[var(--color-cta)]" /> Telegram Username
                <span className="text-[var(--color-text-muted)] normal-case font-normal">(optional)</span>
              </label>
              <input
                type="text"
                placeholder="@yourusername"
                className="w-full mt-1.5 bg-[var(--color-surface-raised)] border border-[var(--border)] rounded-xl px-4 py-3 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]/50 focus:ring-1 focus:ring-[var(--color-accent)]/25 transition-all"
                value={form.telegram}
                onChange={(e) => setForm({ ...form, telegram: e.target.value })}
              />
              <p className="text-[11px] text-[var(--color-text-muted)] mt-1.5">We&apos;ll send buy/sell alerts directly to your Telegram.</p>
            </div>

            {error && (
              <div className="text-[var(--color-danger)] text-sm bg-[var(--color-danger)]/10 p-3 rounded-xl border border-[var(--color-danger)]/20">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--color-cta)] hover:bg-[var(--color-accent)] text-[var(--color-text-inverse)] font-semibold py-3.5 rounded-xl transition-colors disabled:opacity-50 disabled:hover:shadow-none"
            >
              {loading ? "Creating Account..." : "Create Account"}
            </button>
          </form>

          <p className="text-center text-sm text-[var(--color-text-muted)] mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-[var(--color-cta)] hover:text-[var(--color-accent)] font-medium transition-colors">
              Log in
            </Link>
          </p>
        </div>
      </div>

      {/* Telegram Activation Popup */}
      {showPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--color-bg)]/80 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md bg-[var(--color-surface)] border border-[var(--border)] rounded-2xl shadow-2xl p-8 relative">
            <div className="w-16 h-16 bg-[var(--color-cta)]/10 border border-[var(--color-cta)]/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <Send size={28} className="text-[var(--color-cta)]" />
            </div>
            
            <h2 className="text-2xl font-black text-[var(--color-text-inverse)] text-center mb-3">Activate Alerts</h2>
            
            <p className="text-[var(--color-text-muted)] text-center text-sm mb-6 leading-relaxed">
              Your account is created! To receive instant buy/sell alerts, connect your Telegram account to the Quantify bot.
            </p>

            <div className="bg-[var(--color-surface-raised)] border border-[var(--border)] rounded-xl p-4 mb-6">
              <ol className="list-decimal list-inside text-sm text-[var(--color-text-primary)] space-y-2 font-medium">
                <li>Open Telegram using the button below.</li>
                <li>Tap <span className="text-[var(--color-cta)] font-mono text-xs bg-[var(--color-cta)]/10 px-1.5 py-0.5 rounded">START</span> in the bot chat.</li>
                <li>Return home to confirm the connection.</li>
              </ol>
            </div>

            <div className="flex flex-col gap-3">
              <a 
                href="https://t.me/QuantifyAlertbot?start=start" 
                target="_blank" 
                rel="noreferrer"
                className="w-full flex items-center justify-center gap-2 bg-[var(--color-cta)] hover:bg-[var(--color-accent)] text-[var(--color-text-inverse)] font-semibold py-3.5 rounded-xl transition-colors shadow-sm"
              >
                <Send size={18} /> Open @QuantifyAlertbot
              </a>
              <button 
                onClick={() => router.push("/portfolio")}
                className="w-full text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] font-semibold py-3 text-sm transition-colors"
              >
                Go home
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
