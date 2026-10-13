from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------
# Auth Schemas
# --------------------------------------------------

class UserRegister(BaseModel):
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name of user")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 characters)")
    confirm_password: Optional[str] = Field(None, description="Password confirmation")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Full name is required.")
        return cleaned


class UserLogin(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=1, max_length=128, description="User password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


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
    description: str = Field(default="", description="Optional longer description")
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
        description="Heuristic confidence score between 0 and 1 (not a calibrated probability)",
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
    page_number: Optional[int] = Field(default=None, description="1-based page when known")
    date_explicit: bool = Field(
        default=False,
        description="True when deadline came from an explicit calendar date near the action",
    )
    review_status: str = Field(
        default="pending",
        description="pending, accepted, corrected, or rejected",
    )
    extraction_method: str = Field(
        default="rule_based",
        description="How the task was extracted (always rule_based in this build)",
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
        description="Heuristic confidence score between 0 and 1",
    )
    detection_reason: str = Field(
        default="",
        description="Why this item was classified as a rule",
    )
    source_snippet: str = Field(
        default="",
        description="Original statement from document",
    )
    page_number: Optional[int] = None


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
    page_number: Optional[int] = None
    date_explicit: bool = Field(default=False)


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
    warnings: List[str] = Field(
        default_factory=list,
        description="Transparent extraction warnings / uncertainty notes",
    )


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
    status: str = "completed"
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
    status: str = "completed"
    processing_error: str = ""
    extraction_warnings: str = ""
    upload_timestamp: datetime
    analysis: DocumentAnalysis

    class Config:
        from_attributes = True


class TaskToggleResponse(BaseModel):
    id: int
    is_completed: bool


class TaskUpdateRequest(BaseModel):
    task: Optional[str] = Field(None, min_length=1, max_length=2000)
    description: Optional[str] = Field(None, max_length=4000)
    deadline: Optional[str] = Field(None, max_length=32)
    priority: Optional[str] = Field(None, pattern="^(HIGH|MEDIUM|LOW)$")
    category: Optional[str] = Field(None, max_length=50)
    review_status: Optional[str] = Field(
        None,
        pattern="^(pending|accepted|corrected|rejected)$",
    )
    is_completed: Optional[bool] = None


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
    page_number: Optional[int] = None
    date_explicit: bool = False


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
    page_number: Optional[int] = None


class TaskItem(BaseModel):
    id: int
    document_id: int
    document_name: str
    task: str
    description: str = ""
    deadline: str
    priority: str
    category: str
    confidence: float
    is_completed: bool
    detection_reason: str = ""
    source_snippet: str = ""
    page_number: Optional[int] = None
    date_explicit: bool = False
    review_status: str = "pending"
    extraction_method: str = "rule_based"


class DashboardStats(BaseModel):
    total_documents: int
    pending_tasks: int
    completed_tasks: int
    upcoming_deadlines: int
    overdue_deadlines: int
    mandatory_rules: int
    prohibited_rules: int
    recommended_rules: int
    tasks_by_priority: Dict[str, int] = Field(default_factory=dict)
    tasks_by_category: Dict[str, int] = Field(default_factory=dict)
    documents_failed: int = 0
    recent_documents: List[DocumentSummaryItem]
    upcoming_deadline_items: List[DeadlineItem]
