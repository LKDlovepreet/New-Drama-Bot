#database

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from dotenv import load_dotenv

load_dotenv()

# Database Switcher (Cloud vs Local)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///storage.db")

# Koyeb fix: Postgres URL 'postgresql://' hona chahiye
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
