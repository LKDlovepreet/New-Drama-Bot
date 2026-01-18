from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class FileRecord(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_token = Column(String, unique=True, index=True)
    file_id = Column(String)
    file_name = Column(String)
    file_type = Column(String)
    uploader_id = Column(BigInteger)

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, unique=True)
    channel_name = Column(String)
    added_by = Column(BigInteger)
    broadcast_enabled = Column(Boolean, default=False) 

class BotUser(Base):
    __tablename__ = "bot_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, index=True)
    joined_date = Column(DateTime, default=datetime.utcnow)
    is_premium = Column(Boolean, default=False)
    verification_expiry = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    # 👇 YE LINE MISSING THI, ISLIYE ERROR AA RAHA THA
    active_topic_id = Column(Integer, default=0)

class GroupSettings(Base):
    __tablename__ = "group_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, unique=True)
    welcome_enabled = Column(Boolean, default=True)
    auto_search = Column(Boolean, default=True)

# 👇 NEW TABLE: Purane topics yaad rakhne ke liye
class StorageTopic(Base):
    __tablename__ = "storage_topics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String) # Jaise: "Movies", "Notes"
    topic_id = Column(BigInteger) # Telegram ka Topic ID
