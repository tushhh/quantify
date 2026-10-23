/**
 * Central API client — reads NEXT_PUBLIC_API_URL at runtime.
 * Falls back to localhost:8000 for local development.
 */

import { safeGetItem } from "./safeStorage";

export const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

// ── Errors ───────────────────────────────────────────────────────────────────

export type ApiErrorKind =
  | "network"      // no response at all (offline, DNS, CORS-less router error)
  | "timeout"      // no response within the request timeout
  | "auth"         // 401
  | "validation"   // 422
  | "client"       // other 4xx
  | "unavailable"  // 503, or an HTML/non-JSON body from a proxy or router
  | "server";      // other 5xx

/**
 * Every failure apiFetch reports, other than a caller-initiated abort.
 * `message` is always user-facing copy, never raw backend or browser text.
 * `status` is the HTTP status, or 0 when no response arrived (network/timeout).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;

  constructor(message: string, status: number, kind: ApiErrorKind) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

/** The user-facing message for any thrown value: ApiError text, otherwise `fallback`. */
export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** True when the error is the caller cancelling the request through its own AbortSignal. */
export function isAbortError(err: unknown): boolean {
  return typeof err === "object" && err !== null && (err as { name?: unknown }).name === "AbortError";
}

const MSG_NETWORK = "Can't reach the Quantify server. It may be restarting, so try again in a minute.";
const MSG_TIMEOUT = "The Quantify server took too long to respond. Try again in a minute.";
const MSG_UNAVAILABLE = "The Quantify service is temporarily unavailable. Try again in a minute.";
const MSG_UNEXPECTED = "The server sent a response we couldn't read. Try again in a minute.";

/** "initial_capital" -> "Initial capital" */
function humanizeField(field: string): string {
  const words = field.replace(/[_-]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : "";
}

/** Flatten a FastAPI/Pydantic 422 `detail` into one readable sentence. */
function validationMessage(detail: unknown): string {
  const fallback = "Some of the values you entered aren't valid. Check them and try again.";
  if (typeof detail === "string") return cleanDetail(detail) ?? fallback;
  if (!Array.isArray(detail)) return fallback;
  const parts = detail
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const { loc, msg } = item as { loc?: unknown; msg?: unknown };
      if (typeof msg !== "string" || !msg) return null;
      const field = Array.isArray(loc)
        ? [...loc].reverse().find((p) => typeof p === "string" && !["body", "query", "path"].includes(p))
        : undefined;
      const text = msg.replace(/^Value error, /, "");
      const sentence = text.charAt(0).toLowerCase() + text.slice(1);
      return typeof field === "string" ? `${humanizeField(field)}: ${sentence}` : text;
    })
    .filter((p): p is string => !!p);
  return parts.length ? `Check your inputs. ${parts.join("; ")}.` : fallback;
}

/**
 * A 4xx `detail` string the API wrote for clients ("Trade not found"), with any
 * trailing machine code like "(not_us_listed)" removed. Returns null for text
 * that looks like an internal error rather than a message.
 */
function cleanDetail(detail: unknown): string | null {
  if (typeof detail !== "string") return null;
  const text = detail.replace(/\s*\([a-z0-9_]+\)\s*$/, "").trim();
  if (!text || text.length > 160 || /[\r\n<]/.test(text)) return null;
  if (/error|exception|traceback/i.test(text)) return null;
  return text;
}

function clientErrorMessage(status: number, detail: unknown): string {
  const clean = cleanDetail(detail);
  if (clean) return clean.charAt(0).toUpperCase() + clean.slice(1);
  if (status === 403) return "You don't have permission to do that.";
  if (status === 404) return "We couldn't find what you asked for. It may have been removed or expired.";
  if (status === 429) return "Too many requests. Wait a moment and try again.";
  return "The server couldn't process this request. Check your inputs and try again.";
}

function errorFromResponse(path: string, status: number, text: string): ApiError {
  let detail: unknown;
  let isJson = false;
  try {
    detail = (JSON.parse(text) as { detail?: unknown } | null)?.detail;
    isJson = true;
  } catch {
    // Non-JSON body: an HTML page from the Heroku router, Vercel or a proxy.
  }

  if (status === 503 || (!isJson && text.trim() !== "")) {
    return new ApiError(MSG_UNAVAILABLE, status, "unavailable");
  }
  if (status >= 500) {
    return new ApiError(`The server hit an error (HTTP ${status}). Try again shortly.`, status, "server");
  }
  if (status === 401) {
    const message = path.startsWith("/api/auth/login")
      ? "Incorrect username or password."
      : "Your session has expired. Log in again to continue.";
    return new ApiError(message, status, "auth");
  }
  if (status === 422) {
    return new ApiError(validationMessage(detail), status, "validation");
  }
  return new ApiError(clientErrorMessage(status, detail), status, "client");
}

