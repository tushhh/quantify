from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
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

class PredictionCache(Base):
    __tablename__ = "prediction_cache"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    result_json = Column(String)  # Full PredictionResponse JSON string

class PredictionSubscription(Base):
    __tablename__ = "prediction_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String(64), unique=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AdhocPredictionCache(Base):
    __tablename__ = "adhoc_prediction_cache"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(16), unique=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    result_json = Column(String)  # Serialized PredictionItem JSON string

class AsyncPredictionJob(Base):
    __tablename__ = "async_prediction_jobs"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String(64), index=True)
    status = Column(String(16), default="pending")  # pending | complete | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    result_json = Column(String, nullable=True)


class BacktestJob(Base):
    """Persists offloaded (cloud) backtest jobs so a dyno restart between dispatch
    and the GitHub Actions callback doesn't drop the job from memory."""
    __tablename__ = "backtest_jobs"
    id = Column(String(64), primary_key=True)           # job_id chosen by the web process
    status = Column(String(16), default="running")      # running | complete | failed
    request_json = Column(String, nullable=True)
    result_json = Column(String, nullable=True)
    error = Column(String, nullable=True)
    is_cloud_run = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
