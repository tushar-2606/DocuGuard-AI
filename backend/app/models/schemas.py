from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# --------------------------------------------------
# Auth Schemas
# --------------------------------------------------

class UserRegister(BaseModel):
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., min_length=1, description="Full name of user")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    confirm_password: Optional[str] = Field(None, description="Password confirmation")


class UserLogin(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --------------------------------------------------
# Intelligence / Extraction Schemas
# --------------------------------------------------

class ExtractedTask(BaseModel):
    id: Optional[int] = None
    task: str = Field(description="The actionable task the user needs to complete")
    deadline: str = Field(
        default="",
        description="Deadline in YYYY-MM-DD format, or empty string if not found",
    )
    priority: str = Field(
        default="LOW",
        description="HIGH, MEDIUM, or LOW",
    )
    category: str = Field(
        default="General",
        description="Category such as Examination, Payment, Documents, Registration, Placement, Scholarship, etc.",
    )
    confidence: float = Field(
        default=0.7,
        description="Confidence score between 0 and 1",
    )
    is_completed: bool = Field(
        default=False,
        description="Whether the task has been marked completed",
    )
    detection_reason: str = Field(
        default="",
        description="Why this item was classified as an actionable task",
    )
    source_snippet: str = Field(
        default="",
        description="Original text statement from document",
    )


class ExtractedRule(BaseModel):
    id: Optional[int] = None
    rule: str = Field(description="The compliance, institutional, or conduct rule")
    rule_type: str = Field(
        default="MANDATORY",
        description="MANDATORY, PROHIBITED, or RECOMMENDED",
    )
    category: str = Field(
        default="General",
        description="Category such as Examination, Academic, Documents, Placement, etc.",
    )
    confidence: float = Field(
        default=0.8,
        description="Confidence score between 0 and 1",
    )
    detection_reason: str = Field(
        default="",
        description="Why this item was classified as a rule",
    )
    source_snippet: str = Field(
        default="",
        description="Original statement from document",
    )


class ExtractedDeadline(BaseModel):
    id: Optional[int] = None
    deadline_date: str = Field(description="YYYY-MM-DD format")
    description: str = Field(description="Context or action tied to this deadline")
    is_completed: bool = Field(default=False)
    confidence: float = Field(default=0.8)
    detection_reason: str = Field(
        default="",
        description="Why this date was recognized as a deadline",
    )
    source_snippet: str = Field(
        default="",
        description="Original text statement from document",
    )


class DocumentAnalysis(BaseModel):
    document_type: str = Field(
        description="Type of document, such as examination_notice, placement_notice, scholarship_notice, circular, or general_notice",
    )
    summary: str = Field(
        description="Short summary of the document",
    )
    tasks: List[ExtractedTask] = Field(default_factory=list)
    rules: List[ExtractedRule] = Field(default_factory=list)
    deadlines: List[ExtractedDeadline] = Field(default_factory=list)


# --------------------------------------------------
# SaaS Document & Workspace Schemas
# --------------------------------------------------

class DocumentSummaryItem(BaseModel):
    id: int
    filename: str
    document_type: str
    pages: int
    upload_timestamp: datetime
    summary: str
    task_count: int
    completed_task_count: int
    rule_count: int
    deadline_count: int

    class Config:
        from_attributes = True


class DocumentDetailResponse(BaseModel):
    id: int
    filename: str
    document_type: str
    pages: int
    text_length: int
    summary: str
    upload_timestamp: datetime
    analysis: DocumentAnalysis

    class Config:
        from_attributes = True


class TaskToggleResponse(BaseModel):
    id: int
    is_completed: bool


class DeadlineItem(BaseModel):
    id: int
    document_id: int
    document_name: str
    deadline_date: str
    description: str
    is_completed: bool
    is_overdue: bool
    confidence: float
    detection_reason: str = ""
    source_snippet: str = ""


class RuleItem(BaseModel):
    id: int
    document_id: int
    document_name: str
    rule: str
    rule_type: str
    category: str
    confidence: float
    detection_reason: str = ""
    source_snippet: str = ""


class TaskItem(BaseModel):
    id: int
    document_id: int
    document_name: str
    task: str
    deadline: str
    priority: str
    category: str
    confidence: float
    is_completed: bool
    detection_reason: str = ""
    source_snippet: str = ""


class DashboardStats(BaseModel):
    total_documents: int
    pending_tasks: int
    completed_tasks: int
    upcoming_deadlines: int
    overdue_deadlines: int
    mandatory_rules: int
    prohibited_rules: int
    recommended_rules: int
    recent_documents: List[DocumentSummaryItem]
    upcoming_deadline_items: List[DeadlineItem]