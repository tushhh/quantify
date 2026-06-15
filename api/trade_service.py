"""
Shared trade business logic used by both the API router and Telegram bot.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from api.models import Trade as DBTrade

log = logging.getLogger("quantify.trade_service")


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_or_aggregate_trade(
    db: Session,
    user_id: int,
    symbol: str,
    shares: float,
    buy_price: float,
    hold_days: int = 30,
    hold_unit: str = "days",
    hold_value: int = 30,
    dip_threshold_pct: Optional[float] = None,
) -> Tuple[DBTrade, bool, Optional[float], Optional[float]]:
    """
    Create a new trade or aggregate into an existing active position.
    Returns (trade, was_aggregated, prev_shares, prev_buy_price).
    """
    now = datetime.now(timezone.utc)

    existing = db.query(DBTrade).filter(
        DBTrade.user_id == user_id,
        DBTrade.symbol == symbol,
        DBTrade.status == "active",
    ).first()

    if existing:
        prev_shares = existing.shares
        prev_buy_price = existing.buy_price
        new_total = existing.shares + shares
        new_avg = (existing.shares * existing.buy_price + shares * buy_price) / new_total
        existing.shares = new_total
        existing.buy_price = round(new_avg, 6)
        existing.hold_days = hold_days
        existing.hold_unit = hold_unit
        existing.hold_value = hold_value
        existing.sell_date = _ensure_utc(existing.created_at) + timedelta(days=hold_days)
        if dip_threshold_pct is not None:
            existing.dip_threshold_pct = dip_threshold_pct
        db.commit()
        db.refresh(existing)
        return existing, True, prev_shares, prev_buy_price

    sell_date = now + timedelta(days=hold_days)
    trade = DBTrade(
        user_id=user_id,
        symbol=symbol,
        shares=shares,
        buy_price=buy_price,
        dip_threshold_pct=dip_threshold_pct,
        hold_days=hold_days,
        hold_unit=hold_unit,
        hold_value=hold_value,
        created_at=now,
        sell_date=sell_date,
        status="active",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade, False, None, None


def close_trade_full(
    db: Session,
    trade: DBTrade,
    sell_price: Optional[float],
) -> Optional[float]:
    """Mark a trade as fully closed, computing realized P&L if sell_price given."""
    realized = None
    if sell_price is not None and trade.buy_price:
        realized = round((sell_price - trade.buy_price) * trade.shares, 2)

    now = datetime.now(timezone.utc)
    trade.status = "closed"
    trade.sell_price = sell_price
    trade.closed_at = now
    if realized is not None:
        trade.realized_pnl = round((trade.realized_pnl or 0.0) + realized, 2)
    db.commit()
    return realized


def reduce_trade_shares(
    db: Session,
    trade: DBTrade,
    shares_to_sell: float,
    sell_price: float,
) -> float:
    """Partially close a position. Returns realized P&L for this sell."""
    realized = round((sell_price - trade.buy_price) * shares_to_sell, 2)
    trade.realized_pnl = round((trade.realized_pnl or 0.0) + realized, 2)
    trade.shares = round(trade.shares - shares_to_sell, 6)
    db.commit()
    return realized


def get_portfolio_summary(
    db: Session,
    user_id: int,
    prices: dict,
) -> dict:
    """Return portfolio stats for a user given a symbol→price mapping."""
    active = db.query(DBTrade).filter(
        DBTrade.user_id == user_id,
        DBTrade.status == "active",
    ).all()

    realized_pnl = sum(
        (t.realized_pnl or 0.0)
        for t in db.query(DBTrade).filter(DBTrade.user_id == user_id).all()
    )

    total_invested = 0.0
    total_value = 0.0
    for t in active:
        cost = t.buy_price * t.shares
        total_invested += cost
        current = prices.get(t.symbol)
        total_value += (current * t.shares) if current is not None else cost

    unrealized_pnl = total_value - total_invested
    unrealized_pnl_pct = (unrealized_pnl / total_invested) if total_invested > 0 else 0.0

    return {
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 4),
        "realized_pnl": round(realized_pnl, 2),
        "positions_count": len(active),
    }
