import os
from sqlalchemy import create_engine
from api import models

# User's direct Supabase URL
url = "postgresql://postgres:2te%26q%3FJ9c.%2CEB5s@db.ugegcaslkcgftaqqobiz.supabase.co:5432/postgres"

try:
    print("Connecting to Supabase...")
    engine = create_engine(url)
    print("Creating tables...")
    models.Base.metadata.create_all(bind=engine)
    print("Successfully created tables on Supabase!")
except Exception as e:
    print("Error:", e)
