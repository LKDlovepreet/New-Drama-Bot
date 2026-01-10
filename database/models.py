#table ka design 

from sqlalchemy import Column, Integer, String, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class FileRecord(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_token = Column(String, unique=True, index=True)
    file_id = Column(String)
    file_name = Column(String)
    file_type = Column(String)  # doc, video, photo
    uploader_id = Column(BigInteger)

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, unique=True) # Channel ka ID
    channel_name = Column(String)
    added_by = Column(BigInteger)

class BotUser(Base):
    __tablename__ = "bot_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, index=True) # User ka Telegram ID
    joined_date = Column(DateTime, default=datetime.utcnow)