// ── Fetch ────────────────────────────────────────────────────────────────────

/** Default request timeout. Heroku's router cuts any request off at 30s anyway. */
const DEFAULT_TIMEOUT_MS = 30_000;

type FetchOptions = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  /** Abort and throw ApiError(kind "timeout") after this long. */
  timeoutMs?: number;
};

async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = opts;
  // Only send Content-Type with a body: a bodyless GET without custom headers
  // is a CORS "simple request" and skips the preflight round trip.
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const token = safeGetItem("token");
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // One controller aborts the request on either the caller's signal or the timeout.
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  const onCallerAbort = () => ctrl.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) onCallerAbort();
    else signal.addEventListener("abort", onCallerAbort, { once: true });
  }

  let res: Response;
  let text: string;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    text = await res.text();
  } catch (err) {
    // A caller-initiated abort keeps its AbortError so callers can ignore it.
    if (signal?.aborted && !timedOut) throw err;
    if (timedOut) throw new ApiError(MSG_TIMEOUT, 0, "timeout");
    throw new ApiError(MSG_NETWORK, 0, "network");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onCallerAbort);
  }

  if (!res.ok) throw errorFromResponse(path, res.status, text);
  if (text.trim() === "") return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(text.trimStart().startsWith("<") ? MSG_UNAVAILABLE : MSG_UNEXPECTED, res.status, "unavailable");
  }
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

export type NewsItem = {
  label: "BULLISH" | "BEARISH" | "NEUTRAL";
  score: number;
  headlines: string[];
};

export type PredictionItem = {
  symbol: string;
  strength: number;
  side: string;
  sector: string;
  name: string;
  predicted_return_pct: number;
  explanations?: PredictionExplanation[];
  news?: NewsItem | null;
  // Trend-screen picks: the stock's actual trailing performance, in percent.
  return_6m_pct?: number | null;
  return_12m_pct?: number | null;
  pct_above_ma200?: number | null;
};

export type TrendBacktest = {
  start: string;
  end: string;
  cagr_pct: number;
  spy_cagr_pct: number;
  excess_cagr_pct: number;
  excess_cagr_stress_pct: number;
  sharpe: number;
  spy_sharpe: number;
  max_drawdown_pct: number;
  spy_max_drawdown_pct: number;
  months_beat_spy_pct: number;
  picks: number;
  liquid_universe: number;
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
  // Trend screen (method === "trend"): the close the list is based on and when it changes.
  method?: string | null;
  as_of?: string | null;
  next_refresh?: string | null;
  generated_at?: string | null;
  backtest?: TrendBacktest | null;
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

export type TradeUpdate = {
  shares?: number;
  buy_price?: number;
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
  aggregated?: boolean;
  prev_shares?: number;
  prev_buy_price?: number;
  realized_pnl?: number | null;
};

export type PortfolioSummary = {
  total_value: number;
  total_invested: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  positions_count: number;
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
      // While the job runs the body is only { status: "running" }; check status before reading results.
      apiFetch<BacktestResponse>(`/api/backtest/result/${jobId}`, { signal }),
  },

  predict: {
    best: (top_n: number = 10, sector?: string, force?: boolean, mode: "live" | "previous_close" = "previous_close") => {
      const params = new URLSearchParams({ top_n: String(top_n) });
      if (sector) params.set("sector", sector);
      if (force) params.set("force", "true");
      params.set("mode", mode);
      // force=true skips the server's 5-minute cache and re-downloads the screener
      // output from GitHub, so give it extra room beyond the default timeout.
      return apiFetch<PredictionResponse>(`/api/predict/best?${params}`, force ? { timeoutMs: 90_000 } : {});
    },
    sectors: () => apiFetch<string[]>("/api/predict/sectors"),
  },
  trades: {
    create: (req: TradeCreate) => apiFetch<TrackedTrade>("/api/trades", { method: "POST", body: req }),
    list: () => apiFetch<TrackedTrade[]>("/api/trades"),
    prices: () => apiFetch<Record<string, number | null>>("/api/trades/prices"),
    summary: () => apiFetch<PortfolioSummary>("/api/trades/portfolio-summary"),
    close: (id: number, sellPrice?: number | null) =>
      apiFetch<{ status: string }>(`/api/trades/${id}/close`, {
        method: "POST",
        body: { sell_price: sellPrice ?? null },
      }),
    update: (id: number, req: TradeUpdate) =>
      apiFetch<TrackedTrade>(`/api/trades/${id}`, { method: "PATCH", body: req }),
    updateDipThreshold: (id: number, dip_threshold_pct: number | null) =>
      apiFetch<TrackedTrade>(`/api/trades/${id}/dip-threshold`, {
        method: "PATCH",
        body: { dip_threshold_pct },
      }),
  },
  health: () => apiFetch<{ status: string }>("/health"),
};

