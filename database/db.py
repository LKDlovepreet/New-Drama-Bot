import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from dotenv import load_dotenv

load_dotenv()

# Database Switcher
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///storage.db")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Engine Create
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Session Factory
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

# 👇 FIX: Ab ye generator nahi, seedha function hai
def get_db():
    return SessionLocal()
