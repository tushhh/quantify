"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Zap, Shield, AlertTriangle, Plus, Crosshair, Send, LogOut, UserCircle } from "lucide-react";
import Link from "next/link";
import { api, type AuthUser, type PredictionItem, type TrackedTrade } from "@/lib/api";
import { Card, Badge } from "@/components/ui";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);

  const [loadingPreds, setLoadingPreds] = useState(false);
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [trades, setTrades] = useState<TrackedTrade[]>([]);
  
  const [newTrade, setNewTrade] = useState({ symbol: "", shares: "", buy_price: "" });
  const [holdStrategy, setHoldStrategy] = useState<"ai" | "custom">("ai");
  const [customHoldDays, setCustomHoldDays] = useState("10");

  const loadTrades = useCallback(async () => {
    try {
      const data = await api.trades.list();
      setTrades(data.filter((t) => t.status === "active"));
    } catch (error) {
      console.error(error);
    }
  }, []);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const u = await api.auth.me();
        setUser(u);
        loadTrades().catch((err) => console.error("Failed to load trades:", err));
      } catch {
        router.push("/login");
      } finally {
        setLoadingAuth(false);
      }
    };

    void checkAuth();
  }, [router, loadTrades]);

  const logout = () => {
    localStorage.removeItem("token");
    router.push("/");
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

  const handleCloseTrade = async (id: number) => {
    try {
      await api.trades.close(id);
      loadTrades();
    } catch (e) {
      console.error(e);
    }
  };

  if (loadingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-500 text-sm">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="max-w-6xl mx-auto px-4 pt-24 pb-24 md:pb-12 flex flex-col gap-8 animate-fade-in text-slate-100">
      
      {/* Header */}
      <div className="flex justify-between items-center bg-white/[0.02] border border-white/5 p-5 rounded-2xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
            <UserCircle className="text-white" size={24} />
          </div>
          <div>
            <p className="font-bold text-white text-lg leading-none">{user.username}</p>
            <p className="text-xs text-slate-500 mt-1.5 flex items-center gap-1.5">
              <Send size={10} className="text-blue-400"/>
              {user.telegram_username ? `${user.telegram_username} connected` : "No Telegram connected"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/account" className="text-sm font-medium text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/5">
            Settings
          </Link>
          <button onClick={logout} className="text-sm font-medium text-slate-500 hover:text-rose-400 transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-rose-500/10">
            <LogOut size={14} />
            Logout
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        
        {/* ML Prediction Engine */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-black flex items-center gap-2 text-white">
              <Crosshair className="text-blue-400" /> AI Predictions
            </h2>
            <button 
              onClick={handlePredict}
              disabled={loadingPreds}
              className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white font-bold py-2.5 px-6 rounded-xl shadow-lg shadow-blue-500/20 transition-all hover:shadow-blue-500/30 active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
            >
              {loadingPreds ? "Analyzing..." : "Run AI Analysis"}
            </button>
          </div>
          
          <Card className="bg-white/[0.02] border-white/5 shadow-xl overflow-hidden min-h-[300px] flex flex-col">
            {predictions.length === 0 && !loadingPreds ? (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-600 gap-3">
                <Zap size={48} className="opacity-20" />
                <p className="text-center px-8">Run analysis to see today&apos;s top algorithmically chosen stocks.</p>
              </div>
            ) : loadingPreds ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-4">
                <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-slate-500 text-sm">Crunching market data with ML models...</p>
              </div>
            ) : (
              <div className="flex flex-col gap-0">
                <div className="grid grid-cols-4 px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-white/5 bg-black/20">
                  <div>Rank</div>
                  <div>Symbol</div>
                  <div>Signal</div>
                  <div className="text-right">Strength</div>
                </div>
                {predictions.map((p, i) => (
                  <div key={p.symbol} className="grid grid-cols-4 px-5 py-4 items-center hover:bg-white/5 border-b border-white/5 transition-colors cursor-pointer" onClick={() => setNewTrade({ ...newTrade, symbol: p.symbol })}>
                    <div className="font-mono text-slate-600">#{i + 1}</div>
                    <div className="font-bold text-white text-lg">{p.symbol}</div>
                    <div><Badge variant="success" className="uppercase">{p.side}</Badge></div>
                    <div className="text-right font-mono text-blue-400 font-bold">+{p.strength.toFixed(3)}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Trade Manager */}
        <div className="flex flex-col gap-4">
          <h2 className="text-2xl font-black flex items-center gap-2 text-white">
            <Shield className="text-violet-400" /> Active Portfolio
          </h2>
          
          {/* Log New Trade */}
          <Card className="bg-violet-500/[0.03] border-violet-500/10 shadow-xl">
            <h3 className="text-sm font-semibold text-violet-300 mb-4 flex items-center gap-2">
              <Plus size={16} /> Log a New Trade
            </h3>
            <form onSubmit={handleCreateTrade} className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Symbol</label>
                  <input required type="text" placeholder="e.g. AMD" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-white outline-none focus:border-violet-500/50 uppercase" value={newTrade.symbol} onChange={e => setNewTrade({...newTrade, symbol: e.target.value})} />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Shares</label>
                  <input required type="number" step="0.01" placeholder="10" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-white outline-none focus:border-violet-500/50" value={newTrade.shares} onChange={e => setNewTrade({...newTrade, shares: e.target.value})} />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Buy Price ($)</label>
                  <input required type="number" step="0.01" placeholder="150.25" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-white outline-none focus:border-violet-500/50" value={newTrade.buy_price} onChange={e => setNewTrade({...newTrade, buy_price: e.target.value})} />
                </div>
              </div>

              {/* Holding Strategy */}
              <div className="p-4 rounded-xl border border-white/5 bg-black/20 flex flex-col gap-3">
                <p className="text-xs font-semibold text-slate-500 uppercase">Holding Strategy</p>
                
                <label className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${holdStrategy === "ai" ? "bg-violet-500/10 border-violet-500/30" : "border-white/5 hover:border-white/10"}`}>
                  <input type="radio" name="strategy" className="mt-1 accent-violet-500" checked={holdStrategy === "ai"} onChange={() => setHoldStrategy("ai")} />
                  <div>
                    <p className="text-sm font-bold text-white">Follow AI Advice (5 Days)</p>
                    <p className="text-xs text-slate-500 mt-0.5">The model predicts maximum returns on a 5-day horizon. We will alert you when it&apos;s time to sell.</p>
                  </div>
                </label>

                <label className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${holdStrategy === "custom" ? "bg-violet-500/10 border-violet-500/30" : "border-white/5 hover:border-white/10"}`}>
                  <input type="radio" name="strategy" className="mt-1 accent-violet-500" checked={holdStrategy === "custom"} onChange={() => setHoldStrategy("custom")} />
                  <div className="w-full">
                    <p className="text-sm font-bold text-white">Custom Duration</p>
                    <p className="text-xs text-slate-500 mt-0.5 mb-2">Set your own holding period.</p>
                    {holdStrategy === "custom" && (
                      <input type="number" min="1" className="w-full max-w-[150px] bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white outline-none focus:border-violet-500/50 text-sm" value={customHoldDays} onChange={e => setCustomHoldDays(e.target.value)} />
                    )}
                  </div>
                </label>
              </div>

              <button type="submit" className="w-full bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 text-white font-bold py-3 rounded-xl transition-all hover:shadow-lg hover:shadow-violet-500/20 active:scale-[0.98]">
                Log Trade & Activate Alerts
              </button>
            </form>
          </Card>

          {/* Active Trades */}
          <div className="flex flex-col gap-3 mt-2">
            {trades.length === 0 ? (
              <div className="p-10 text-center rounded-2xl border border-dashed border-white/10 text-slate-600 bg-white/[0.01]">
                No active positions being tracked.
              </div>
            ) : (
              trades.map(t => (
                <Card key={t.id} className="bg-white/[0.02] border-white/5 shadow-lg p-5 relative overflow-hidden group hover:border-white/10 transition-all">
                  {t.alert && (
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-rose-500 to-orange-500 animate-pulse"></div>
                  )}
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-xl font-black text-white">{t.symbol}</h3>
                      <p className="text-sm text-slate-500">{t.shares} shares @ ${t.buy_price}</p>
                    </div>
                    <button onClick={() => handleCloseTrade(t.id)} className="text-slate-500 hover:text-rose-400 transition-colors bg-white/5 px-3 py-1.5 rounded-lg hover:bg-rose-500/10 text-xs font-bold uppercase tracking-wider">
                      Close
                    </button>
                  </div>
                  
                  {t.alert && (
                    <div className="mt-4 bg-rose-500/10 border border-rose-500/20 rounded-xl p-3 flex gap-3 items-center">
                      <AlertTriangle className="text-rose-500 shrink-0" size={18} />
                      <p className="text-sm text-rose-200 font-medium">{t.alert}</p>
                    </div>
                  )}
                  
                  <div className="mt-4 pt-4 border-t border-white/5 flex justify-between text-[11px] text-slate-600 font-mono uppercase tracking-widest">
                    <span>In: {new Date(t.created_at).toLocaleDateString()}</span>
                    <span className="text-violet-400">Target Out: {new Date(t.sell_date).toLocaleDateString()}</span>
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
