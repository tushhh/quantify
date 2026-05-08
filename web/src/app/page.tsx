"use client";

import { useEffect, useState } from "react";
import { Zap, Shield, AlertTriangle, Plus, Crosshair, X, Lock, User as UserIcon, Send } from "lucide-react";
import { api, PredictionItem, TrackedTrade } from "@/lib/api";
import { Card, Badge } from "@/components/ui";

export default function HomePage() {
  const [user, setUser] = useState<{username: string, telegram_username: string} | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authForm, setAuthForm] = useState({ username: "", password: "", telegram: "" });
  const [authError, setAuthError] = useState("");

  const [loadingPreds, setLoadingPreds] = useState(false);
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [trades, setTrades] = useState<TrackedTrade[]>([]);
  
  const [newTrade, setNewTrade] = useState({ symbol: "", shares: "", buy_price: "" });
  const [holdStrategy, setHoldStrategy] = useState<"ai" | "custom">("ai");
  const [customHoldDays, setCustomHoldDays] = useState("10");

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const u = await api.auth.me();
      setUser(u);
      loadTrades();
    } catch (e) {
      setUser(null);
    } finally {
      setLoadingAuth(false);
    }
  };

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    try {
      if (authMode === "register") {
        await api.auth.register({
          username: authForm.username,
          password: authForm.password,
          telegram_username: authForm.telegram || null
        });
      }
      // Login
      const res = await api.auth.login({ username: authForm.username, password: authForm.password });
      localStorage.setItem("token", res.access_token);
      await checkAuth();
    } catch (e: any) {
      setAuthError(e.message || "Authentication failed");
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    setTrades([]);
  };

  const loadTrades = async () => {
    try {
      const data = await api.trades.list();
      setTrades(data.filter(t => t.status === "active"));
    } catch (e) {
      console.error(e);
    }
  };

  const handlePredict = async () => {
    setLoadingPreds(true);
    try {
      const res = await api.predict.best(5);
      setPredictions(res.signals);
      if (res.signals.length > 0) {
        setNewTrade({ ...newTrade, symbol: res.signals[0].symbol });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPreds(false);
    }
  };

  const handleCreateTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTrade.symbol || !newTrade.shares || !newTrade.buy_price) return;
    try {
      await api.trades.create({
        symbol: newTrade.symbol,
        shares: parseFloat(newTrade.shares),
        buy_price: parseFloat(newTrade.buy_price),
        hold_days: holdStrategy === "ai" ? 5 : parseInt(customHoldDays)
      });
      setNewTrade({ symbol: "", shares: "", buy_price: "" });
      loadTrades();
    } catch (e) {
      console.error(e);
    }
  };

  const handleCloseTrade = async (id: string) => {
    try {
      await api.trades.close(id);
      loadTrades();
    } catch (e) {
      console.error(e);
    }
  };

  if (loadingAuth) return <div className="min-h-screen flex items-center justify-center text-slate-400">Loading Quantify AI...</div>;

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="max-w-md w-full p-8 bg-slate-900 border-white/10 shadow-2xl">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-blue-500/20 rounded-2xl flex items-center justify-center border border-blue-500/30">
              <Lock className="text-blue-400" size={32} />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-center text-white mb-2">
            {authMode === "login" ? "Welcome Back" : "Create Account"}
          </h2>
          <p className="text-center text-slate-400 text-sm mb-6">Secure access to your automated trading dashboard</p>
          
          <form onSubmit={handleAuth} className="flex flex-col gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Username</label>
              <input required type="text" className="w-full mt-1 bg-slate-950 border border-white/10 rounded-lg px-4 py-2.5 text-white" value={authForm.username} onChange={e => setAuthForm({...authForm, username: e.target.value})} />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Password</label>
              <input required type="password" className="w-full mt-1 bg-slate-950 border border-white/10 rounded-lg px-4 py-2.5 text-white" value={authForm.password} onChange={e => setAuthForm({...authForm, password: e.target.value})} />
            </div>
            
            {authMode === "register" && (
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase flex items-center gap-2">
                  <Send size={12} className="text-blue-400"/> Telegram Username (For Alerts)
                </label>
                <input type="text" placeholder="@yourusername" className="w-full mt-1 bg-slate-950 border border-white/10 rounded-lg px-4 py-2.5 text-white" value={authForm.telegram} onChange={e => setAuthForm({...authForm, telegram: e.target.value})} />
                <p className="text-[10px] text-slate-500 mt-1">We will send buy/sell alerts directly to your phone.</p>
              </div>
            )}

            {authError && <div className="text-rose-400 text-sm bg-rose-500/10 p-3 rounded border border-rose-500/20">{authError}</div>}
            
            <button type="submit" className="mt-2 w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all">
              {authMode === "login" ? "Login to Dashboard" : "Register & Start Trading"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-400 mt-6 cursor-pointer hover:text-white" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>
            {authMode === "login" ? "Don't have an account? Sign up" : "Already have an account? Login"}
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 flex flex-col gap-10 animate-fade-in text-slate-100">
      
      {/* Header */}
      <div className="flex justify-between items-center bg-slate-900 border border-white/10 p-4 rounded-2xl shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-500/20 rounded-full flex items-center justify-center border border-blue-500/30">
            <UserIcon className="text-blue-400" size={20} />
          </div>
          <div>
            <p className="font-bold text-white leading-none">{user.username}</p>
            <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
              <Send size={10} className="text-blue-400"/> {user.telegram_username ? `${user.telegram_username} connected` : "No Telegram connected"}
            </p>
          </div>
        </div>
        <button onClick={logout} className="text-sm font-semibold text-slate-400 hover:text-white transition-colors">Logout</button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        
        {/* ML Prediction Engine */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold flex items-center gap-2 text-white">
              <Crosshair className="text-blue-400" /> AI Predictions
            </h2>
            <button 
              onClick={handlePredict}
              disabled={loadingPreds}
              className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 px-6 rounded-xl shadow-[0_0_20px_rgba(59,130,246,0.3)] transition-all hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
            >
              {loadingPreds ? "Analyzing Markets..." : "Run AI Analysis"}
            </button>
          </div>
          
          <Card className="bg-slate-900 border-white/10 shadow-xl overflow-hidden min-h-[300px] flex flex-col">
            {predictions.length === 0 && !loadingPreds ? (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-3">
                <Zap size={48} className="opacity-20" />
                <p className="text-center px-8">Run analysis to see today's top algorithmically chosen stocks.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-0">
                <div className="grid grid-cols-4 px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-white/5 bg-black/20">
                  <div>Rank</div>
                  <div>Symbol</div>
                  <div>Signal</div>
                  <div className="text-right">AI Strength</div>
                </div>
                {predictions.map((p, i) => (
                  <div key={p.symbol} className="grid grid-cols-4 px-5 py-4 items-center hover:bg-white/5 border-b border-white/5 transition-colors cursor-pointer" onClick={() => setNewTrade({ ...newTrade, symbol: p.symbol })}>
                    <div className="font-mono text-slate-500">#{i + 1}</div>
                    <div className="font-bold text-white text-lg">{p.symbol}</div>
                    <div><Badge variant="blue" className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 uppercase">{p.side}</Badge></div>
                    <div className="text-right font-mono text-blue-400 font-bold">+{p.strength.toFixed(3)}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Trade Manager */}
        <div className="flex flex-col gap-4">
          <h2 className="text-2xl font-bold flex items-center gap-2 text-white">
            <Shield className="text-indigo-400" /> Active Portfolio
          </h2>
          
          {/* Log New Trade */}
          <Card className="bg-indigo-900/10 border-indigo-500/20 shadow-xl">
            <h3 className="text-sm font-semibold text-indigo-300 mb-4 flex items-center gap-2">
              <Plus size={16} /> Log a New Trade
            </h3>
            <form onSubmit={handleCreateTrade} className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Symbol</label>
                  <input required type="text" placeholder="e.g. AMD" className="w-full bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500 uppercase" value={newTrade.symbol} onChange={e => setNewTrade({...newTrade, symbol: e.target.value})} />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Shares</label>
                  <input required type="number" step="0.01" placeholder="10" className="w-full bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500" value={newTrade.shares} onChange={e => setNewTrade({...newTrade, shares: e.target.value})} />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Buy Price ($)</label>
                  <input required type="number" step="0.01" placeholder="150.25" className="w-full bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500" value={newTrade.buy_price} onChange={e => setNewTrade({...newTrade, buy_price: e.target.value})} />
                </div>
              </div>

              {/* Holding Strategy Decision */}
              <div className="p-4 rounded-xl border border-white/5 bg-black/20 flex flex-col gap-3">
                <p className="text-xs font-semibold text-slate-400 uppercase">Holding Strategy</p>
                
                <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${holdStrategy === "ai" ? "bg-indigo-500/10 border-indigo-500/30" : "border-white/5 hover:border-white/10"}`}>
                  <input type="radio" name="strategy" className="mt-1" checked={holdStrategy === "ai"} onChange={() => setHoldStrategy("ai")} />
                  <div>
                    <p className="text-sm font-bold text-white">Follow AI Advice (5 Days)</p>
                    <p className="text-xs text-slate-400 mt-0.5">The model predicts maximum returns on a 5-day horizon. We will alert you on Telegram when it's time to sell.</p>
                  </div>
                </label>

                <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${holdStrategy === "custom" ? "bg-indigo-500/10 border-indigo-500/30" : "border-white/5 hover:border-white/10"}`}>
                  <input type="radio" name="strategy" className="mt-1" checked={holdStrategy === "custom"} onChange={() => setHoldStrategy("custom")} />
                  <div className="w-full">
                    <p className="text-sm font-bold text-white">Custom Duration</p>
                    <p className="text-xs text-slate-400 mt-0.5 mb-2">Sell whenever you wish. Set an arbitrary timeline.</p>
                    {holdStrategy === "custom" && (
                      <input type="number" min="1" className="w-full max-w-[150px] bg-slate-950 border border-white/10 rounded-lg px-3 py-1.5 text-white outline-none focus:border-indigo-500 text-sm" value={customHoldDays} onChange={e => setCustomHoldDays(e.target.value)} />
                    )}
                  </div>
                </label>
              </div>

              <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3 rounded-xl transition-colors">
                Log Trade & Activate Alerts
              </button>
            </form>
          </Card>

          {/* Active Trades */}
          <div className="flex flex-col gap-3 mt-2">
            {trades.length === 0 ? (
              <div className="p-8 text-center rounded-xl border border-dashed border-white/10 text-slate-500 bg-white/5">
                No active positions being tracked.
              </div>
            ) : (
              trades.map(t => (
                <Card key={t.id} className="bg-slate-900 border-white/10 shadow-lg p-5 relative overflow-hidden group">
                  {t.alert && (
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-rose-500 to-orange-500 animate-pulse"></div>
                  )}
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-xl font-black text-white">{t.symbol}</h3>
                      <p className="text-sm text-slate-400">{t.shares} shares @ ${t.buy_price}</p>
                    </div>
                    <button onClick={() => handleCloseTrade(t.id)} className="text-slate-500 hover:text-rose-400 transition-colors bg-white/5 px-3 py-1.5 rounded-md hover:bg-rose-500/10 text-xs font-bold uppercase tracking-wider">
                      Close Position
                    </button>
                  </div>
                  
                  {t.alert && (
                    <div className="mt-4 bg-rose-500/10 border border-rose-500/30 rounded-lg p-3 flex gap-3 items-center">
                      <AlertTriangle className="text-rose-500 shrink-0" size={18} />
                      <p className="text-sm text-rose-200 font-medium">{t.alert}</p>
                    </div>
                  )}
                  
                  <div className="mt-4 pt-4 border-t border-white/5 flex justify-between text-[11px] text-slate-500 font-mono uppercase tracking-widest">
                    <span>In: {new Date(t.created_at).toLocaleDateString()}</span>
                    <span className="text-indigo-400">Target Out: {new Date(t.sell_date).toLocaleDateString()}</span>
                  </div>
                </Card>
              ))
            )}
          </div>
          
        </div>
      </div>
    </div>
  );
}
