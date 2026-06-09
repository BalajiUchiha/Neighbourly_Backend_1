import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# DATABASE_URL is loaded from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Set up engine and sessionmaker safely in case DATABASE_URL is not configured yet
if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,    # re-validates connections before use (handles Supabase/PgBouncer drops)
        pool_recycle=300,      # recycle connections every 5 min
        connect_args={"connect_timeout": 10},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    engine = None
    SessionLocal = None

Base = declarative_base()

def get_db():
    """Dependency helper to get a database session."""
    if SessionLocal is None:
        raise ValueError("DATABASE_URL is not configured in backend/.env")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
