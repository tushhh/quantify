import os
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Bot, Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
)
from api.database import SessionLocal
from api.models import User, Trade
from api.market_data import fetch_latest_prices
from api.hold_utils import hold_days_from_unit

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ── Conversation states ────────────────────────────────────────────────────────
BUY_TICKER, BUY_SHARES, BUY_PRICE = range(3)
SELL_TICKER, SELL_QTY, SELL_PRICE = range(10, 13)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_by_chat_id(chat_id: str):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()


async def _require_linked_account(update: Update) -> bool:
    """Reply with an error if the user hasn't linked their account. Returns True if OK."""
    chat_id = str(update.message.chat_id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()
    if not user:
        await update.message.reply_text(
            "❌ Your Telegram account isn't linked to Quantify yet.\n"
            "Go to Account Settings on the dashboard, enter your Telegram username, then send /start here."
        )
        return False
    return True


# ── /start ────────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the chat_id for the user when they send /start."""
    telegram_username = update.message.from_user.username
    chat_id = str(update.message.chat_id)

    if not telegram_username:
        await update.message.reply_text("You need a Telegram username set in your profile settings to connect to Quantify.")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            (User.telegram_username == telegram_username) |
            (User.telegram_username == f"@{telegram_username}")
        ).first()

        if user:
            user.telegram_chat_id = chat_id
            db.commit()
            await update.message.reply_text(
                f"✅ Welcome to Quantify, @{telegram_username}! Your device is now connected. You will receive automated buy/sell alerts here.\n\n"
                f"Commands:\n"
                f"/buy — log a new buy\n"
                f"/sell — record a sell\n"
                f"/portfolio — view your positions & P&L\n"
                f"/cancel — cancel any command"
            )
        else:
            await update.message.reply_text(
                f"❌ I couldn't find your username (@{telegram_username}) in Quantify. Please go to your Account Settings on the dashboard and enter your exact Telegram username, then come back here and type /start again."
            )
    except Exception as exc:
        db.rollback()
        log.exception("Failed to link Telegram chat for @%s: %s", telegram_username, exc)
        await update.message.reply_text(
            "⚠️ I could not connect your Telegram account right now. Please try /start again in a moment."
        )
    finally:
        db.close()


# ── /cancel ───────────────────────────────────────────────────────────────────

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ Cancelled.")
    return ConversationHandler.END


# ── /buy conversation ─────────────────────────────────────────────────────────

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_linked_account(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "📈 *New Buy*\n\nWhich ticker did you buy? (e.g. AAPL)",
        parse_mode="Markdown",
    )
    return BUY_TICKER


async def buy_got_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sym = update.message.text.strip().upper()
    if not sym.isalpha() or len(sym) > 10:
        await update.message.reply_text("❌ That doesn't look like a valid ticker. Try again (e.g. AAPL):")
        return BUY_TICKER

    # Validate the symbol
    try:
        from api.routers.utils import _is_us_equity
        loop = asyncio.get_event_loop()
        valid, meta = await loop.run_in_executor(None, _is_us_equity, sym)
        if not valid:
            await update.message.reply_text(f"❌ {sym} isn't recognised as a US-listed equity ({meta}). Try a different ticker:")
            return BUY_TICKER
    except Exception:
        pass  # If validation fails, allow it through — the symbol will just work or not

    context.user_data["buy_ticker"] = sym
    await update.message.reply_text(f"✅ {sym}\n\nHow many shares did you buy?")
    return BUY_SHARES


async def buy_got_shares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        shares = float(text)
        if shares <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a positive number of shares (e.g. 10 or 2.5):")
        return BUY_SHARES

    context.user_data["buy_shares"] = shares
    await update.message.reply_text(f"✅ {shares} shares\n\nAt what price per share did you buy? (e.g. 175.50)")
    return BUY_PRICE


