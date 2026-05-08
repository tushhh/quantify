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
    sell_date = created_at + timedelta(days=req.hold_days)
    
    db_trade = DBTrade(
        user_id=current_user.id,
        symbol=req.symbol.upper(),
        shares=req.shares,
        buy_price=req.buy_price,
        hold_days=req.hold_days,
        created_at=created_at,
        sell_date=sell_date,
        status="active"
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    
    if current_user.telegram_username:
        from api.telegram_bot import send_telegram_alert
        msg = f"✅ TRADE LOGGED: {req.shares} shares of {req.symbol.upper()} at ${req.buy_price}.\n\nQuantify will monitor this position and alert you when to sell on {sell_date.strftime('%Y-%m-%d')}."
        background_tasks.add_task(send_telegram_alert, current_user.telegram_username, msg)
    
    return TrackedTrade(
        id=str(db_trade.id),
        symbol=db_trade.symbol,
        shares=db_trade.shares,
        buy_price=db_trade.buy_price,
        hold_days=db_trade.hold_days,
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
            elif now >= (t.sell_date.replace(tzinfo=timezone.utc) - timedelta(days=1)):
                alert = "Sell date approaching (within 24h)"
                
        res.append(TrackedTrade(
            id=str(t.id),
            symbol=t.symbol,
            shares=t.shares,
            buy_price=t.buy_price,
            hold_days=t.hold_days,
            created_at=t.created_at.isoformat(),
            sell_date=t.sell_date.isoformat(),
            status=t.status,
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
