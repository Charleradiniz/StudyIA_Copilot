from sqlalchemy import Column, String, DateTime
from app.db.database import Base
import uuid
from datetime import datetime

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String)
    faiss_path = Column(String)
    json_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)