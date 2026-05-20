from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from api.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    telegram_username = Column(String, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String)
    shares = Column(Float)
    buy_price = Column(Float)
    dip_threshold_pct = Column(Float, nullable=True, default=None)
    hold_days = Column(Integer)
    hold_unit = Column(String, default="days")
    hold_value = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sell_date = Column(DateTime)
    status = Column(String, default="active")
    alerted_at = Column(DateTime, nullable=True, default=None)  # Timestamp when alert was sent
    last_health_check_at = Column(DateTime, nullable=True, default=None)
    last_health_strength = Column(Float, nullable=True, default=None)
    last_health_reason = Column(String, nullable=True, default=None)
    last_health_alert_at = Column(DateTime, nullable=True, default=None)
    last_dip_alert_at = Column(DateTime, nullable=True, default=None)
