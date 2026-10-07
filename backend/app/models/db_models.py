from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Document.upload_timestamp)",
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(100), nullable=False)
    pages = Column(Integer, default=1)
    text_length = Column(Integer, default=0)
    summary = Column(Text, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="documents")
    tasks = relationship("Task", back_populates="document", cascade="all, delete-orphan")
    rules = relationship("Rule", back_populates="document", cascade="all, delete-orphan")
    deadlines = relationship("Deadline", back_populates="document", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_text = Column(Text, nullable=False)
    deadline = Column(String(100), default="")
    priority = Column(String(20), default="LOW")
    category = Column(String(50), default="General")
    confidence = Column(Float, default=0.5)
    is_completed = Column(Boolean, default=False)
    detection_reason = Column(Text, default="")
    source_snippet = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="tasks")


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_text = Column(Text, nullable=False)
    rule_type = Column(String(50), nullable=False)  # MANDATORY, PROHIBITED, RECOMMENDED
    category = Column(String(50), default="General")
    confidence = Column(Float, default=0.5)
    detection_reason = Column(Text, default="")
    source_snippet = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="rules")


class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deadline_date = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    confidence = Column(Float, default=0.5)
    detection_reason = Column(Text, default="")
    source_snippet = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="deadlines")
