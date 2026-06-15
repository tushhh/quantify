import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Optional
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from api.database import SessionLocal
from api.models import PredictionSubscription, AdhocPredictionCache
from api.schemas import PredictionItem
from api.driver_explain import humanize_driver, build_plain_summary

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prediction_bot")

BOT_TOKEN = os.getenv("TELEGRAM_PREDICTION_BOT_TOKEN")


class PredictionUnavailable(Exception):
    """Raised when a single-ticker prediction cannot be produced.

    ``user_message`` is HTML-safe and intended to be shown directly to the
    Telegram user, so the failure reason is accurate rather than always
    blaming the ticker.
    """

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message

# Rate limiter settings
_user_request_timestamps = {}
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 5

# Concurrency safety: limit parallel ad-hoc queries to protect Heroku dyno memory/CPU
prediction_semaphore = asyncio.Semaphore(2)

def check_rate_limit(key: str) -> bool:
    """Returns True if the request is within limits, False if rate-limited."""
    now = datetime.now(timezone.utc).timestamp()
    if key not in _user_request_timestamps:
        _user_request_timestamps[key] = [now]
        return True
    
    # Filter out timestamps older than the window
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    timestamps = [ts for ts in _user_request_timestamps[key] if ts > cutoff]
    _user_request_timestamps[key] = timestamps
    
    if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
        return False
        
    timestamps.append(now)
    return True

