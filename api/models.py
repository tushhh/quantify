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
    hold_days = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sell_date = Column(DateTime)
    status = Column(String, default="active")
