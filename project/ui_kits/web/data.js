// Mock data for the Quantify web UI kit. Attached to window.QKIT.
window.QKIT = {
  universe: [
    { symbol: "NVDA", name: "NVIDIA Corporation" },
    { symbol: "AAPL", name: "Apple Inc." },
    { symbol: "MSFT", name: "Microsoft Corporation" },
    { symbol: "AMD",  name: "Advanced Micro Devices" },
    { symbol: "TSLA", name: "Tesla, Inc." },
    { symbol: "META", name: "Meta Platforms, Inc." },
    { symbol: "INTC", name: "Intel Corporation" },
    { symbol: "JPM",  name: "JPMorgan Chase & Co." },
  ],
  predictions: [
    { rank: 1, symbol: "NVDA", side: "long",  predictedReturnPct: 2.41,  strength: 0.182, drivers: [ {feature:"mom_12_1",zscore:2.07,direction:"higher"}, {feature:"rsi_14",zscore:1.21,direction:"higher"}, {feature:"vol_regime",zscore:0.84,direction:"higher"} ] },
    { rank: 2, symbol: "AVGO", side: "long",  predictedReturnPct: 1.88,  strength: 0.147, drivers: [ {feature:"ev_ebitda",zscore:1.6,direction:"higher"}, {feature:"mom_6_1",zscore:1.3,direction:"higher"} ] },
    { rank: 3, symbol: "AAPL", side: "long",  predictedReturnPct: 1.06,  strength: 0.094, drivers: [ {feature:"vol_20",zscore:-1.4,direction:"lower"}, {feature:"roe",zscore:1.1,direction:"higher"} ] },
    { rank: 4, symbol: "JPM",  side: "long",  predictedReturnPct: 0.72,  strength: 0.061, drivers: [ {feature:"value_pb",zscore:1.2,direction:"higher"}, {feature:"quality",zscore:0.8,direction:"higher"} ] },
    { rank: 5, symbol: "INTC", side: "short", predictedReturnPct: -1.73, strength: -0.121, drivers: [ {feature:"trend_adx",zscore:-1.9,direction:"lower"}, {feature:"roe",zscore:-1.1,direction:"lower"} ] },
    { rank: 6, symbol: "PYPL", side: "short", predictedReturnPct: -2.14, strength: -0.158, drivers: [ {feature:"mom_12_1",zscore:-2.2,direction:"lower"}, {feature:"margin",zscore:-1.3,direction:"lower"} ] },
  ],
  trades: [
    { id: 1, symbol: "MSFT", shares: 12, buy_price: 402.10, current: 421.55, hold_days: 21, dip: 0.10, in: "Jun 2", out: "Jun 23" },
    { id: 2, symbol: "AMD",  shares: 40, buy_price: 168.30, current: 159.04, hold_days: 14, dip: 0.08, in: "Jun 6", out: "Jun 20", alert: "PRICE DROP — 5.5% vs entry (threshold 8.0%)" },
  ],
  strategies: [
    { name: "Trend Following",          alloc: 15, sharpe: 1.21, idea: "EMA 50/200 crossover, ADX-filtered, ATR stops" },
    { name: "Cross-Sectional Momentum", alloc: 20, sharpe: 1.64, idea: "Long top-quintile / short bottom by 12-1m returns" },
    { name: "Pairs Mean Reversion",     alloc: 20, sharpe: 0.98, idea: "Engle-Granger cointegration, z-score entry/exit" },
    { name: "Quality Value",            alloc: 20, sharpe: 1.07, idea: "Composite rank on value + quality metrics" },
    { name: "ML Return Predictor",      alloc: 15, sharpe: 1.84, idea: "LightGBM + XGBoost + CatBoost ensemble" },
    { name: "Volatility Regime",        alloc: 10, sharpe: 0.76, idea: "VIX regime detection re-weights the book" },
  ],
  equityCurve: [100,101.2,100.6,102.4,103.9,103.1,105.6,107.2,106.4,108.9,110.3,109.1,111.8,113.4,112.6,115.2,117.9,116.4,119.1,121.8,120.4,123.2,124.8,126.1],
  benchCurve:  [100,100.4,100.9,101.2,101.0,101.8,102.3,102.0,102.9,103.6,103.2,104.1,104.8,104.5,105.4,106.1,105.7,106.8,107.5,107.1,108.0,108.6,108.2,109.0],
};