def predict_single_ticker(symbol: str) -> Optional[PredictionItem]:
    """Blocking synchronous function to fetch data and run ML predictions for a single ticker.

    Bypasses the cross-sectional ranking in MLReturnPredictorStrategy (which always gives
    a middle percentile of 0.5 when the universe contains only one symbol, resulting in
    direction="close" and strength=0). Instead we load the model directly and score the
    raw model output to derive side/strength.

    Runs inside a background thread pool via asyncio.to_thread.
    """
    try:
        import joblib
        import pandas as pd
        from quantify.data.providers.yfinance_provider import YFinanceProvider
        from quantify.data.cache import ParquetCache
        from quantify.data.features import FeatureEngine
        from quantify.data.universe import get_sector_map
        from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
        from api.routers.predict import _latest_completed_session_date, _get_ticker_name, _download_latest_model

        now_utc = datetime.now(timezone.utc)
        session_date = _latest_completed_session_date(now_utc)

        # 3 years lookback to compute technical indicator features
        end_dt = datetime.combine(session_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        start_dt = end_dt - timedelta(days=365 * 3)

        # Build a strategy instance just to access feature list and model path.
        # train_enabled=False so we never trigger training here.
        strat = MLReturnPredictorStrategy(universe=[symbol], train_enabled=False)

        cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
        provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))
        data = provider.get_multiple([symbol], start=start_dt, end=end_dt)

        if not data or symbol not in data or data[symbol].empty:
            log.warning("No market data returned for ad-hoc ticker %s", symbol)
            raise PredictionUnavailable(
                f"❓ Couldn't find market data for <b>{symbol}</b>.\n\n"
                f"Double-check the symbol — use the exchange ticker (e.g. <code>AAPL</code>, "
                f"<code>BRK-B</code>). Indices and most non-US listings aren't supported."
            )

        df = data[symbol]
        if len(df) < 50:
            log.warning("Insufficient history for ad-hoc ticker %s: %d rows", symbol, len(df))
            raise PredictionUnavailable(
                f"🐣 <b>{symbol}</b> has only {len(df)} trading days of history.\n\n"
                f"The model needs at least 50 days, so very recent listings can't be scored yet."
            )

        # Compute technical indicator features
        required = strat.get_required_features()
        engine = FeatureEngine()
        features = engine.compute(data, required=list(required))

        feat_df = features.get(symbol)
        enriched_df = df.join(feat_df, how="left", rsuffix="_feat") if feat_df is not None else df

        # Append fundamental valuation features so the feature vector matches
        # the model trained with fundamentals (earnings_yield, book_to_market,
        # fcf_yield, roe).
        try:
            from quantify.data.fundamentals import fetch_fundamentals, add_fundamental_features

            fundamentals = fetch_fundamentals([symbol], cache_dir=cache_dir)
            enriched_df = add_fundamental_features({symbol: enriched_df}, fundamentals)[symbol]
        except Exception as fund_err:
            log.warning("Failed to add fundamental features for %s: %s", symbol, fund_err)

        # --- Load the shared ML model (download from GitHub if needed) ---
        model = strat._model  # may already be loaded from disk in __init__
        if model is None:
            log.info("Model not on disk — downloading from GitHub for %s", symbol)
            _download_latest_model()
            try:
                model = joblib.load(strat._model_path)
                strat._model = model
                # Re-align the feature list with the freshly downloaded model's
                # metadata (the __init__ alignment ran before the download), so
                # inference matches the exact trained feature set.
                try:
                    with open(strat._model_meta_path) as fh:
                        persisted = json.load(fh).get("features")
                    if isinstance(persisted, list) and persisted:
                        strat.features = list(persisted)
                except Exception:
                    pass
                log.info("Loaded ML model from disk after download for %s", symbol)
            except Exception as load_err:
                log.warning("Could not load ML model for %s: %s", symbol, load_err)

        if model is None:
            log.warning("No trained model available — cannot predict for %s", symbol)
            raise PredictionUnavailable(
                f"⚠️ The prediction model is temporarily unavailable.\n\n"
                f"Please try <b>/predict {symbol}</b> again in a few minutes."
            )

        # --- Direct model inference (bypass cross-sectional ranking) ---
        # MLReturnPredictorStrategy.generate_signals ranks across the full universe.
        # With only one symbol, the percentile rank is always 0.5 → direction="close"
        # → strength=0. We bypass that and score the raw model output directly.
        # Build the feature vector from the model's EXACT expected feature list,
        # in the trained order. When train_enabled=False, strat.features is
        # aligned to the persisted model's metadata, so this matches training.
        #
        # Any feature missing for this single ad-hoc ticker — e.g. sector
        # relative-strength columns that are only computed cross-sectionally, or
        # fundamentals that failed to load — is filled with 0.0 (the standardized
        # mean) rather than dropped. Dropping columns shifts/shrinks the vector
        # so model.predict raises, which previously surfaced to users as a
        # misleading "ticker doesn't exist / lacks 50 days of history" error.
        expected_features = list(strat.features)
        if not expected_features:
            log.warning("Model exposes no feature list for %s", symbol)
            raise PredictionUnavailable(
                f"⚠️ The prediction model is temporarily unavailable.\n\n"
                f"Please try <b>/predict {symbol}</b> again in a few minutes."
            )

        last_row = enriched_df.iloc[-1]
        feat_values = {
            f: (float(last_row[f]) if f in enriched_df.columns and pd.notna(last_row[f]) else 0.0)
            for f in expected_features
        }
        # Pass a single-row DataFrame so the model sees the feature names it was
        # trained with (correct column alignment; no sklearn feature-name warning).
        X = pd.DataFrame([feat_values], columns=expected_features)

        try:
            raw_score = float(model.predict(X)[0])
        except Exception:
            # Fallback: some persisted estimators expect a bare numpy array.
            try:
                raw_score = float(model.predict(X.values)[0])
            except Exception as pred_err:
                log.warning("Model prediction failed for %s: %s", symbol, pred_err)
                raise PredictionUnavailable(
                    f"⚠️ The prediction model couldn't score <b>{symbol}</b> right now.\n\n"
                    f"This is on our side. Please try again in a few minutes."
                )

        # raw_score is a cross-sectional rank value in [-1, 1]:
        #   > 0 → bullish (long), < 0 → bearish (short)
        # Strength = abs(raw_score) clipped to [0, 1]
        side = "long" if raw_score >= 0 else "short"
        strength = float(min(abs(raw_score), 1.0))
        predicted_return_pct = round(raw_score * 100, 2)

        # Best-effort feature explanations (raw values; only features that were
        # actually present for this ticker, so we don't surface 0.0-filled gaps).
        present = {
            f: float(last_row[f])
            for f in expected_features
            if f in enriched_df.columns and pd.notna(last_row[f])
        }
        strat._last_feature_values = {symbol: present}
        strat._last_feature_zscores = {symbol: present}
        explanations = strat._build_explanations(symbol)

        sector_map = get_sector_map()
        sector = sector_map.get(symbol, "Unknown")
        name = _get_ticker_name(symbol)

        return PredictionItem(
            symbol=symbol,
            strength=strength,
            side=side,
            sector=sector,
            name=name,
            predicted_return_pct=predicted_return_pct,
            explanations=explanations,
        )
    except PredictionUnavailable:
        # Already carries an accurate, user-facing message — let it propagate.
        raise
    except Exception as e:
        log.exception("Failed to run dynamic prediction for %s: %s", symbol, e)
        raise PredictionUnavailable(
            f"⚠️ Something went wrong generating a prediction for <b>{symbol}</b>.\n\n"
            f"This is on our side, not your ticker. Please try again shortly."
        )