async def buy_got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("$", "").strip()
    try:
        price = float(text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a valid price (e.g. 175.50):")
        return BUY_PRICE

    sym = context.user_data["buy_ticker"]
    shares = context.user_data["buy_shares"]
    chat_id = str(update.message.chat_id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            await update.message.reply_text("❌ Account not linked. Send /start first.")
            return ConversationHandler.END

        from api.trade_service import create_or_aggregate_trade
        trade, aggregated, prev_shares, prev_price = create_or_aggregate_trade(
            db=db,
            user_id=user.id,
            symbol=sym,
            shares=shares,
            buy_price=price,
            hold_days=30,
            hold_unit="days",
            hold_value=30,
        )

        if aggregated:
            msg = (
                f"✅ *{sym} position updated*\n\n"
                f"Added {shares} shares @ ${price:.2f}\n"
                f"New total: {trade.shares} shares @ ${trade.buy_price:.2f} avg\n"
                f"_(was {prev_shares} shares @ ${prev_price:.2f})_\n\n"
                f"Hold target: 30 days. Update on the dashboard to change."
            )
        else:
            msg = (
                f"✅ *{sym} logged*\n\n"
                f"{shares} shares @ ${price:.2f}\n"
                f"Sell target: {trade.sell_date.strftime('%d %b %Y')}\n\n"
                f"Hold target defaults to 30 days. Update on the dashboard to change."
            )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as exc:
        log.exception("buy_got_price error: %s", exc)
        db.rollback()
        await update.message.reply_text("⚠️ Something went wrong saving your trade. Please try again.")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END


# ── /sell conversation ────────────────────────────────────────────────────────

async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_linked_account(update):
        return ConversationHandler.END

    chat_id = str(update.message.chat_id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        active = db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.status == "active",
        ).all()
    finally:
        db.close()

    if not active:
        await update.message.reply_text("📭 You have no active positions to sell.")
        return ConversationHandler.END

    lines = ["📉 *Sell*\n\nYour active positions:"]
    for t in active:
        lines.append(f"  • {t.symbol} — {t.shares} shares @ ${t.buy_price:.2f} avg")
    lines.append("\nWhich ticker would you like to sell?")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    return SELL_TICKER


async def sell_got_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sym = update.message.text.strip().upper()
    chat_id = str(update.message.chat_id)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        trade = db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.symbol == sym,
            Trade.status == "active",
        ).first()
        if not trade:
            await update.message.reply_text(
                f"❌ You don't have an active position in {sym}.\nTry a different ticker, or /cancel to exit:"
            )
            return SELL_TICKER

        context.user_data["sell_ticker"] = sym
        context.user_data["sell_trade_id"] = trade.id
        context.user_data["sell_trade_shares"] = trade.shares
        context.user_data["sell_trade_buy_price"] = trade.buy_price
    finally:
        db.close()

    shares = context.user_data["sell_trade_shares"]
    await update.message.reply_text(
        f"✅ {sym} — {shares} shares @ ${context.user_data['sell_trade_buy_price']:.2f} avg\n\n"
        f"How many shares are you selling?\n_(Enter a number or *all* to close the full position)_",
        parse_mode="Markdown",
    )
    return SELL_QTY


async def sell_got_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    total_shares = context.user_data["sell_trade_shares"]

    if text == "all":
        context.user_data["sell_qty"] = "all"
    else:
        try:
            qty = float(text)
            if qty <= 0:
                raise ValueError
            if qty > total_shares:
                await update.message.reply_text(
                    f"❌ You only have {total_shares} shares. Enter a smaller number or *all*:",
                    parse_mode="Markdown",
                )
                return SELL_QTY
            context.user_data["sell_qty"] = qty
        except ValueError:
            await update.message.reply_text("❌ Enter a number of shares or *all*:", parse_mode="Markdown")
            return SELL_QTY

    await update.message.reply_text("At what price per share are you selling? (e.g. 182.00)")
    return SELL_PRICE


async def sell_got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("$", "").strip()
    try:
        sell_price = float(text)
        if sell_price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a valid price (e.g. 182.00):")
        return SELL_PRICE

    chat_id = str(update.message.chat_id)
    sym = context.user_data["sell_ticker"]
    qty = context.user_data["sell_qty"]
    trade_id = context.user_data["sell_trade_id"]
    buy_price = context.user_data["sell_trade_buy_price"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        trade = db.query(Trade).filter(
            Trade.id == trade_id,
            Trade.user_id == user.id,
            Trade.status == "active",
        ).first()
        if not trade:
            await update.message.reply_text("❌ Position not found — it may have already been closed.")
            return ConversationHandler.END

        from api.trade_service import close_trade_full, reduce_trade_shares

        if qty == "all":
            realized = close_trade_full(db, trade, sell_price)
            shares_sold = context.user_data["sell_trade_shares"]
            pnl_arrow = "📈" if (realized or 0) >= 0 else "📉"
            msg = (
                f"✅ *{sym} position closed*\n\n"
                f"Sold {shares_sold} shares @ ${sell_price:.2f}\n"
                f"Avg cost: ${buy_price:.2f}\n"
            )
            if realized is not None:
                sign = "+" if realized >= 0 else ""
                msg += f"Realized P&L: {pnl_arrow} *{sign}${realized:,.2f}*"
        else:
            realized = reduce_trade_shares(db, trade, qty, sell_price)
            pnl_arrow = "📈" if realized >= 0 else "📉"
            sign = "+" if realized >= 0 else ""
            msg = (
                f"✅ *{sym} partial sell recorded*\n\n"
                f"Sold {qty} shares @ ${sell_price:.2f}\n"
                f"Avg cost: ${buy_price:.2f}\n"
                f"Realized P&L: {pnl_arrow} *{sign}${realized:,.2f}*\n"
                f"Remaining: {trade.shares} shares"
            )

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as exc:
        log.exception("sell_got_price error: %s", exc)
        db.rollback()
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END


# ── /portfolio command ─────────────────────────────────────────────────────────

async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_linked_account(update):
        return

    chat_id = str(update.message.chat_id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        active = db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.status == "active",
        ).all()

        symbols = list({t.symbol for t in active})
        if symbols:
            loop = asyncio.get_running_loop()
            prices = await loop.run_in_executor(None, fetch_latest_prices, symbols)
        else:
            prices = {}

        from api.trade_service import get_portfolio_summary
        summary = get_portfolio_summary(db, user.id, prices)
    finally:
        db.close()

    pos = summary["positions_count"]
    if pos == 0:
        await update.message.reply_text("📭 You have no active positions.")
        return

    unreal = summary["unrealized_pnl"]
    real = summary["realized_pnl"]
    unreal_pct = summary["unrealized_pnl_pct"] * 100
    unreal_arrow = "📈" if unreal >= 0 else "📉"
    real_arrow = "📈" if real >= 0 else "📉"

    lines = [
        f"📊 *Portfolio — {pos} position{'s' if pos != 1 else ''}*\n",
        f"💰 Value:        ${summary['total_value']:,.2f}",
        f"💼 Invested:     ${summary['total_invested']:,.2f}",
        f"{unreal_arrow} Unrealized P&L: {'+'if unreal>=0 else ''}${unreal:,.2f} ({unreal_pct:+.2f}%)",
        f"{real_arrow} Realized P&L:   {'+'if real>=0 else ''}${real:,.2f}",
        "",
        "*Positions:*",
    ]

    for t in active:
        current = prices.get(t.symbol)
        if current is not None:
            pnl = (current - t.buy_price) * t.shares
            pnl_str = f"{'+'if pnl>=0 else ''}${pnl:,.2f}"
            pct_str = f"{(current - t.buy_price) / t.buy_price * 100:+.2f}%"
            arrow = "📈" if pnl >= 0 else "📉"
            lines.append(
                f"{arrow} {t.symbol}: {t.shares} @ ${t.buy_price:.2f} → ${current:.2f} ({pct_str}, {pnl_str})"
            )
        else:
            lines.append(f"• {t.symbol}: {t.shares} shares @ ${t.buy_price:.2f} avg")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Alert loop ────────────────────────────────────────────────────────────────

async def check_alerts_loop():
    """Background check for trades that need selling (managed by APScheduler)."""
    if not BOT_TOKEN:
        return

    bot = Bot(token=BOT_TOKEN)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        active_trades = db.query(Trade).filter(Trade.status == "active").all()

        from api.hold_health import evaluate_hold_health

        horizon_days: dict[str, int] = {}
        symbols: list[str] = []
        for trade in active_trades:
            symbols.append(trade.symbol)
            if trade.hold_unit and trade.hold_value:
                horizon_days[trade.symbol] = hold_days_from_unit(trade.hold_value, trade.hold_unit)
            else:
                horizon_days[trade.symbol] = trade.hold_days

        # Both calls below make blocking network requests; run them off the event
        # loop so bot polling stays responsive while the 3-hourly check runs.
        loop = asyncio.get_running_loop()
        health_results = await loop.run_in_executor(
            None, lambda: evaluate_hold_health(symbols, horizon_days, now=now)
        )
        unique_symbols = list({s.upper() for s in symbols})
        prices = await loop.run_in_executor(None, fetch_latest_prices, unique_symbols)

        for trade in active_trades:
            user = db.query(User).filter(User.id == trade.user_id).first()
            if not user or not user.telegram_chat_id:
                continue

            dirty = False

            sell_utc = trade.sell_date if trade.sell_date.tzinfo else trade.sell_date.replace(tzinfo=timezone.utc)
            if now >= sell_utc and trade.alerted_at is None:
                msg = f"🚨 ALERT: Your holding duration for {trade.shares} shares of {trade.symbol} has ended!\n\nIt is time to SELL and secure your position."
                log.info(f"Sending alert to chat {user.telegram_chat_id}: {msg}")
                try:
                    await bot.send_message(chat_id=user.telegram_chat_id, text=msg)
                    trade.alerted_at = now
                    db.commit()
                    log.info(f"Alert recorded for trade {trade.id} at {now}")
                except Exception as e:
                    log.error(f"Failed to send to {user.telegram_chat_id}: {e}")
                continue

            dip_threshold = trade.dip_threshold_pct
            if dip_threshold is not None and dip_threshold > 0:
                current_price = prices.get(trade.symbol)
                if current_price is not None and trade.buy_price:
                    drawdown = (current_price - trade.buy_price) / trade.buy_price
                    if drawdown <= -dip_threshold and trade.last_dip_alert_at is None:
                        msg = (
                            f"🚨 PRICE ALERT: {trade.symbol}\n"
                            f"Price drop exceeded {dip_threshold * 100:.1f}% from entry.\n"
                            f"Entry: ${trade.buy_price:.2f} | Last: ${current_price:.2f}\n"
                            f"Current move: {drawdown * 100:.2f}%"
                        )
                        log.info(f"Sending dip alert to chat {user.telegram_chat_id}: {msg}")
                        try:
                            await bot.send_message(chat_id=user.telegram_chat_id, text=msg)
                            trade.last_dip_alert_at = now
                            dirty = True
                        except Exception as e:
                            log.error(f"Failed to send dip alert to {user.telegram_chat_id}: {e}")

            health = health_results.get(trade.symbol)
            if health:
                prev_strength = trade.last_health_strength
                trade.last_health_check_at = now
                trade.last_health_strength = health.strength
                trade.last_health_reason = health.reason_text

                if health.strength < 0 and (prev_strength is None or prev_strength >= 0):
                    msg = (
                        f"🚨 SELL ALERT: {trade.symbol}\n"
                        f"Reason: {health.reason_text}\n"
                        f"Health score: {health.strength:+.2f} (horizon {health.horizon_days}d)"
                    )
                    log.info(f"Sending alert to chat {user.telegram_chat_id}: {msg}")
                    try:
                        await bot.send_message(chat_id=user.telegram_chat_id, text=msg)
                        trade.last_health_alert_at = now
                        dirty = True
                    except Exception as e:
                        log.error(f"Failed to send to {user.telegram_chat_id}: {e}")
                dirty = True

            if dirty:
                db.commit()

    except Exception as e:
        db.rollback()
        log.exception("Error checking alerts: %s", e)
    finally:
        db.close()


# ── Outbound alert utility ────────────────────────────────────────────────────

def send_telegram_alert(username: str, message: str):
    """Instantly send a Telegram alert to a user using their saved chat_id."""
    if not BOT_TOKEN or not username:
        log.warning(f"Cannot send alert to @{username}: BOT_TOKEN not set or username missing")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            (User.telegram_username == username) |
            (User.telegram_username == f"@{username}")
        ).first()

        if not user or not user.telegram_chat_id:
            log.warning(f"User @{username} not found or no chat_id")
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send_message_async(user.telegram_chat_id, message))
        except RuntimeError:
            asyncio.run(_send_message_async(user.telegram_chat_id, message))

        log.info(f"✅ Telegram alert scheduled for @{username} (chat_id: {user.telegram_chat_id})")
    except Exception as e:
        log.error(f"❌ Failed to send Telegram alert to @{username}: {e}")
    finally:
        db.close()


async def _send_message_async(chat_id: str, message: str):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=message)


# ── Bot lifecycle ─────────────────────────────────────────────────────────────

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
    telegram_app.add_handler(CommandHandler("portfolio", portfolio_cmd))

    buy_conv = ConversationHandler(
        entry_points=[CommandHandler("buy", buy_start)],
        states={
            BUY_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_got_ticker)],
            BUY_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_got_shares)],
            BUY_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_got_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        conversation_timeout=300,
    )

    sell_conv = ConversationHandler(
        entry_points=[CommandHandler("sell", sell_start)],
        states={
            SELL_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_got_ticker)],
            SELL_QTY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_got_qty)],
            SELL_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_got_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        conversation_timeout=300,
    )

    telegram_app.add_handler(buy_conv)
    telegram_app.add_handler(sell_conv)
    telegram_app.add_handler(CommandHandler("cancel", cancel_cmd))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram Bot is polling for commands.")


async def stop_telegram_bot():
    """Stop the telegram bot polling."""
    global telegram_app
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
