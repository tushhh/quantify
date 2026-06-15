import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from api.schemas import (
    TrackedTrade, TradeCreate, TradeDipUpdate, TradeUpdate,
    TradeCloseRequest, TradePartialSellRequest, PortfolioSummary,
)
from api.database import get_db
from api.models import Trade as DBTrade, User as DBUser
from api.routers.auth import get_current_user
from api.routers import utils as utils_router
from api.hold_utils import hold_days_from_unit
from api.market_data import fetch_latest_prices
from api.trade_service import close_trade_full, reduce_trade_shares, get_portfolio_summary

router = APIRouter(prefix="/trades", tags=["trades"])
log = logging.getLogger("quantify.api.trades")


def _ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime regardless of input awareness."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validate_dip_threshold(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value < 0 or value > 0.9:
        raise HTTPException(status_code=400, detail="dip_threshold_pct must be between 0 and 0.9")
    return float(value)


@router.post("", response_model=TrackedTrade)
async def create_trade(
    req: TradeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Log a new trade to track for the current user."""
    created_at = datetime.now(timezone.utc)
    hold_unit = (req.hold_unit or "").strip().lower()
    dip_threshold_pct = _validate_dip_threshold(req.dip_threshold_pct)
    if req.hold_value is not None:
        if hold_unit not in {"days", "months", "years"}:
            raise HTTPException(status_code=400, detail="hold_unit must be days, months, or years")
        if req.hold_value <= 0:
            raise HTTPException(status_code=400, detail="hold_value must be > 0")
        hold_days = hold_days_from_unit(req.hold_value, hold_unit)
        hold_value = req.hold_value
    elif req.hold_days is not None:
        if req.hold_days <= 0:
            raise HTTPException(status_code=400, detail="hold_days must be > 0")
        hold_days = req.hold_days
        hold_unit = "days"
        hold_value = req.hold_days
    else:
        raise HTTPException(status_code=400, detail="Provide hold_value + hold_unit or hold_days")

    sell_date = created_at + timedelta(days=hold_days)
    sym = req.symbol.strip().upper()

    loop = asyncio.get_running_loop()
    try:
        valid, meta = await loop.run_in_executor(None, utils_router._is_us_equity, sym)
    except Exception:
        raise HTTPException(status_code=500, detail="Symbol validation failed")
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid symbol or not US-listed: {sym} ({meta})")

    # Aggregate into existing active position for the same symbol
    existing = db.query(DBTrade).filter(
        DBTrade.user_id == current_user.id,
        DBTrade.symbol == sym,
        DBTrade.status == "active",
    ).first()

    if existing:
        prev_shares = existing.shares
        prev_buy_price = existing.buy_price
        new_total_shares = existing.shares + req.shares
        new_avg_price = (existing.shares * existing.buy_price + req.shares * req.buy_price) / new_total_shares
        existing.shares = new_total_shares
        existing.buy_price = round(new_avg_price, 6)
        existing.hold_days = hold_days
        existing.hold_unit = hold_unit
        existing.hold_value = hold_value
        existing.sell_date = _ensure_utc(existing.created_at) + timedelta(days=hold_days)
        if dip_threshold_pct is not None:
            existing.dip_threshold_pct = dip_threshold_pct
        db.commit()
        db.refresh(existing)

        if current_user.telegram_username:
            from api.telegram_bot import send_telegram_alert
            msg = (
                f"✅ POSITION UPDATED: Added {req.shares} shares of {sym} at ${req.buy_price:.2f}.\n\n"
                f"New position: {existing.shares} shares @ ${existing.buy_price:.2f} avg.\n"
                f"New hold target: {hold_value} {hold_unit}.\n"
                f"Sell target: {existing.sell_date.strftime('%Y-%m-%d')}."
            )
            background_tasks.add_task(send_telegram_alert, current_user.telegram_username, msg)

        sell_utc = _ensure_utc(existing.sell_date)
        return TrackedTrade(
            id=existing.id,
            symbol=existing.symbol,
            shares=existing.shares,
            buy_price=existing.buy_price,
            hold_days=existing.hold_days,
            hold_unit=existing.hold_unit,
            hold_value=existing.hold_value,
            dip_threshold_pct=existing.dip_threshold_pct,
            created_at=existing.created_at.isoformat(),
            sell_date=sell_utc.isoformat(),
            status=existing.status,
            aggregated=True,
            prev_shares=prev_shares,
            prev_buy_price=round(prev_buy_price, 6),
        )

    db_trade = DBTrade(
        user_id=current_user.id,
        symbol=sym,
        shares=req.shares,
        buy_price=req.buy_price,
        dip_threshold_pct=dip_threshold_pct,
        hold_days=hold_days,
        hold_unit=hold_unit,
        hold_value=hold_value,
        created_at=created_at,
        sell_date=sell_date,
        status="active",
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)

    if current_user.telegram_username:
        from api.telegram_bot import send_telegram_alert
        msg = (
            f"✅ TRADE LOGGED: {req.shares} shares of {sym} at ${req.buy_price}.\n\n"
            f"Hold duration: {hold_value} {hold_unit}.\n"
            f"Quantify will monitor this position and alert you to sell on "
            f"{sell_date.strftime('%Y-%m-%d')}."
        )
        background_tasks.add_task(send_telegram_alert, current_user.telegram_username, msg)

    return TrackedTrade(
        id=db_trade.id,
        symbol=db_trade.symbol,
        shares=db_trade.shares,
        buy_price=db_trade.buy_price,
        hold_days=db_trade.hold_days,
        hold_unit=db_trade.hold_unit,
        hold_value=db_trade.hold_value,
        dip_threshold_pct=db_trade.dip_threshold_pct,
        created_at=db_trade.created_at.isoformat(),
        sell_date=db_trade.sell_date.isoformat(),
        status=db_trade.status,
    )


@router.get("", response_model=List[TrackedTrade])
async def list_trades(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """List all active tracked trades for the current user."""
    trades = db.query(DBTrade).filter(
        DBTrade.user_id == current_user.id,
        DBTrade.status == "active",
    ).all()
    now = datetime.now(timezone.utc)

    res = []
    for t in trades:
        sell_utc = _ensure_utc(t.sell_date)
        alert = None
        if t.status == "active":
            if now >= sell_utc:
                alert = "HOLDING PERIOD EXPIRED — SELL NOW"
            elif t.last_health_strength is not None and t.last_health_strength < 0:
                alert = f"SELL: {t.last_health_reason or 'Negative outlook detected'}"
            elif now >= sell_utc - timedelta(days=1):
                alert = "Sell date approaching (within 24h)"

        res.append(TrackedTrade(
            id=t.id,
            symbol=t.symbol,
            shares=t.shares,
            buy_price=t.buy_price,
            hold_days=t.hold_days,
            hold_unit=t.hold_unit,
            hold_value=t.hold_value,
            dip_threshold_pct=t.dip_threshold_pct,
            created_at=t.created_at.isoformat(),
            sell_date=sell_utc.isoformat(),
            status=t.status,
            current_strength=t.last_health_strength,
            last_health_reason=t.last_health_reason,
            alert=alert,
        ))
    return res


@router.patch("/{trade_id}/dip-threshold", response_model=TrackedTrade)
async def update_dip_threshold(
    trade_id: int,
    req: TradeDipUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Update the dip alert threshold for a trade (0 disables alerts)."""
    trade = db.query(DBTrade).filter(
        DBTrade.id == trade_id,
        DBTrade.user_id == current_user.id,
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    dip_threshold_pct = _validate_dip_threshold(req.dip_threshold_pct)
    if dip_threshold_pct is not None and dip_threshold_pct <= 0:
        dip_threshold_pct = None

    previous = trade.dip_threshold_pct
    trade.dip_threshold_pct = dip_threshold_pct
    if previous != trade.dip_threshold_pct:
        trade.last_dip_alert_at = None

    db.commit()
    db.refresh(trade)

    sell_utc = _ensure_utc(trade.sell_date)
    return TrackedTrade(
        id=trade.id,
        symbol=trade.symbol,
        shares=trade.shares,
        buy_price=trade.buy_price,
        hold_days=trade.hold_days,
        hold_unit=trade.hold_unit,
        hold_value=trade.hold_value,
        dip_threshold_pct=trade.dip_threshold_pct,
        created_at=trade.created_at.isoformat(),
        sell_date=sell_utc.isoformat(),
        status=trade.status,
        current_strength=trade.last_health_strength,
        last_health_reason=trade.last_health_reason,
        alert=None,
    )


@router.get("/prices")
async def get_trade_prices(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Return current market prices for all active trades of the current user."""
    trades = db.query(DBTrade).filter(
        DBTrade.user_id == current_user.id,
        DBTrade.status == "active",
    ).all()
    symbols = list({t.symbol for t in trades})
    if not symbols:
        return {}
    loop = asyncio.get_running_loop()
    prices = await loop.run_in_executor(None, fetch_latest_prices, symbols)
    return prices


@router.patch("/{trade_id}", response_model=TrackedTrade)
async def update_trade(
    trade_id: int,
    req: TradeUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Update shares, price, or hold duration for an existing trade."""
    trade = db.query(DBTrade).filter(
        DBTrade.id == trade_id,
        DBTrade.user_id == current_user.id,
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if req.shares is not None:
        if req.shares <= 0:
            raise HTTPException(status_code=400, detail="shares must be > 0")
        trade.shares = req.shares

    if req.buy_price is not None:
        if req.buy_price <= 0:
            raise HTTPException(status_code=400, detail="buy_price must be > 0")
        trade.buy_price = req.buy_price

    if req.hold_value is not None and req.hold_unit is not None:
        hu = req.hold_unit.strip().lower()
        if hu not in {"days", "months", "years"}:
            raise HTTPException(status_code=400, detail="hold_unit must be days, months, or years")
        if req.hold_value <= 0:
            raise HTTPException(status_code=400, detail="hold_value must be > 0")
        hd = hold_days_from_unit(req.hold_value, hu)
        trade.hold_days = hd
        trade.hold_unit = hu
        trade.hold_value = req.hold_value
        trade.sell_date = _ensure_utc(trade.created_at) + timedelta(days=hd)
    elif req.hold_days is not None:
        if req.hold_days <= 0:
            raise HTTPException(status_code=400, detail="hold_days must be > 0")
        trade.hold_days = req.hold_days
        trade.hold_unit = "days"
        trade.hold_value = req.hold_days
        trade.sell_date = _ensure_utc(trade.created_at) + timedelta(days=req.hold_days)

    if req.dip_threshold_pct is not None:
        dip = _validate_dip_threshold(req.dip_threshold_pct)
        if dip is not None and dip <= 0:
            dip = None
        if trade.dip_threshold_pct != dip:
            trade.last_dip_alert_at = None
        trade.dip_threshold_pct = dip

    db.commit()
    db.refresh(trade)

    sell_utc = _ensure_utc(trade.sell_date)
    return TrackedTrade(
        id=trade.id,
        symbol=trade.symbol,
        shares=trade.shares,
        buy_price=trade.buy_price,
        hold_days=trade.hold_days,
        hold_unit=trade.hold_unit,
        hold_value=trade.hold_value,
        dip_threshold_pct=trade.dip_threshold_pct,
        created_at=trade.created_at.isoformat(),
        sell_date=sell_utc.isoformat(),
        status=trade.status,
        current_strength=trade.last_health_strength,
        last_health_reason=trade.last_health_reason,
        alert=None,
    )


@router.post("/{trade_id}/close")
async def close_trade(
    trade_id: int,
    req: TradeCloseRequest = TradeCloseRequest(),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Close a trade and optionally record the sell price for P&L tracking."""
    trade = db.query(DBTrade).filter(
        DBTrade.id == trade_id,
        DBTrade.user_id == current_user.id,
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    close_trade_full(db, trade, req.sell_price)
    return {"status": "ok"}


@router.delete("/{trade_id}")
async def close_trade_legacy(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Legacy close endpoint — use POST /{id}/close for P&L tracking."""
    trade = db.query(DBTrade).filter(
        DBTrade.id == trade_id,
        DBTrade.user_id == current_user.id,
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    close_trade_full(db, trade, None)
    return {"status": "ok"}


@router.patch("/{trade_id}/partial-sell")
async def partial_sell_trade(
    trade_id: int,
    req: TradePartialSellRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Reduce shares on an active position and record realized P&L."""
    trade = db.query(DBTrade).filter(
        DBTrade.id == trade_id,
        DBTrade.user_id == current_user.id,
        DBTrade.status == "active",
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if req.shares_to_sell >= trade.shares:
        raise HTTPException(status_code=400, detail="Use close endpoint to sell all shares")
    realized = reduce_trade_shares(db, trade, req.shares_to_sell, req.sell_price)
    sell_utc = _ensure_utc(trade.sell_date)
    return {
        "status": "ok",
        "realized_pnl": realized,
        "remaining_shares": trade.shares,
    }


@router.get("/portfolio-summary", response_model=PortfolioSummary)
async def portfolio_summary(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Return portfolio-level P&L metrics for the current user."""
    active = db.query(DBTrade).filter(
        DBTrade.user_id == current_user.id,
        DBTrade.status == "active",
    ).all()
    symbols = list({t.symbol for t in active})
    prices = {}
    if symbols:
        loop = asyncio.get_running_loop()
        prices = await loop.run_in_executor(None, fetch_latest_prices, symbols)
    return get_portfolio_summary(db, current_user.id, prices)
