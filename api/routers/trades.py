import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from api.schemas import TrackedTrade, TradeCreate
from api.database import get_db
from api.models import Trade as DBTrade, User as DBUser
from api.routers.auth import get_current_user
from api.routers import utils as utils_router
from api.hold_health import hold_days_from_unit

router = APIRouter(prefix="/trades", tags=["trades"])
log = logging.getLogger("quantify.api.trades")

@router.post("", response_model=TrackedTrade)
async def create_trade(
    req: TradeCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: DBUser = Depends(get_current_user)
):
    """Log a new trade to track for the current user."""
    created_at = datetime.now(timezone.utc)
    hold_unit = (req.hold_unit or "").strip().lower()
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
    # Validate symbol exists and is a US-listed equity
    sym = req.symbol.strip().upper()
    try:
        valid, meta = utils_router._is_us_equity(sym)
    except Exception:
        raise HTTPException(status_code=500, detail="Symbol validation failed")
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid symbol or not US-listed: {sym} ({meta})")
    
    db_trade = DBTrade(
        user_id=current_user.id,
        symbol=req.symbol.upper(),
        shares=req.shares,
        buy_price=req.buy_price,
        hold_days=hold_days,
        hold_unit=hold_unit,
        hold_value=hold_value,
        created_at=created_at,
        sell_date=sell_date,
        status="active"
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    
    if current_user.telegram_username:
        from api.telegram_bot import send_telegram_alert
        msg = (
            f"✅ TRADE LOGGED: {req.shares} shares of {req.symbol.upper()} at ${req.buy_price}.\n\n"
            f"Hold duration: {hold_value} {hold_unit}.\n"
            f"Quantify will monitor this position and alert you when to sell on {sell_date.strftime('%Y-%m-%d')}."
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
        created_at=db_trade.created_at.isoformat(),
        sell_date=db_trade.sell_date.isoformat(),
        status=db_trade.status
    )

@router.get("", response_model=List[TrackedTrade])
async def list_trades(
    db: Session = Depends(get_db), 
    current_user: DBUser = Depends(get_current_user)
):
    """List all tracked trades for the current user."""
    trades = db.query(DBTrade).filter(DBTrade.user_id == current_user.id).all()
    now = datetime.now(timezone.utc)
    
    res = []
    for t in trades:
        alert = None
        if t.status == "active":
            if now >= t.sell_date.replace(tzinfo=timezone.utc):
                alert = "HOLDING PERIOD EXPIRED - SELL NOW"
            elif t.last_health_strength is not None and t.last_health_strength < 0:
                alert = f"SELL: {t.last_health_reason or 'Negative outlook detected'}"
            elif now >= (t.sell_date.replace(tzinfo=timezone.utc) - timedelta(days=1)):
                alert = "Sell date approaching (within 24h)"
                
        res.append(TrackedTrade(
            id=t.id,
            symbol=t.symbol,
            shares=t.shares,
            buy_price=t.buy_price,
            hold_days=t.hold_days,
            hold_unit=t.hold_unit,
            hold_value=t.hold_value,
            created_at=t.created_at.isoformat(),
            sell_date=t.sell_date.isoformat(),
            status=t.status,
            current_strength=t.last_health_strength,
            last_health_reason=t.last_health_reason,
            alert=alert
        ))
    return res

@router.delete("/{trade_id}")
async def close_trade(
    trade_id: int, 
    db: Session = Depends(get_db), 
    current_user: DBUser = Depends(get_current_user)
):
    """Mark a trade as closed."""
    trade = db.query(DBTrade).filter(DBTrade.id == trade_id, DBTrade.user_id == current_user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    trade.status = "closed"
    db.commit()
    return {"status": "ok"}
