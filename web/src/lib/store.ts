/**
 * Zustand store — global app state (backtest config, results, UI state).
 */
"use client";

import { create } from "zustand";
import type {
  BacktestRequest,
  BacktestResponse,
  RiskConfig,
  StrategyConfig,
  RiskPreset,
  StrategyInfo,
  BacktestCostConfig,
} from "@/lib/api";

// ── Defaults ──────────────────────────────────────────────────────────────────

export const DEFAULT_RISK: RiskConfig = {
  max_portfolio_drawdown: 0.15,
  max_gross_leverage: 1.5,
  max_single_position: 0.10,
  max_sector_exposure: 0.30,
  daily_loss_limit: 0.03,
  default_stop_loss: 0.02,
  default_take_profit: 0.04,
  default_position_sizer: "equal_weight",
};

export const DEFAULT_STRATEGIES: Record<string, StrategyConfig> = {
  trend_following:          { enabled: true,  allocation: 0.15, params: {} },
  cross_sectional_momentum: { enabled: true,  allocation: 0.20, params: {} },
  pairs_mean_reversion:     { enabled: true,  allocation: 0.20, params: {} },
  quality_value:            { enabled: true,  allocation: 0.20, params: {} },
  ml_return_predictor:      { enabled: true,  allocation: 0.15, params: {} },
  volatility_regime:        { enabled: true,  allocation: 0.10, params: {} },
};

// ── Store type ────────────────────────────────────────────────────────────────

type AppState = {
  // Config
  startDate: string;
  endDate: string;
  initialCapital: number;
  benchmark: string;
  risk: RiskConfig;
  costs: BacktestCostConfig;
  strategies: Record<string, StrategyConfig>;
  selectedPresetId: string;

  // Results
  backtestResult: BacktestResponse | null;
  isRunning: boolean;
  error: string | null;

  // Metadata from API
  strategyInfos: StrategyInfo[];
  presets: RiskPreset[];

  // Actions
  setStartDate: (d: string) => void;
  setEndDate: (d: string) => void;
  setInitialCapital: (n: number) => void;
  setBenchmark: (s: string) => void;
  setRisk: (r: Partial<RiskConfig>) => void;
  setCosts: (c: Partial<BacktestCostConfig>) => void;
  setStrategy: (name: string, cfg: Partial<StrategyConfig>) => void;
  applyPreset: (preset: RiskPreset) => void;
  setSelectedPresetId: (id: string) => void;
  setBacktestResult: (r: BacktestResponse | null) => void;
  setIsRunning: (b: boolean) => void;
  setError: (e: string | null) => void;
  setStrategyInfos: (s: StrategyInfo[]) => void;
  setPresets: (p: RiskPreset[]) => void;
  buildRequest: () => BacktestRequest;
  // UI
  sidebarOpen: boolean;
  setSidebarOpen: (b: boolean) => void;
  toggleSidebar: () => void;
};

// ── Store ─────────────────────────────────────────────────────────────────────

export const useAppStore = create<AppState>((set, get) => ({
  startDate: "2021-01-01",
  endDate: "2024-01-01",
  initialCapital: 100_000,
  benchmark: "SPY",
  risk: { ...DEFAULT_RISK },
  costs: {
    commission_per_share: 0.005,
    spread_bps: 5,
    slippage_pct: 0.05,
  },
  strategies: { ...DEFAULT_STRATEGIES },
  selectedPresetId: "moderate",
  backtestResult: null,
  isRunning: false,
  error: null,
  strategyInfos: [],
  presets: [],

  setStartDate: (d) => set({ startDate: d }),
  setEndDate: (d) => set({ endDate: d }),
  setInitialCapital: (n) => set({ initialCapital: n }),
  setBenchmark: (s) => set({ benchmark: s }),
  setRisk: (r) => set((st) => ({ risk: { ...st.risk, ...r } })),
  setCosts: (c) => set((st) => ({ costs: { ...st.costs, ...c } })),
  setStrategy: (name, cfg) =>
    set((st) => ({
      strategies: {
        ...st.strategies,
        [name]: { ...st.strategies[name], ...cfg },
      },
    })),
  applyPreset: (preset) =>
    set({
      risk: { ...preset.risk },
      strategies: {
        ...DEFAULT_STRATEGIES,
        ...preset.strategy_overrides,
      },
      selectedPresetId: preset.id,
    }),
  setSelectedPresetId: (id) => set({ selectedPresetId: id }),
  setBacktestResult: (r) => set({ backtestResult: r }),
  setIsRunning: (b) => set({ isRunning: b }),
  setError: (e) => set({ error: e }),
  setStrategyInfos: (s) => set({ strategyInfos: s }),
  setPresets: (p) => set({ presets: p }),

  // UI
  sidebarOpen: true,
  setSidebarOpen: (b: boolean) => set({ sidebarOpen: b }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  buildRequest: (): BacktestRequest => {
    const st = get();
    return {
      strategies: st.strategies,
      start_date: st.startDate,
      end_date: st.endDate,
      initial_capital: st.initialCapital,
      risk: st.risk,
      costs: st.costs,
      benchmark: st.benchmark,
    };
  },
}));
