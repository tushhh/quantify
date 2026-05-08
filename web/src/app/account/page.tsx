"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UserCircle, Send, Lock, Check, AlertCircle, LogOut, Shield } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<{id: number, username: string, telegram_username: string | null} | null>(null);
  const [loading, setLoading] = useState(true);

  // Form states
  const [telegram, setTelegram] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Feedback
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const u = await api.auth.me();
      setUser(u);
      setTelegram(u.telegram_username || "");
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTelegram = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api.auth.update({ telegram_username: telegram || null });
      setUser(updated);
      setSuccess("Telegram username updated successfully!");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e: any) {
      setError(e.message || "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await api.auth.update({ new_password: newPassword });
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Password changed successfully!");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e: any) {
      setError(e.message || "Failed to change password");
    } finally {
      setSaving(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 pt-24 pb-24 md:pb-12 flex flex-col gap-6 animate-fade-in">
      <h1 className="text-3xl font-black text-white">Account Settings</h1>

      {/* Success/Error Feedback */}
      {success && (
        <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 text-emerald-400 text-sm font-medium animate-fade-in">
          <Check size={18} />
          {success}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-3 bg-rose-500/10 border border-rose-500/20 rounded-xl p-4 text-rose-400 text-sm font-medium animate-fade-in">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* Profile Card */}
      <Card className="bg-white/[0.02] border-white/5 p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-violet-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/20">
            <UserCircle className="text-white" size={32} />
          </div>
          <div>
            <p className="text-xl font-black text-white">{user.username}</p>
            <p className="text-sm text-slate-500">User ID: #{user.id}</p>
          </div>
        </div>
      </Card>

      {/* Telegram Settings */}
      <Card className="bg-white/[0.02] border-white/5 p-6">
        <h2 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <Send size={18} className="text-blue-400" />
          Telegram Alerts
        </h2>
        <p className="text-sm text-slate-500 mb-5">
          Connect your Telegram to receive automated buy/sell alerts when your trade holding period expires.
        </p>

        <div className="flex gap-3">
          <input
            type="text"
            placeholder="@yourusername"
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25 transition-all"
            value={telegram}
            onChange={(e) => setTelegram(e.target.value)}
          />
          <button
            onClick={handleSaveTelegram}
            disabled={saving}
            className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white font-bold px-6 py-3 rounded-xl transition-all hover:shadow-lg hover:shadow-blue-500/20 active:scale-95 disabled:opacity-50 shrink-0"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>

        {user.telegram_username && (
          <div className="mt-3 flex items-center gap-2 text-xs text-emerald-400">
            <Check size={12} />
            <span>Currently connected as <strong>{user.telegram_username}</strong></span>
          </div>
        )}
      </Card>

      {/* Change Password */}
      <Card className="bg-white/[0.02] border-white/5 p-6">
        <h2 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <Lock size={18} className="text-violet-400" />
          Change Password
        </h2>
        <p className="text-sm text-slate-500 mb-5">
          Update your account password. Must be at least 6 characters.
        </p>

        <form onSubmit={handleChangePassword} className="flex flex-col gap-4">
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">New Password</label>
            <input
              required
              type="password"
              placeholder="Enter new password"
              className="w-full mt-1.5 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/25 transition-all"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Confirm New Password</label>
            <input
              required
              type="password"
              placeholder="Confirm new password"
              className="w-full mt-1.5 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-600 outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/25 transition-all"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={saving || !newPassword || !confirmPassword}
            className="w-full bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 text-white font-bold py-3 rounded-xl transition-all hover:shadow-lg hover:shadow-violet-500/20 active:scale-[0.98] disabled:opacity-50"
          >
            {saving ? "Updating..." : "Update Password"}
          </button>
        </form>
      </Card>

      {/* Danger Zone */}
      <Card className="bg-rose-500/[0.02] border-rose-500/10 p-6">
        <h2 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <Shield size={18} className="text-rose-400" />
          Session
        </h2>
        <p className="text-sm text-slate-500 mb-5">
          Sign out of your account on this device.
        </p>
        <button
          onClick={logout}
          className="flex items-center gap-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-bold px-6 py-3 rounded-xl border border-rose-500/20 transition-all active:scale-95"
        >
          <LogOut size={16} />
          Sign Out
        </button>
      </Card>
    </div>
  );
}
