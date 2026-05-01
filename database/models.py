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
    uploader_id = Column(BigInteger) # Yeh decide karega ki kis customer ki file hai

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
    active_topic_id = Column(Integer, default=0)
    
    # --- PURANA ADMIN SYSTEM ---
    is_admin = Column(Boolean, default=False)
    
    # --- BOT 2 FEATURES (Warn, Global Ban, Temp Mute) ---
    warning_count = Column(Integer, default=0)
    is_global_banned = Column(Boolean, default=False)
    restricted_until = Column(DateTime, nullable=True)

    # 👇 NAYE SAAS DASHBOARD FEATURES (Goal 1) 👇
    role = Column(String, default="user") # Options: 'owner', 'admin', 'customer', 'user'
    web_username = Column(String, unique=True, nullable=True) # Login ID
    web_password = Column(String, nullable=True) # Login Password (Hashed)

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
    owner_id = Column(BigInteger, nullable=True) # NAYA: Kis customer ka group hai
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
    added_by = Column(BigInteger, nullable=True) # NAYA: Kisne add kiya
    keyword = Column(String, index=True) # NAYA: Unique hata diya gaya hai
    reply_text = Column(String) 

# 👇 NAYA: COMMUNITY MESSAGING (Goal 2) 👇
class CommunityMessage(Base):
    __tablename__ = "community_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(BigInteger)
    sender_role = Column(String) # Admin hai ya Customer
    message_text = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