def _signal_one_liner(signal: PredictionItem) -> str:
    """Plain-English 'why' line for a single predicted stock (no leading bullet)."""
    summary = build_plain_summary(signal.side, signal.explanations)
    if summary:
        lead = "Bullish" if signal.side == "long" else "Bearish"
        return f"{lead} — {summary}."
    return "Bullish signal." if signal.side == "long" else "Bearish signal."


def format_prediction_msg(signal: PredictionItem) -> str:
    """Format a PredictionItem into a formatted HTML string."""
    side_word = "Bullish 🟢" if signal.side == "long" else "Bearish 🔴"
    msg = (
        f"📊 <b>ML Prediction for {signal.symbol} ({signal.name})</b>\n\n"
        f"• <b>Signal:</b> {side_word}\n"
        f"• <b>Strength:</b> {signal.strength:.2%}\n"
        f"• <b>Predicted 21d Return:</b> {signal.predicted_return_pct:+.2f}%\n"
        f"• <b>Sector:</b> {signal.sector}\n"
    )

    # Plain-English summary line so non-expert users understand the call.
    summary = build_plain_summary(signal.side, signal.explanations)
    if summary:
        msg += f"\n💡 <b>In plain terms:</b> {summary}.\n"

    if signal.explanations:
        msg += "\n<b>What's driving it:</b>\n"
        for exp in signal.explanations[:3]:
            label, meaning = humanize_driver(exp.feature, exp.direction)
            msg += f"• <b>{label}:</b> {meaning}\n"

    msg += (
        "\n<i>Strength = model conviction (higher = stronger signal). "
        "Not financial advice.</i>"
    )
    return msg

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and instructions."""
    msg = (
        "👋 <b>Welcome to Quantify Prediction Bot!</b>\n\n"
        "I provide ML-powered stock price predictions. You can add me to groups/channels or query me directly here.\n\n"
        "💬 <b>Commands:</b>\n"
        "• /predict &lt;SYMBOL&gt; - Get details & explanations for a ticker (e.g. <code>/predict TSLA</code>)\n"
        "• /top - View top 10 bullish predictions of the day\n"
        "• /bottom - View top 10 bearish predictions of the day\n"
        "• /subscribe - Subscribe this chat to daily prediction signals\n"
        "• /unsubscribe - Stop receiving daily summaries\n"
        "• /fullscan - Run a live full 500-stock S&P 500 scan (results sent when ready)\n"
        "• /help - Display this help message"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display help information."""
    await start_cmd(update, context)

