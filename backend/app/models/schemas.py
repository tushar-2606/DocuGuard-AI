from pydantic import BaseModel, Field
from typing import List


class ExtractedTask(BaseModel):
    task: str = Field(description="The actionable task the user needs to complete")
    deadline: str = Field(
        description="Deadline in YYYY-MM-DD format, or empty string if not found"
    )
    priority: str = Field(
        description="HIGH, MEDIUM, or LOW"
    )
    category: str = Field(
        description="Category such as Examination, Payment, Documents, Registration, Placement, Scholarship, etc."
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1"
    )


class DocumentAnalysis(BaseModel):
    document_type: str = Field(
        description="Type of document, such as examination_notice, placement_notice, scholarship_notice, circular, or general_notice"
    )
    summary: str = Field(
        description="Short summary of the document"
    )
    tasks: List[ExtractedTask]