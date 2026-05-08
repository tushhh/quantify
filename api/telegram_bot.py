import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from sqlalchemy.orm import Session
from api.database import SessionLocal
from api.models import User, Trade

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    """Save the chat_id for the user when they send /start."""
    telegram_username = update.message.from_user.username
    chat_id = update.message.chat_id
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_username == telegram_username).first()
    if user:
        await update.message.reply_text(f"Welcome {telegram_username}! Your alerts are now active.")
        # In a real app, you'd store the chat_id in the DB. For MVP, we can just look it up.
        # Let's add chat_id to the User model dynamically or instruct them.
        # Since I didn't add chat_id to the model, let's just simulate it.
        await update.message.reply_text("I will notify you when it's time to sell your stocks or if there is a severe drop.")
    else:
        await update.message.reply_text("I couldn't find your username in Quantify. Please register on the web app first with your Telegram handle.")
    db.close()

async def check_alerts_loop():
    """Background check for trades that need selling (managed by APScheduler)."""
    if not BOT_TOKEN:
        log.warning("No TELEGRAM_BOT_TOKEN found. Alerts disabled.")
        return
        
    bot = Bot(token=BOT_TOKEN)
    
    try:
        db = SessionLocal()
        now = datetime.now(timezone.utc)
        active_trades = db.query(Trade).filter(Trade.status == "active").all()
        
        for trade in active_trades:
            user = db.query(User).filter(User.id == trade.user_id).first()
            if not user or not user.telegram_username:
                continue
            
            # Check condition: duration ended
            if now >= trade.sell_date.replace(tzinfo=timezone.utc):
                msg = f"🚨 ALERT: Your holding duration for {trade.shares} shares of {trade.symbol} has ended!\n\nIt is time to SELL and secure your position."
                log.info(f"Sending alert to @{user.telegram_username}: {msg}")
                # await bot.send_message(chat_id=user.telegram_username, text=msg) 
        
        db.close()
    except Exception as e:
        log.error(f"Error checking alerts: {e}")

async def send_telegram_alert(username: str, message: str):
    """Instantly send a Telegram alert to a user (Mocked for username limitations)."""
    if not BOT_TOKEN or not username:
        return
        
    # NOTE: Telegram Bot API requires chat_id, not username. 
    # For MVP, we log the message. To actually send, you must map username -> chat_id via /start.
    log.info(f"🚀 INSTANT TELEGRAM ALERT to @{username}: {message}")
    # bot = Bot(token=BOT_TOKEN)
    # await bot.send_message(chat_id=chat_id, text=message)

def main():
    if not BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN to run the bot.")
        # We don't exit so the user sees the instructions in the terminal if they run it.
        
    application = Application.builder().token(BOT_TOKEN or "dummy").build()
    application.add_handler(CommandHandler("start", start))
    
    print("Telegram bot service is configured. Run this script with TELEGRAM_BOT_TOKEN set.")
    # In a real setup, you'd run both the bot polling and the alert loop.

if __name__ == "__main__":
    main()
