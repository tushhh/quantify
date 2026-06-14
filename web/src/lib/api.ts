/**
 * Central API client — reads NEXT_PUBLIC_API_URL at runtime.
 * Falls back to localhost:8000 for local development.
 */

export const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

type FetchOptions = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
};

async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Types mirroring the Python schemas ───────────────────────────────────────

export type RiskConfig = {
  max_portfolio_drawdown: number;
  max_gross_leverage: number;
  max_single_position: number;
  max_sector_exposure: number;
  daily_loss_limit: number;
  default_stop_loss: number;
  default_take_profit: number;
  default_position_sizer: "equal_weight" | "volatility_target" | "half_kelly";
};

export type StrategyConfig = {
  enabled: boolean;
  allocation: number;
  params: Record<string, unknown>;
};

export type BacktestCostConfig = {
  commission_per_share: number;
  spread_bps: number;
  slippage_pct: number;
};

export type BacktestRequest = {
  strategies: Record<string, StrategyConfig>;
  start_date: string;
  end_date: string;
  initial_capital: number;
  risk: RiskConfig;
  costs: BacktestCostConfig;
  benchmark: string;
  universe?: string[];
};

export type BacktestMetrics = {
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  avg_holding_days: number;
};

export type EquityPoint = {
  date: string;
  value: number;
  pct: number;
  benchmark_value?: number;
  benchmark_pct?: number;
};

export type DrawdownPoint = { date: string; drawdown: number };

export type TradeRecord = {
  symbol: string;
  strategy_name: string;
  entry_date: string | null;
  exit_date: string | null;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  return_pct: number;
  holding_days: number;
  side: string;
};

export type BacktestResponse = {
  status: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  drawdown_curve: DrawdownPoint[];
  trades: TradeRecord[];
  signals_count: number;
  metadata: Record<string, unknown>;
};

export type BacktestSubmitResponse = {
  status: string;
  job_id: string;
  is_cloud_run: boolean;
};

export type ParamSpec = {
  key: string;
  label: string;
  type: "int" | "float" | "bool" | "select";
  default: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  description: string;
};

export type StrategyInfo = {
  name: string;
  label: string;
  description: string;
  default_allocation: number;
  params: ParamSpec[];
};

export type RiskPreset = {
  id: string;
  label: string;
  description: string;
  risk: RiskConfig;
  strategy_overrides: Record<string, StrategyConfig>;
};

export type AuthUser = {
  id: number;
  username: string;
  telegram_username: string | null;
};

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type AuthUpdateRequest = {
  telegram_username?: string | null;
  new_password?: string;
};

export type TickerInfo = { symbol: string; sector: string; name: string };
export type UniverseResponse = { tickers: TickerInfo[]; sectors: string[] };

export type PredictionItem = {
  symbol: string;
  strength: number;
  side: string;
  sector: string;
  name: string;
  predicted_return_pct: number;
  explanations?: PredictionExplanation[];
};

export type PredictionExplanation = {
  feature: string;
  zscore: number;
  value?: number | null;
  weight?: number | null;
  direction?: "higher" | "lower";
  score?: number;
};

export type PredictionResponse = {
  status: string; // "ok" or "computing"
  mode?: "live" | "previous_close";
  date: string;
  signals?: PredictionItem[]; // Now optional since it's omitted in computing state
  cached: boolean;
  cache_age_minutes: number;
  universe_size: number;
  model_metrics?: Record<string, number> | null;
  message?: string; // e.g. "Model training started..."
};

export type TradeCreate = {
  symbol: string;
  shares: number;
  buy_price: number;
  hold_days?: number;
  hold_unit?: "days" | "months" | "years";
  hold_value?: number;
  dip_threshold_pct?: number | null;
};

export type TrackedTrade = TradeCreate & {
  id: number;
  created_at: string;
  sell_date: string;
  status: string;
  current_strength?: number;
  current_price?: number;
  last_health_reason?: string;
  alert?: string;
};

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    login: (data: { username: string; password: string }) =>
      apiFetch<AuthToken>("/api/auth/login", { method: "POST", body: data }),
    register: (data: { username: string; password: string; telegram_username?: string | null }) =>
      apiFetch<AuthUser>("/api/auth/register", { method: "POST", body: data }),
    me: () => apiFetch<AuthUser>("/api/auth/me"),
    update: (data: AuthUpdateRequest) => apiFetch<AuthUser>("/api/auth/update", { method: "PUT", body: data }),
  },
  strategies: {
    list: () => apiFetch<StrategyInfo[]>("/api/strategies"),
    get:  (name: string) => apiFetch<StrategyInfo>(`/api/strategies/${name}`),
  },
  risk: {
    presets: () => apiFetch<RiskPreset[]>("/api/risk/presets"),
    preset:  (id: string) => apiFetch<RiskPreset>(`/api/risk/presets/${id}`),
  },
  universe: {
    get:     (sector?: string) =>
      apiFetch<UniverseResponse>(`/api/universe${sector ? `?sector=${encodeURIComponent(sector)}` : ""}`),
    sectors: () => apiFetch<string[]>("/api/universe/sectors"),
  },
  utils: {
    validateSymbol: (symbol: string) => apiFetch<{ valid: boolean; reason?: string; exchange?: string }>(`/api/utils/validate_symbol?symbol=${encodeURIComponent(symbol)}`),
  },
  backtest: {
    submit: (req: BacktestRequest, jobId: string, signal?: AbortSignal) =>
      apiFetch<BacktestSubmitResponse>(`/api/backtest?job_id=${jobId}`, {
        method: "POST",
        body: req,
        signal,
      }),

    pollResult: (jobId: string, signal?: AbortSignal) =>
      apiFetch<any>(`/api/backtest/result/${jobId}`, { signal }),
  },

  predict: {
    best: (top_n: number = 10, sector?: string, force?: boolean, mode: "live" | "previous_close" = "previous_close") => {
      const params = new URLSearchParams({ top_n: String(top_n) });
      if (sector) params.set("sector", sector);
      if (force) params.set("force", "true");
      params.set("mode", mode);
      return apiFetch<PredictionResponse>(`/api/predict/best?${params}`);
    },
    sectors: () => apiFetch<string[]>("/api/predict/sectors"),
  },
  trades: {
    create: (req: TradeCreate) => apiFetch<TrackedTrade>("/api/trades", { method: "POST", body: req }),
    list: () => apiFetch<TrackedTrade[]>("/api/trades"),
    prices: () => apiFetch<Record<string, number | null>>("/api/trades/prices"),
    close: (id: number) => apiFetch<{status: string}>(`/api/trades/${id}`, { method: "DELETE" }),
    updateDipThreshold: (id: number, dip_threshold_pct: number | null) =>
      apiFetch<TrackedTrade>(`/api/trades/${id}/dip-threshold`, {
        method: "PATCH",
        body: { dip_threshold_pct },
      }),
  },
  health: () => apiFetch<{ status: string }>("/health"),
};

