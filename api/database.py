import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger("quantify.api.database")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/quantify.db")

# If using SQLite locally, create the directory
if DATABASE_URL.startswith("sqlite"):
    os.makedirs("./data", exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Cloud PostgreSQL (Render/Supabase)
    # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_trade_columns() -> None:
    """Ensure optional trade columns exist for hold health tracking."""
    ddl = [
        ("alerted_at", "ALTER TABLE trades ADD COLUMN alerted_at TIMESTAMP"),
        ("dip_threshold_pct", "ALTER TABLE trades ADD COLUMN dip_threshold_pct FLOAT"),
        ("hold_unit", "ALTER TABLE trades ADD COLUMN hold_unit VARCHAR(16) DEFAULT 'days'"),
        ("hold_value", "ALTER TABLE trades ADD COLUMN hold_value INTEGER DEFAULT 0"),
        ("last_health_check_at", "ALTER TABLE trades ADD COLUMN last_health_check_at TIMESTAMP"),
        ("last_health_strength", "ALTER TABLE trades ADD COLUMN last_health_strength FLOAT"),
        ("last_health_reason", "ALTER TABLE trades ADD COLUMN last_health_reason VARCHAR(512)"),
        ("last_health_alert_at", "ALTER TABLE trades ADD COLUMN last_health_alert_at TIMESTAMP"),
        ("last_dip_alert_at", "ALTER TABLE trades ADD COLUMN last_dip_alert_at TIMESTAMP"),
        ("sell_price", "ALTER TABLE trades ADD COLUMN sell_price FLOAT"),
        ("realized_pnl", "ALTER TABLE trades ADD COLUMN realized_pnl FLOAT"),
        ("closed_at", "ALTER TABLE trades ADD COLUMN closed_at TIMESTAMP"),
    ]
    try:
        inspector = inspect(engine)
        existing_cols = {col["name"] for col in inspector.get_columns("trades")}
        with engine.begin() as conn:
            for column, stmt in ddl:
                if column in existing_cols:
                    continue
                try:
                    conn.execute(text(stmt))
                    log.info("✅ Migration executed: %s", stmt)
                except Exception as e:
                    log.warning("Migration statement failed for %s: %s", column, e)
        log.info("✅ All trade columns verified/created successfully")
    except Exception as e:
        log.error(f"❌ Failed to run trade migrations: {e}")


def ensure_user_columns() -> None:
    """Ensure optional user columns exist for Telegram integration."""
    ddl = [
        ("telegram_chat_id", "ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR(64)"),
    ]
    try:
        inspector = inspect(engine)
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        with engine.begin() as conn:
            for column, stmt in ddl:
                if column in existing_cols:
                    continue
                try:
                    conn.execute(text(stmt))
                    log.info("✅ Migration executed: %s", stmt)
                except Exception as e:
                    log.warning("Migration statement failed for %s: %s", column, e)
        log.info("✅ All user columns verified/created successfully")
    except Exception as e:
        log.error(f"❌ Failed to run user migrations: {e}")

def ensure_gain_alert_columns() -> None:
    """Add columns introduced after initial deploy of the gain alert tables."""
    migrations = {
        "gain_alert_subscriptions": [
            ("threshold_pct", "ALTER TABLE gain_alert_subscriptions ADD COLUMN threshold_pct FLOAT DEFAULT 4.0"),
        ],
        "gain_alert_state": [
            ("chat_id", "ALTER TABLE gain_alert_state ADD COLUMN chat_id VARCHAR(64)"),
            ("last_alerted_pct", "ALTER TABLE gain_alert_state ADD COLUMN last_alerted_pct FLOAT"),
        ],
    }
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        with engine.begin() as conn:
            for table, cols in migrations.items():
                if table not in existing_tables:
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(table)}
                for col, stmt in cols:
                    if col not in existing_cols:
                        try:
                            conn.execute(text(stmt))
                            log.info("✅ Migration executed: %s", stmt)
                        except Exception as e:
                            log.warning("Migration failed for %s.%s: %s", table, col, e)
        log.info("✅ Gain alert columns verified/created successfully")
    except Exception as e:
        log.error("❌ Failed to run gain alert migrations: %s", e)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