async def predict_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retrieve prediction for a specific ticker: /predict AAPL"""
    if not context.args:
        await update.message.reply_text("Usage: /predict <SYMBOL>")
        return
        
    symbol = context.args[0].upper()
    chat_key = f"chat_{update.effective_chat.id}"
    user_key = f"user_{update.effective_user.id}"
    
    # Enforce rate-limits
    if not check_rate_limit(chat_key) or not check_rate_limit(user_key):
        await update.message.reply_text(
            "⚠️ <b>Rate limit reached.</b> You are sending commands too quickly. Please wait a moment and try again.",
            parse_mode="HTML"
        )
        return

    db = SessionLocal()
    try:
        # Step 1: Check the pre-computed top 100 S&P 500 cache
        from api.routers.predict import _load_prediction_cache
        cache_result, _ = _load_prediction_cache(db, mode="previous_close")
        
        signal = None
        if cache_result and cache_result.signals:
            candidate = next((s for s in cache_result.signals if s.symbol == symbol), None)
            # Guard: only accept the cached signal if it has real non-zero values.
            # A strength and return of 0 means the cache was populated before the
            # ML model had been trained/downloaded — treat it as a cache miss.
            if candidate and not (candidate.strength == 0.0 and candidate.predicted_return_pct == 0.0):
                signal = candidate

        # Step 2: Check the ad-hoc database cache (4-hour TTL)
        if not signal:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
            cached_adhoc = db.query(AdhocPredictionCache).filter(
                AdhocPredictionCache.symbol == symbol,
                AdhocPredictionCache.created_at >= cutoff
            ).first()
            if cached_adhoc:
                try:
                    signal_dict = json.loads(cached_adhoc.result_json)
                    candidate = PredictionItem(**signal_dict)
                    # Apply same guard to ad-hoc cache
                    if not (candidate.strength == 0.0 and candidate.predicted_return_pct == 0.0):
                        signal = candidate
                        log.info("Ad-hoc cache hit for ticker %s", symbol)
                    else:
                        log.info("Ad-hoc cache for %s has zero values, recomputing.", symbol)
                except Exception:
                    log.warning("Failed to deserialize ad-hoc cache for %s", symbol)

        # Step 3: Serve from cache if available
        if signal:
            msg = format_prediction_msg(signal)
            await update.message.reply_text(msg, parse_mode="HTML")
            return

        # Step 4: Run live computation with concurrency controls
        status_msg = await update.message.reply_text(
            f"🔍 <b>Generating live ML prediction for {symbol}...</b>\n"
            f"<i>This takes about 2-3 seconds to fetch data and compute indicators.</i>",
            parse_mode="HTML"
        )
        
        # Concurrency safety: limit parallel executions to avoid memory/CPU spikes
        try:
            async with prediction_semaphore:
                # Run the synchronous prediction logic in a background thread to prevent blocking
                signal = await asyncio.to_thread(predict_single_ticker, symbol)
        except PredictionUnavailable as exc:
            # Accurate, reason-specific message (invalid ticker, too new, or a
            # transient model/internal issue) — never the old catch-all.
            await status_msg.edit_text(exc.user_message, parse_mode="HTML")
            return

        if not signal:
            await status_msg.edit_text(
                f"❌ Couldn't generate a prediction for <b>{symbol}</b> right now. "
                f"Please try again shortly.",
                parse_mode="HTML"
            )
            return

        # Cache the new ad-hoc prediction in the DB
        try:
            db.query(AdhocPredictionCache).filter(AdhocPredictionCache.symbol == symbol).delete()
            new_cache = AdhocPredictionCache(
                symbol=symbol,
                result_json=json.dumps(signal.model_dump())
            )
            db.add(new_cache)
            db.commit()
            log.info("Saved ad-hoc prediction cache for %s", symbol)
        except Exception as cache_err:
            db.rollback()
            log.error("Failed to save ad-hoc prediction cache for %s: %s", symbol, cache_err)

        # Format and send final message (edit the status message)
        msg = format_prediction_msg(signal)
        await status_msg.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        log.exception("Error in predict_cmd for symbol %s: %s", symbol, e)
        await update.message.reply_text("⚠️ Failed to load prediction details.")
    finally:
        db.close()

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display top bullish predictions."""
    db = SessionLocal()
    try:
        from api.routers.predict import _load_prediction_cache, _is_computing, _run_and_cache_predictions
        cache_result, _ = _load_prediction_cache(db, mode="previous_close")

        if not cache_result or not cache_result.signals:
            chat_id = str(update.effective_chat.id)
            add_pending_result_notification(chat_id)
            if not _is_computing:
                asyncio.create_task(asyncio.to_thread(_run_and_cache_predictions, "bot"))
            await update.message.reply_text(
                "⏳ <b>Predictions are being computed now.</b>\n\n"
                "This usually takes 2–3 minutes for the full 500-stock universe. "
                "I'll send you the results here as soon as they're ready!",
                parse_mode="HTML",
            )
            return

        longs = [s for s in cache_result.signals if s.side == "long"]
        if not longs:
            await update.message.reply_text("ℹ️ No bullish predictions found.")
            return

        msg = f"🟢 <b>Top Bullish Predictions ({cache_result.date})</b>\n\n"
        for i, s in enumerate(longs[:10], 1):
            msg += (
                f"{i}. <b>{s.symbol}</b> ({s.name})\n"
                f"   • Return: {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"
            )
            summary = build_plain_summary(s.side, s.explanations)
            if summary:
                msg += f"   <i>{summary}</i>\n"

        msg += "\n<i>Tap /predict &lt;SYMBOL&gt; for a full breakdown.</i>"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in top_cmd: %s", e)
        await update.message.reply_text("⚠️ Failed to load top predictions.")
    finally:
        db.close()

