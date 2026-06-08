import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from api.database import SessionLocal
from api.models import PredictionSubscription, AdhocPredictionCache
from api.schemas import PredictionItem

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prediction_bot")

BOT_TOKEN = os.getenv("TELEGRAM_PREDICTION_BOT_TOKEN")

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
    
    Runs inside a background thread pool via asyncio.to_thread.
    """
    try:
        from quantify.data.providers.yfinance_provider import YFinanceProvider
        from quantify.data.cache import ParquetCache
        from quantify.data.features import FeatureEngine
        from quantify.data.universe import get_sector_map
        from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
        from api.routers.predict import _latest_completed_session_date, _get_ticker_name

        now_utc = datetime.now(timezone.utc)
        session_date = _latest_completed_session_date(now_utc)
        
        # 3 years lookback for ML training features
        end_dt = datetime.combine(session_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        start_dt = end_dt - timedelta(days=365 * 3)

        strat = MLReturnPredictorStrategy(universe=[symbol], train_enabled=False)

        cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
        provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))
        data = provider.get_multiple([symbol], start=start_dt, end=end_dt)

        if not data or symbol not in data or data[symbol].empty:
            log.warning("No market data returned for ad-hoc ticker %s", symbol)
            return None

        df = data[symbol]
        # Require a minimum history to compute technical indicator features safely
        if len(df) < 50:
            log.warning("Insufficient history for ad-hoc ticker %s: %d rows", symbol, len(df))
            return None

        required = strat.get_required_features()
        engine = FeatureEngine()
        features = engine.compute(data, required=list(required))

        feat_df = features.get(symbol)
        if feat_df is not None:
            enriched = {symbol: df.join(feat_df, how="left", rsuffix="_feat")}
        else:
            enriched = {symbol: df}

        signals = strat.generate_signals(enriched)
        if not signals:
            log.warning("No signals generated for ad-hoc ticker %s", symbol)
            return None

        s = signals[0]
        sector_map = get_sector_map()
        sector = sector_map.get(symbol, "Unknown")
        pred_return = s.metadata.get("predicted_return_1d", s.metadata.get("predicted_return_5d", 0.0)) if s.metadata else 0.0
        explanations = s.metadata.get("explanations", []) if s.metadata else []
        name = _get_ticker_name(symbol)

        return PredictionItem(
            symbol=symbol,
            strength=s.strength,
            side=s.direction,
            sector=sector,
            name=name,
            predicted_return_pct=round(float(pred_return) * 100, 2),
            explanations=explanations,
        )
    except Exception as e:
        log.exception("Failed to run dynamic prediction for %s: %s", symbol, e)
        return None

def format_prediction_msg(signal: PredictionItem) -> str:
    """Format a PredictionItem into a formatted HTML string."""
    msg = (
        f"📊 <b>ML Prediction for {signal.symbol} ({signal.name})</b>\n\n"
        f"• <b>Side:</b> {signal.side.upper()}\n"
        f"• <b>Strength:</b> {signal.strength:.2%}\n"
        f"• <b>Predicted 1d Return:</b> {signal.predicted_return_pct:+.2f}%\n"
        f"• <b>Sector:</b> {signal.sector}\n"
    )
    if signal.explanations:
        msg += "\n<b>Key Drivers:</b>\n"
        for exp in signal.explanations[:3]:
            sign = "+" if exp.zscore >= 0 else ""
            msg += f"• <i>{exp.feature}</i>: z-score = {sign}{exp.zscore:.2f} ({exp.direction})\n"
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
            signal = next((s for s in cache_result.signals if s.symbol == symbol), None)
            
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
                    signal = PredictionItem(**signal_dict)
                    log.info("Ad-hoc cache hit for ticker %s", symbol)
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
        async with prediction_semaphore:
            # Run the synchronous prediction logic in a background thread to prevent blocking
            signal = await asyncio.to_thread(predict_single_ticker, symbol)
            
        if not signal:
            await status_msg.edit_text(
                f"❌ Failed to generate prediction for <b>{symbol}</b>.\n\n"
                f"Please verify it is a valid ticker symbol and has at least 50 days of daily history.",
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
        from api.routers.predict import _load_prediction_cache
        cache_result, _ = _load_prediction_cache(db, mode="previous_close")
        if not cache_result or not cache_result.signals:
            await update.message.reply_text("⚠️ No predictions available at this time. Run predictions from the dashboard first.")
            return

        longs = [s for s in cache_result.signals if s.side == "long"]
        if not longs:
            await update.message.reply_text("ℹ️ No bullish predictions found.")
            return

        msg = f"🟢 <b>Top Bullish Predictions ({cache_result.date})</b>\n\n"
        for i, s in enumerate(longs[:10], 1):
            msg += f"{i}. <b>{s.symbol}</b> ({s.name})\n   • Return: {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"

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
        from api.routers.predict import _load_prediction_cache
        cache_result, _ = _load_prediction_cache(db, mode="previous_close")
        if not cache_result or not cache_result.signals:
            await update.message.reply_text("⚠️ No predictions available at this time. Run predictions from the dashboard first.")
            return

        shorts = [s for s in cache_result.signals if s.side == "short"]
        if not shorts:
            await update.message.reply_text("ℹ️ No bearish predictions found.")
            return

        msg = f"🔴 <b>Top Bearish Predictions ({cache_result.date})</b>\n\n"
        for i, s in enumerate(shorts[:10], 1):
            msg += f"{i}. <b>{s.symbol}</b> ({s.name})\n   • Return: {s.predicted_return_pct:+.2f}% | Strength: {s.strength:.2%}\n"

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
            msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% 1d | Strength: {s.strength:.2%}\n"

        msg += "\n🔴 <b>Top Short Predictions (Sell)</b>\n"
        for i, s in enumerate(shorts[:5], 1):
            msg += f"{i}. <b>{s.symbol}</b> | {s.predicted_return_pct:+.2f}% 1d | Strength: {s.strength:.2%}\n"

        msg += (
            "\n<i>Type /predict &lt;SYMBOL&gt; in this chat to see detailed analysis for any stock!</i>"
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
