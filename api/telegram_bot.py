import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from sqlalchemy.orm import Session
from api.database import SessionLocal
from api.models import User, Trade

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the chat_id for the user when they send /start."""
    telegram_username = update.message.from_user.username
    chat_id = str(update.message.chat_id)
    
    if not telegram_username:
        await update.message.reply_text("You need a Telegram username set in your profile settings to connect to Quantify.")
        return
        
    db = SessionLocal()
    # Handle the case where user stored username with or without '@'
    user = db.query(User).filter(
        (User.telegram_username == telegram_username) | 
        (User.telegram_username == f"@{telegram_username}")
    ).first()
    
    if user:
        user.telegram_chat_id = chat_id
        db.commit()
        await update.message.reply_text(f"✅ Welcome to Quantify, @{telegram_username}! Your device is now connected. You will receive automated buy/sell alerts here.")
    else:
        await update.message.reply_text(f"❌ I couldn't find your username (@{telegram_username}) in Quantify. Please go to your Account Settings on the dashboard and enter your exact Telegram username, then come back here and type /start again.")
    db.close()

async def check_alerts_loop():
    """Background check for trades that need selling (managed by APScheduler)."""
    if not BOT_TOKEN:
        return
        
    bot = Bot(token=BOT_TOKEN)
    
    try:
        db = SessionLocal()
        now = datetime.now(timezone.utc)
        active_trades = db.query(Trade).filter(Trade.status == "active").all()
        
        for trade in active_trades:
            user = db.query(User).filter(User.id == trade.user_id).first()
            if not user or not user.telegram_chat_id:
                continue
            
            # Check condition: duration ended
            if now >= trade.sell_date.replace(tzinfo=timezone.utc):
                msg = f"🚨 ALERT: Your holding duration for {trade.shares} shares of {trade.symbol} has ended!\n\nIt is time to SELL and secure your position."
                log.info(f"Sending alert to chat {user.telegram_chat_id}: {msg}")
                try:
                    await bot.send_message(chat_id=user.telegram_chat_id, text=msg)
                    # Mark trade as alerted or closed so we don't spam. For MVP, we'll just log.
                except Exception as e:
                    log.error(f"Failed to send to {user.telegram_chat_id}: {e}")
        
        db.close()
    except Exception as e:
        log.error(f"Error checking alerts: {e}")

async def send_telegram_alert(username: str, message: str):
    """Instantly send a Telegram alert to a user using their saved chat_id."""
    if not BOT_TOKEN or not username:
        return
        
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_username == username).first()
    db.close()
    
    if user and user.telegram_chat_id:
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=user.telegram_chat_id, text=message)
            log.info(f"🚀 INSTANT TELEGRAM ALERT sent to @{username}")
        except Exception as e:
            log.error(f"Failed to send instant alert to @{username}: {e}")
    else:
        log.warning(f"Could not send instant alert to @{username}: No chat_id found. They need to /start the bot.")

# Global bot application instance
telegram_app = None

async def start_telegram_bot():
    """Initialize and start the telegram bot polling in the background."""
    global telegram_app
    if not BOT_TOKEN:
        log.warning("No TELEGRAM_BOT_TOKEN set. Telegram integration disabled.")
        return
        
    log.info("Starting Telegram Bot poller...")
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_cmd))
    
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram Bot is polling for /start commands.")

async def stop_telegram_bot():
    """Stop the telegram bot polling."""
    global telegram_app
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
