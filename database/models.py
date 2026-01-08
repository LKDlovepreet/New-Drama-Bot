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
