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
    active_topic_id = Column(Integer, default=0)
    
    # --- BOT 2 FEATURES (Warn, Global Ban, Temp Mute) ---
    warning_count = Column(Integer, default=0)
    is_global_banned = Column(Boolean, default=False)
    restricted_until = Column(DateTime, nullable=True)

class StorageTopic(Base):
    __tablename__ = "storage_topics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String)
    topic_id = Column(BigInteger)

# --- BOT 2 NEW TABLES ---

class GroupSettings(Base):
    __tablename__ = "group_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, unique=True)
    welcome_enabled = Column(Boolean, default=True)
    rules_text = Column(String, default="1. Be respectful.\n2. No spam or links.\n3. Follow admins.")
    anti_link = Column(Boolean, default=True)
    anti_flood = Column(Boolean, default=True)

class AdminPermission(Base):
    __tablename__ = "admin_permissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True)
    can_ban = Column(Boolean, default=False)
    can_warn = Column(Boolean, default=False)
    can_change_settings = Column(Boolean, default=False)

class AutoReply(Base):
    __tablename__ = "auto_replies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, unique=True, index=True) # Ex: "help"
    reply_text = Column(String) # Ex: "Please contact owner..."