async def bottom_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display top bearish predictions."""
    db = SessionLocal()
    try:
        from api.routers.predict import _load_prediction_cache, _is_computing, _run_and_cache_predictions
        cache_result, _ = _load_prediction_cache(db, mode="previous_close")

        if not cache_result or not cache_result.signals:
            chat_id = str(update.effective_chat.id)
            add_pending_result_notification(chat_id)
            if not _is_computing:
                asyncio.create_task(asyncio.to_thread(_run_and_cache_predictions, "bot"))
            await update.message.reply_text(
                "⏳ <b>Predictions are being computed now.</b>\n\n"
                "This usually takes 2–3 minutes for the full 500-stock universe. "
                "I'll send you the results here as soon as they're ready!",
                parse_mode="HTML",
            )
            return

        shorts = [s for s in cache_result.signals if s.side == "short"]
        if not shorts:
            await update.message.reply_text("ℹ️ No bearish predictions found.")
            return

        msg = f"🔴 <b>Top Bearish Predictions ({cache_result.date})</b>\n\n"
        for i, s in enumerate(shorts[:10], 1):
            msg += (
                f"{i}. <b>{s.symbol}</b> ({s.name})\n"
                f"   • Return: {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"
            )
            summary = build_plain_summary(s.side, s.explanations)
            if summary:
                msg += f"   <i>{summary}</i>\n"

        msg += "\n<i>Tap /predict &lt;SYMBOL&gt; for a full breakdown.</i>"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.exception("Error in bottom_cmd: %s", e)
        await update.message.reply_text("⚠️ Failed to load bottom predictions.")
    finally:
        db.close()

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe current chat to receive daily predictions."""
    chat_id = str(update.effective_chat.id)
    chat_title = update.effective_chat.title or "Private Chat"
    db = SessionLocal()
    try:
        existing = db.query(PredictionSubscription).filter(PredictionSubscription.chat_id == chat_id).first()
        if existing:
            await update.message.reply_text("🔔 This chat is already subscribed to daily prediction signals!")
        else:
            sub = PredictionSubscription(chat_id=chat_id)
            db.add(sub)
            db.commit()
            await update.message.reply_text(
                f"✅ Subscribed successfully!\n\nThis chat ({chat_title}) will now receive automated daily prediction summaries when they are computed."
            )
    except Exception as e:
        db.rollback()
        log.exception("Failed to subscribe chat %s: %s", chat_id, e)
        await update.message.reply_text("⚠️ An error occurred while subscribing. Please try again.")
    finally:
        db.close()

