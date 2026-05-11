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
        router.push("/dashboard");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-[#070b14]">
      {/* Background effects */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-to-b from-blue-600/10 via-violet-600/8 to-transparent rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Back to home */}
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-white transition-colors mb-8">
          <ArrowLeft size={14} />
          Back to home
        </Link>

        <div className="rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-sm p-8 shadow-2xl shadow-black/40">
          {/* Logo */}
          <div className="flex justify-center mb-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
              <TrendingUp size={28} className="text-white" />
            </div>
          </div>

          <h1 className="text-2xl font-black text-center text-white mb-1">Create Your Account</h1>
          <p className="text-center text-slate-500 text-sm mb-8">Start trading with AI-powered predictions</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Username</label>
              <input
                required
                type="text"
                autoComplete="username"
                placeholder="Choose a username"
                className="w-full mt-1.5 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25 transition-all"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Password</label>
              <div className="relative mt-1.5">
                <input
                  required
                  type={showPw ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Create a password"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25 transition-all pr-12"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <Send size={10} className="text-blue-400" /> Telegram Username
                <span className="text-slate-600 normal-case font-normal">(optional)</span>
              </label>
              <input
                type="text"
                placeholder="@yourusername"
                className="w-full mt-1.5 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25 transition-all"
                value={form.telegram}
                onChange={(e) => setForm({ ...form, telegram: e.target.value })}
              />
              <p className="text-[11px] text-slate-600 mt-1.5">We&apos;ll send buy/sell alerts directly to your Telegram.</p>
            </div>

            {error && (
              <div className="text-rose-400 text-sm bg-rose-500/10 p-3 rounded-xl border border-rose-500/20">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white font-bold py-3.5 rounded-xl transition-all hover:shadow-lg hover:shadow-blue-500/20 active:scale-[0.98] disabled:opacity-50 disabled:hover:shadow-none"
            >
              {loading ? "Creating Account..." : "Create Account"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-blue-400 hover:text-blue-300 font-medium transition-colors">
              Log in
            </Link>
          </p>
        </div>
      </div>

      {/* Telegram Activation Popup */}
      {showPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md bg-[#0e1525] border border-white/10 rounded-2xl shadow-2xl p-8 relative">
            <div className="w-16 h-16 bg-blue-500/10 border border-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <Send size={28} className="text-blue-400" />
            </div>
            
            <h2 className="text-2xl font-black text-white text-center mb-3">Activate Alerts</h2>
            
            <p className="text-slate-400 text-center text-sm mb-6 leading-relaxed">
              Your account is created! To receive instant buy/sell alerts, you must connect your device to our Telegram bot.
            </p>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4 mb-6">
              <ol className="list-decimal list-inside text-sm text-slate-300 space-y-2 font-medium">
                <li>Click the button below to open Telegram.</li>
                <li>Tap <span className="text-blue-400 font-mono text-xs bg-blue-500/10 px-1.5 py-0.5 rounded">START</span> at the bottom of the chat.</li>
                <li>Return to the dashboard.</li>
              </ol>
            </div>

            <div className="flex flex-col gap-3">
              <a 
                href="https://t.me/QuantifyAlertbot?start=start" 
                target="_blank" 
                rel="noreferrer"
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white font-bold py-3.5 rounded-xl transition-all shadow-lg hover:shadow-blue-500/20 active:scale-95"
              >
                <Send size={18} /> Open @QuantifyAlertbot
              </a>
              <button 
                onClick={() => router.push("/dashboard")}
                className="w-full text-slate-500 hover:text-white font-semibold py-3 text-sm transition-colors"
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
