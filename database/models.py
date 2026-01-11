from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime # 👈 Yaha DateTime add kiya hai
from sqlalchemy.orm import declarative_base
from datetime import datetime # 👈 Ye line bhi zaroori hai

Base = declarative_base()

# 1. File Record Table
class FileRecord(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_token = Column(String, unique=True, index=True)
    file_id = Column(String)
    file_name = Column(String)
    file_type = Column(String)  # doc, video, photo
    uploader_id = Column(BigInteger)

# 2. Channel Table
class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, unique=True) # Channel ka ID
    channel_name = Column(String)
    added_by = Column(BigInteger)

# 3. Users Table (Isme Error aa raha tha)
class BotUser(Base):
    __tablename__ = "bot_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, index=True)
    joined_date = Column(DateTime, default=datetime.utcnow) # 👈 Ab ye chal jayega