async def unsubscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribe current chat from daily predictions."""
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    try:
        sub = db.query(PredictionSubscription).filter(PredictionSubscription.chat_id == chat_id).first()
        if sub:
            db.delete(sub)
            db.commit()
            await update.message.reply_text("🔕 Unsubscribed successfully. You will no longer receive automated daily prediction signals.")
        else:
            await update.message.reply_text("ℹ️ This chat is not currently subscribed.")
    except Exception as e:
        db.rollback()
        log.exception("Failed to unsubscribe chat %s: %s", chat_id, e)
        await update.message.reply_text("⚠️ An error occurred while unsubscribing. Please try again.")
    finally:
        db.close()

async def broadcast_predictions(result=None):
    """Broadcast daily predictions to all subscribed chats."""
    if not BOT_TOKEN:
        log.warning("Cannot broadcast: TELEGRAM_PREDICTION_BOT_TOKEN not set.")
        return

    db = SessionLocal()
    try:
        if not result:
            from api.routers.predict import _load_prediction_cache
            result, _ = _load_prediction_cache(db, "previous_close")

        if not result or not result.signals:
            log.warning("No predictions available to broadcast.")
            return

        longs = [s for s in result.signals if s.side == "long"]
        shorts = [s for s in result.signals if s.side == "short"]

        msg = (
            "📊 <b>Daily ML Prediction Signals</b>\n"
            f"📅 <b>Date:</b> {result.date}\n"
            f"📈 <b>Universe Size:</b> {result.universe_size} stocks\n"
            "───────────────────\n\n"
            "🟢 <b>Top Long Predictions (Buy)</b>\n"
        )
        for i, s in enumerate(longs[:5], 1):
            msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% 21d | Strength: {s.strength:.2%}\n"
            summary = build_plain_summary(s.side, s.explanations)
            if summary:
                msg += f"   <i>{summary}</i>\n"

        msg += "\n🔴 <b>Top Short Predictions (Sell)</b>\n"
        for i, s in enumerate(shorts[:5], 1):
            msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% 21d | Strength: {s.strength:.2%}\n"
            summary = build_plain_summary(s.side, s.explanations)
            if summary:
                msg += f"   <i>{summary}</i>\n"

        msg += (
            "\n<i>Strength = model conviction. Type /predict &lt;SYMBOL&gt; for a full breakdown. "
            "Not financial advice.</i>"
        )

        subscriptions = db.query(PredictionSubscription).all()
        if not subscriptions:
            log.info("No subscribed chats to broadcast predictions to.")
            return

        log.info(f"Broadcasting daily predictions to {len(subscriptions)} chats...")
        bot = Bot(token=BOT_TOKEN)

        for sub in subscriptions:
            try:
                await bot.send_message(chat_id=sub.chat_id, text=msg, parse_mode="HTML")
                log.info(f"Broadcast sent successfully to chat {sub.chat_id}")
            except Exception as e:
                log.error(f"Failed to send broadcast to {sub.chat_id}: {e}")
                if "chat not found" in str(e).lower() or "bot was blocked" in str(e).lower() or "kicked" in str(e).lower():
                    log.info(f"Removing inactive subscription for chat {sub.chat_id}")
                    try:
                        # Re-fetch sub to delete in a separate transaction
                        sub_to_del = db.query(PredictionSubscription).filter(PredictionSubscription.chat_id == sub.chat_id).first()
                        if sub_to_del:
                            db.delete(sub_to_del)
                            db.commit()
                    except Exception as clean_err:
                        db.rollback()
                        log.error(f"Failed to clean up subscription {sub.chat_id}: {clean_err}")

    except Exception as e:
        log.exception("Error in broadcast_predictions: %s", e)
    finally:
        db.close()

async def _send_fullscan_result(chat_id: str, result_json: Optional[str], error: Optional[str]):
    """Send the completed full 500-stock screener results to a Telegram chat."""
    if not BOT_TOKEN:
        return
    bot = Bot(token=BOT_TOKEN)

    if error or not result_json:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ <b>Full scan failed.</b>\n\nPlease try again later.",
            parse_mode="HTML",
        )
        return

    try:
        from api.schemas import PredictionResponse
        result = PredictionResponse(**json.loads(result_json))
    except Exception:
        await bot.send_message(chat_id=chat_id, text="⚠️ Failed to parse screener results.", parse_mode="HTML")
        return

    longs = [s for s in result.signals if s.side == "long"]
    shorts = [s for s in result.signals if s.side == "short"]

    def _news_line(s) -> str:
        if not s.news:
            return ""
        emoji = {"BULLISH": "📰🟢", "BEARISH": "📰🔴"}.get(s.news.label, "📰")
        line = f"   {emoji} <b>{s.news.label}</b>"
        if s.news.headlines:
            line += f" · <i>{s.news.headlines[0][:80]}</i>"
        return line + "\n"

    msg = (
        f"✅ <b>Full 500-Stock Scan Complete</b>\n"
        f"📅 <b>Date:</b> {result.date}\n"
        f"📈 <b>Universe:</b> {result.universe_size} stocks\n"
        "───────────────────\n\n"
        "🟢 <b>Top Longs</b>\n"
    )
    for i, s in enumerate(longs[:8], 1):
        msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"
        summary = build_plain_summary(s.side, s.explanations)
        if summary:
            msg += f"   <i>{summary}</i>\n"
        msg += _news_line(s)

    msg += "\n🔴 <b>Top Shorts</b>\n"
    for i, s in enumerate(shorts[:8], 1):
        msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"
        summary = build_plain_summary(s.side, s.explanations)
        if summary:
            msg += f"   <i>{summary}</i>\n"
        msg += _news_line(s)

    msg += "\n<i>Use /predict &lt;SYMBOL&gt; for detailed analysis on any stock.</i>"

    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")


async def fullscan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger the full 500-stock screener via GitHub Actions: /fullscan"""
    chat_id = str(update.effective_chat.id)
    chat_key = f"chat_{chat_id}"
    user_key = f"user_{update.effective_user.id}"

    if not check_rate_limit(chat_key) or not check_rate_limit(user_key):
        await update.message.reply_text(
            "⚠️ <b>Rate limit reached.</b> Please wait a moment and try again.",
            parse_mode="HTML",
        )
        return

    # Check GitHub integration is configured
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_WORKFLOW_TOKEN") or os.getenv("GITHUB_TOKEN")

    if not repo or not token:
        await update.message.reply_text(
            "⚠️ <b>GitHub Actions not configured.</b>\n\n"
            "Set GITHUB_REPOSITORY and GH_WORKFLOW_TOKEN (or GITHUB_TOKEN) env vars. "
            "Try /top for cached results.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        "🔍 <b>Full 500-stock scan triggered!</b>\n\n"
        "I'm dispatching the screener to GitHub Actions now. "
        "This takes about 2-3 minutes. I'll send you the results here when it's done — no need to wait.",
        parse_mode="HTML",
    )

    # Create a pending job record in DB
    db = SessionLocal()
    try:
        from api.models import AsyncPredictionJob
        job = AsyncPredictionJob(chat_id=chat_id, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    except Exception as e:
        log.error("Failed to create job record for chat_id=%s: %s", chat_id, e)
        db.rollback()
        job_id = 0
    finally:
        db.close()

    # Dispatch the workflow directly via GitHub Actions API
    heroku_url = os.getenv("HEROKU_APP_URL", "").rstrip("/")
    internal_secret = os.getenv("INTERNAL_API_SECRET", "")
    callback_url = f"{heroku_url}/api/internal/job-complete" if heroku_url else ""

    payload = json.dumps({
        "ref": "main",
        "inputs": {
            "chat_id": chat_id,
            "job_id": str(job_id),
            "heroku_callback_url": callback_url,
            "internal_secret": internal_secret,
        }
    }).encode()

    url = f"https://api.github.com/repos/{repo}/actions/workflows/full_screener.yml/dispatches"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
        log.info("Triggered full_screener workflow for chat_id=%s job_id=%d", chat_id, job_id)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        log.error("GitHub API error triggering workflow: HTTP %d — %s", e.code, error_body)
        await update.message.reply_text(
            f"⚠️ <b>GitHub API error ({e.code}).</b>\n\n"
            "The workflow token may lack permissions. Ensure GH_WORKFLOW_TOKEN has <code>actions:write</code> scope.",
            parse_mode="HTML",
        )
    except Exception as e:
        log.error("Failed to trigger screener for chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(
            "⚠️ <b>Could not start the scan.</b>\n\nPlease try again later, or use /top for cached results.",
            parse_mode="HTML",
        )


# Chat IDs waiting for the next completed prediction run (populated by top/bottom when cache is cold)
_pending_result_chats: set[str] = set()


def add_pending_result_notification(chat_id: str) -> None:
    _pending_result_chats.add(chat_id)


async def _send_results_to_pending_chats(result) -> None:
    """Notify chats that were waiting for predictions after a cold-cache request."""
    global _pending_result_chats
    if not _pending_result_chats or not BOT_TOKEN:
        return

    chats_to_notify = _pending_result_chats.copy()
    _pending_result_chats.clear()

    longs = [s for s in result.signals if s.side == "long"]
    shorts = [s for s in result.signals if s.side == "short"]

    msg = (
        f"✅ <b>Predictions are ready!</b>\n"
        f"📅 <b>Date:</b> {result.date} · {result.universe_size} stocks\n"
        "───────────────────\n\n"
        "🟢 <b>Top Longs</b>\n"
    )
    for i, s in enumerate(longs[:5], 1):
        msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"
    msg += "\n🔴 <b>Top Shorts</b>\n"
    for i, s in enumerate(shorts[:5], 1):
        msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"
    msg += "\n<i>Use /top and /bottom for the full list, or /predict &lt;SYMBOL&gt; for details.</i>"

    bot = Bot(token=BOT_TOKEN)
    for chat_id in chats_to_notify:
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            log.info("Sent pending-result notification to chat %s", chat_id)
        except Exception as e:
            log.error("Failed to notify pending chat %s: %s", chat_id, e)


# Global bot application instance
prediction_app = None

async def start_prediction_bot():
    """Initialize and start the telegram prediction bot polling in the background."""
    global prediction_app
    if not BOT_TOKEN:
        log.warning("No TELEGRAM_PREDICTION_BOT_TOKEN set. Telegram Prediction integration disabled.")
        return
        
    log.info("Starting Telegram Prediction Bot poller...")
    prediction_app = Application.builder().token(BOT_TOKEN).build()
    prediction_app.add_handler(CommandHandler("start", start_cmd))
    prediction_app.add_handler(CommandHandler("help", help_cmd))
    prediction_app.add_handler(CommandHandler("predict", predict_cmd))
    prediction_app.add_handler(CommandHandler("top", top_cmd))
    prediction_app.add_handler(CommandHandler("bottom", bottom_cmd))
    prediction_app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    prediction_app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    prediction_app.add_handler(CommandHandler("fullscan", fullscan_cmd))

    await prediction_app.initialize()
    await prediction_app.start()
    await prediction_app.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram Prediction Bot is polling for commands.")

async def stop_prediction_bot():
    """Stop the telegram prediction bot polling."""
    global prediction_app
    if prediction_app:
        await prediction_app.updater.stop()
        await prediction_app.stop()
        await prediction_app.shutdown()
