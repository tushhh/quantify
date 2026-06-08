import os
import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from api.database import SessionLocal
from api.models import PredictionSubscription

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prediction_bot")

BOT_TOKEN = os.getenv("TELEGRAM_PREDICTION_BOT_TOKEN")

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
    db = SessionLocal()
    try:
        from api.routers.predict import _load_prediction_cache
        cache_result, _ = _load_prediction_cache(db, mode="previous_close")
        if not cache_result or not cache_result.signals:
            await update.message.reply_text("⚠️ No predictions available at this time. Run predictions from the dashboard first.")
            return
            
        signal = next((s for s in cache_result.signals if s.symbol == symbol), None)
        if signal:
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
            
            await update.message.reply_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ Could not find prediction details for '{symbol}'.")
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
            f"📊 <b>Daily ML Prediction Signals</b>\n"
            f"📅 <b>Date:</b> {result.date}\n"
            f"📈 <b>Universe Size:</b> {result.universe_size} stocks\n"
            f"───────────────────\n\n"
            f"🟢 <b>Top Long Predictions (Buy)</b>\n"
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
