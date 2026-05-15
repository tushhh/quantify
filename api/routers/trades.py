import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
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


def _ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime regardless of input awareness."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fetch_prices_sync(symbols: List[str]) -> Dict[str, Optional[float]]:
    """Fetch latest close prices for a list of symbols via yfinance (synchronous)."""
    result: Dict[str, Optional[float]] = {s: None for s in symbols}
    if not symbols:
        return result
    try:
        import yfinance as yf
        import pandas as pd

        tickers = " ".join(symbols)
        raw = yf.download(
            tickers,
            period="5d",
            auto_adjust=True,
            progress=False,
            group_by="ticker" if len(symbols) > 1 else "column",
            threads=True,
        )
        if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
            return result

        def _get_close(df: pd.DataFrame) -> Optional[float]:
            """Extract the latest close price from a DataFrame, case-insensitively."""
            col_map = {c.lower(): c for c in df.columns}
            col = col_map.get("close")
            if col is None:
                return None
            series = df[col].dropna()
            return round(float(series.iloc[-1]), 4) if not series.empty else None

        if len(symbols) == 1:
            result[symbols[0]] = _get_close(raw)
        else:
            for sym in symbols:
                try:
                    result[sym] = _get_close(raw[sym])
                except Exception:
                    pass
    except Exception as exc:
        log.warning("Price fetch failed: %s", exc)
    return result


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

    db_trade = DBTrade(
        user_id=current_user.id,
        symbol=sym,
        shares=req.shares,
        buy_price=req.buy_price,
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
        created_at=db_trade.created_at.isoformat(),
        sell_date=db_trade.sell_date.isoformat(),
        status=db_trade.status,
    )


@router.get("", response_model=List[TrackedTrade])
async def list_trades(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """List all tracked trades for the current user."""
    trades = db.query(DBTrade).filter(DBTrade.user_id == current_user.id).all()
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
            created_at=t.created_at.isoformat(),
            sell_date=sell_utc.isoformat(),
            status=t.status,
            current_strength=t.last_health_strength,
            last_health_reason=t.last_health_reason,
            alert=alert,
        ))
    return res


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
    prices = await loop.run_in_executor(None, _fetch_prices_sync, symbols)
    return prices


@router.delete("/{trade_id}")
async def close_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """Mark a trade as closed."""
    trade = db.query(DBTrade).filter(
        DBTrade.id == trade_id,
        DBTrade.user_id == current_user.id,
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    trade.status = "closed"
    db.commit()
    return {"status": "ok"}
