import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Check if we should use SQLite (Standalone) or Postgres (Production)
IS_STANDALONE = os.getenv("POSTGRES_HOST") is None or os.getenv("POSTGRES_HOST") == ""

if IS_STANDALONE:
    print("🚀 SRME: Standalone Mode (SQLite/Threading) Active")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DB_PATH = os.path.join(BASE_DIR, "data", "srme.db")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    
    # Enable WAL mode for better concurrency
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "srme_user")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "srme_password")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "srme_db")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=20,
        max_overflow=10
    )
import threading

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_lock = threading.Lock() # Global lock for SQLite standalone mode

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
