from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    safe_filename = Column(String(255), default="")
    document_type = Column(String(100), nullable=False)
    pages = Column(Integer, default=1)
    text_length = Column(Integer, default=0)
    summary = Column(Text, nullable=False)
    status = Column(String(50), default="completed")  # pending, completed, failed
    processing_error = Column(Text, default="")
    content_hash = Column(String(64), default="", index=True)
    extraction_warnings = Column(Text, default="")
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
    description = Column(Text, default="")
    deadline = Column(String(100), default="")
    deadline_time = Column(String(5), default="")
    priority = Column(String(20), default="LOW", index=True)
    category = Column(String(50), default="General", index=True)
    confidence = Column(Float, default=0.5)
    is_completed = Column(Boolean, default=False, index=True)
    detection_reason = Column(Text, default="")
    source_snippet = Column(Text, default="")
    page_number = Column(Integer, nullable=True)
    date_explicit = Column(Boolean, default=False)
    review_status = Column(String(30), default="pending")  # pending, accepted, corrected, rejected
    extraction_method = Column(String(50), default="rule_based")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    page_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="rules")


class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deadline_date = Column(String(100), nullable=False)
    deadline_time = Column(String(5), default="")
    description = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    confidence = Column(Float, default=0.5)
    detection_reason = Column(Text, default="")
    source_snippet = Column(Text, default="")
    page_number = Column(Integer, nullable=True)
    date_explicit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="deadlines")


class ReminderPreference(Base):
    __tablename__ = "reminder_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    enabled = Column(Boolean, nullable=False, default=True)
    desktop_enabled = Column(Boolean, nullable=False, default=False)
    email_enabled = Column(Boolean, nullable=False, default=False)
    remind_three_days = Column(Boolean, nullable=False, default=True)
    remind_one_day = Column(Boolean, nullable=False, default=True)
    remind_at_deadline = Column(Boolean, nullable=False, default=True)
    remind_overdue = Column(Boolean, nullable=False, default=False)
    date_only_time = Column(String(5), nullable=False, default="09:00")
    timezone = Column(String(100), nullable=False, default="UTC")
    updated_at = Column(DateTime, nullable=False, default=_utcnow_naive, onupdate=_utcnow_naive)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(task_id IS NOT NULL AND deadline_id IS NULL) OR "
            "(task_id IS NULL AND deadline_id IS NOT NULL)",
            name="ck_notification_single_target",
        ),
        UniqueConstraint(
            "user_id",
            "reminder_key",
            name="uq_notification_reminder_instance",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    deadline_id = Column(
        Integer,
        ForeignKey("deadlines.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_key = Column(String(64), nullable=False)
    reminder_key = Column(String(128), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    stage = Column(String(30), nullable=False)
    reminder_date = Column(String(10), nullable=False)
    deadline_at = Column(DateTime, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    desktop_notified_at = Column(DateTime, nullable=True)
    email_status = Column(String(20), nullable=False, default="disabled")
    email_attempts = Column(Integer, nullable=False, default=0)
    email_last_error = Column(Text, nullable=False, default="")
    email_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, index=True)

    task = relationship("Task")
    deadline = relationship("Deadline")
    document = relationship("Document")
