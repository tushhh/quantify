"use client";

import { useEffect, useState } from "react";
import { Zap, Shield, TrendingUp, AlertTriangle, Plus, Crosshair, X } from "lucide-react";
import { api, PredictionItem, TrackedTrade } from "@/lib/api";
import { Card, Badge } from "@/components/ui";

export default function HomePage() {
  const [loadingPreds, setLoadingPreds] = useState(false);
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [trades, setTrades] = useState<TrackedTrade[]>([]);
  
  const [newTrade, setNewTrade] = useState({
    symbol: "", shares: "", buy_price: "", hold_days: "5"
  });

  // Fetch trades on mount
  useEffect(() => {
    loadTrades();
  }, []);

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
        hold_days: parseInt(newTrade.hold_days)
      });
      setNewTrade({ symbol: "", shares: "", buy_price: "", hold_days: "5" });
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

  return (
    <div className="max-w-6xl mx-auto px-4 py-12 flex flex-col gap-12 animate-fade-in text-slate-100">
      
      {/* Premium Hero */}
      <section className="flex flex-col items-center text-center gap-6 py-12 relative">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/40 via-slate-900 to-transparent blur-3xl opacity-50"></div>
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/50 bg-blue-500/10 text-blue-400 text-sm font-semibold tracking-wide backdrop-blur-md shadow-[0_0_15px_rgba(59,130,246,0.2)]">
          <Zap size={14} className="fill-blue-400" />
          Quantify AI Core Active
        </div>
        <h1 className="text-5xl sm:text-7xl font-black text-white leading-tight tracking-tighter">
          Automated <br className="sm:hidden" />
          <span className="text-transparent bg-clip-text bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-500">
            Alpha Generation
          </span>
        </h1>
        <p className="text-slate-400 max-w-2xl text-lg sm:text-xl leading-relaxed font-light">
          Run the Ensemble Machine Learning model to discover the best short-term plays, log your trades, and let the system manage your holding periods automatically.
        </p>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* ML Prediction Engine */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold flex items-center gap-2">
              <Crosshair className="text-blue-400" /> Prediction Engine
            </h2>
            <button 
              onClick={handlePredict}
              disabled={loadingPreds}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold py-2.5 px-6 rounded-xl shadow-[0_0_20px_rgba(79,70,229,0.3)] transition-all hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
            >
              {loadingPreds ? "Analyzing 128,000+ data points..." : "Run AI Analysis"}
            </button>
          </div>
          
          <Card className="bg-white/5 border-white/10 backdrop-blur-lg shadow-xl overflow-hidden min-h-[300px] flex flex-col">
            {predictions.length === 0 && !loadingPreds ? (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-3">
                <Zap size={48} className="opacity-20" />
                <p>Run analysis to see today's top picks</p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-4 px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-white/5">
                  <div>Rank</div>
                  <div>Symbol</div>
                  <div>Signal</div>
                  <div className="text-right">AI Strength</div>
                </div>
                {predictions.map((p, i) => (
                  <div key={p.symbol} className="grid grid-cols-4 px-4 py-3 items-center hover:bg-white/5 rounded-lg transition-colors cursor-pointer" onClick={() => setNewTrade({ ...newTrade, symbol: p.symbol })}>
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
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="text-indigo-400" /> Active Positions
          </h2>
          
          {/* Active Trades */}
          <div className="flex flex-col gap-3">
            {trades.length === 0 ? (
              <div className="p-8 text-center rounded-xl border border-dashed border-white/10 text-slate-500 bg-white/5">
                No active positions. Log a trade below.
              </div>
            ) : (
              trades.map(t => (
                <Card key={t.id} className="bg-gradient-to-br from-slate-900 to-slate-800 border-white/10 shadow-lg p-5 relative overflow-hidden group">
                  {t.alert && (
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-rose-500 to-orange-500 animate-pulse"></div>
                  )}
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-xl font-black text-white">{t.symbol}</h3>
                      <p className="text-sm text-slate-400">{t.shares} shares @ ${t.buy_price}</p>
                    </div>
                    <button onClick={() => handleCloseTrade(t.id)} className="text-slate-500 hover:text-rose-400 transition-colors bg-white/5 p-1.5 rounded-md hover:bg-rose-500/10">
                      <X size={16} />
                    </button>
                  </div>
                  
                  {t.alert && (
                    <div className="mt-4 bg-rose-500/10 border border-rose-500/30 rounded-lg p-3 flex gap-3 items-center">
                      <AlertTriangle className="text-rose-500 shrink-0" size={18} />
                      <p className="text-sm text-rose-200 font-medium">{t.alert}</p>
                    </div>
                  )}
                  
                  <div className="mt-4 pt-4 border-t border-white/5 flex justify-between text-xs text-slate-500 font-mono">
                    <span>Bought: {new Date(t.created_at).toLocaleDateString()}</span>
                    <span>Target Sell: {new Date(t.sell_date).toLocaleDateString()}</span>
                  </div>
                </Card>
              ))
            )}
          </div>

          {/* Log New Trade */}
          <Card className="mt-2 bg-indigo-900/20 border-indigo-500/20 backdrop-blur-md">
            <h3 className="text-sm font-semibold text-indigo-300 mb-4 flex items-center gap-2">
              <Plus size={16} /> Log New Trade
            </h3>
            <form onSubmit={handleCreateTrade} className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Symbol</label>
                <input required type="text" placeholder="e.g. AMD" className="w-full bg-slate-950/50 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500 uppercase" value={newTrade.symbol} onChange={e => setNewTrade({...newTrade, symbol: e.target.value})} />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Hold Days</label>
                <input required type="number" min="1" className="w-full bg-slate-950/50 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500" value={newTrade.hold_days} onChange={e => setNewTrade({...newTrade, hold_days: e.target.value})} />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Shares</label>
                <input required type="number" step="0.01" placeholder="10" className="w-full bg-slate-950/50 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500" value={newTrade.shares} onChange={e => setNewTrade({...newTrade, shares: e.target.value})} />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Buy Price ($)</label>
                <input required type="number" step="0.01" placeholder="150.25" className="w-full bg-slate-950/50 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500" value={newTrade.buy_price} onChange={e => setNewTrade({...newTrade, buy_price: e.target.value})} />
              </div>
              <button type="submit" className="col-span-2 mt-2 bg-indigo-500/20 hover:bg-indigo-500/40 text-indigo-300 border border-indigo-500/30 font-semibold py-2.5 rounded-lg transition-colors">
                Track Position
              </button>
            </form>
          </Card>
          
        </div>
      </div>
    </div>
  );
}
