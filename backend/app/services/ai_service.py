import re
from datetime import datetime
from typing import List, Optional, Tuple

from dateparser.search import search_dates
from app.models.schemas import DocumentAnalysis, ExtractedTask


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

CATEGORIES = [
    "Examination",
    "Payment",
    "Documents",
    "Registration",
    "Placement",
    "Internship",
    "Scholarship",
    "Attendance",
    "Academic",
    "General",
]

# Lazy-loaded so the backend starts quickly.
_classifier = None


# ---------------------------------------------------------
# Text cleanup
# ---------------------------------------------------------

def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------
# Date extraction
# ---------------------------------------------------------

def extract_dates(text: str) -> List[Tuple[str, str]]:
    """
    Returns:
        [(original_date_text, YYYY-MM-DD), ...]
    """

    month = (
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    )
    explicit_date = re.compile(
        rf"\b(?:"
        rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{month})\s*,?\s*\d{{4}}"
        rf"|(?:{month})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}"
        rf")\b",
        flags=re.IGNORECASE,
    )

    results = []
    explicit_matches = list(explicit_date.finditer(text))
    for match in explicit_matches:
        original = match.group().strip()
        normalized = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", original, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized.replace(",", " ")).strip()

        parsed_date = None
        for date_format in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                parsed_date = datetime.strptime(normalized, date_format)
                break
            except ValueError:
                continue

        if parsed_date:
            results.append((original, parsed_date.strftime("%Y-%m-%d")))

    if explicit_matches:
        return results

    matches = search_dates(
        text,
        languages=["en"],
        settings={
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DAY_OF_MONTH": "first",
        },
    )
    if not matches:
        return results

    for original, parsed_date in matches:
        if parsed_date:
            results.append((original.strip(), parsed_date.strftime("%Y-%m-%d")))

    return results


# ---------------------------------------------------------
# Find deadline from a sentence
# ---------------------------------------------------------

def find_deadline(text: str) -> str:
    """
    Only returns a date when the surrounding text strongly
    indicates that the date is a deadline/due date.
    """

    deadline_keywords = [
        "deadline",
        "last date",
        "due date",
        "submit by",
        "submission date",
        "apply by",
        "pay by",
        "before",
        "on or before",
        "latest by",
        "must be completed by",
        "complete by",
    ]

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    for sentence in sentences:

        lower = sentence.lower()

        if not any(keyword in lower for keyword in deadline_keywords):
            continue

        dates = extract_dates(sentence)

        if dates:
            return dates[0][1]

    return ""


# ---------------------------------------------------------
# Identify actionable sentences
# ---------------------------------------------------------

def is_actionable(sentence: str) -> bool:

    lower = sentence.lower()

    action_patterns = [
        r"\bsubmit\b",
        r"\bregister\b",
        r"\bapply\b",
        r"\bupload\b",
        r"\bpay\b",
        r"\bcomplete\b",
        r"\bfill\b",
        r"\bverify\b",
        r"\bdownload\b",
        r"\bcollect\b",
        r"\bappear\b",
        r"\battend\b",
        r"\bbring\b",
        r"\bdeposit\b",
        r"\brenew\b",
        r"\bconfirm\b",
        r"\bprovide\b",
        r"\bsend\b",
        r"\breport\b",
        r"\benroll\b",
        r"\bjoin\b",
    ]

    return any(re.search(pattern, lower) for pattern in action_patterns)


# ---------------------------------------------------------
# Extract task wording
# ---------------------------------------------------------

def extract_task(sentence: str) -> str:

    sentence = sentence.strip()

    # Remove bullets/numbers
    sentence = re.sub(
        r"^[\s•\-*]+",
        "",
        sentence
    )

    sentence = re.sub(
        r"^\d+[\).\s]+",
        "",
        sentence
    )

    # Remove deadline tail
    sentence = re.sub(
        r"\s*(deadline|last date|due date|submit by|apply by|pay by)"
        r"\s*[:\-]?\s*.*$",
        "",
        sentence,
        flags=re.IGNORECASE,
    )

    sentence = sentence.strip(" .:-")

    if len(sentence) > 180:
        sentence = sentence[:177] + "..."

    return sentence


# ---------------------------------------------------------
# Priority
# ---------------------------------------------------------

def detect_priority(sentence: str, deadline: str) -> str:

    lower = sentence.lower()

    high_words = [
        "mandatory",
        "compulsory",
        "urgent",
        "immediately",
        "must",
        "required",
        "last date",
        "deadline",
        "due",
        "pay",
        "submit",
    ]

    medium_words = [
        "important",
        "recommended",
        "please",
        "verify",
        "complete",
        "register",
        "apply",
        "upload",
    ]

    if any(word in lower for word in high_words):
        return "HIGH"

    if deadline:
        return "HIGH"

    if any(word in lower for word in medium_words):
        return "MEDIUM"

    return "LOW"


# ---------------------------------------------------------
# Category
# ---------------------------------------------------------

def detect_category(sentence: str) -> str:

    lower = sentence.lower()

    category_keywords = {
        "Examination": [
            "exam",
            "examination",
            "hall ticket",
            "admit card",
            "exam form",
            "semester",
        ],
        "Payment": [
            "fee",
            "fees",
            "payment",
            "pay",
            "amount",
            "deposit",
        ],
        "Documents": [
            "document",
            "certificate",
            "photo",
            "proof",
            "upload",
            "attach",
        ],
        "Registration": [
            "registration",
            "register",
            "enrollment",
            "enrol",
        ],
        "Placement": [
            "placement",
            "campus",
            "company",
            "recruitment",
            "job",
            "interview",
        ],
        "Internship": [
            "internship",
            "intern",
            "training",
        ],
        "Scholarship": [
            "scholarship",
            "financial aid",
            "stipend",
        ],
        "Attendance": [
            "attendance",
            "present",
            "absent",
        ],
        "Academic": [
            "assignment",
            "project",
            "course",
            "academic",
            "faculty",
        ],
    }

    best_category = "General"
    best_score = 0

    for category, keywords in category_keywords.items():

        score = sum(
            1
            for keyword in keywords
            if keyword in lower
        )

        if score > best_score:
            best_score = score
            best_category = category

    return best_category


# ---------------------------------------------------------
# Confidence
# ---------------------------------------------------------

def calculate_confidence(
    sentence: str,
    deadline: str
) -> float:

    score = 0.55

    if is_actionable(sentence):
        score += 0.15

    if deadline:
        score += 0.15

    if detect_category(sentence) != "General":
        score += 0.10

    if len(sentence) >= 15:
        score += 0.05

    return min(round(score, 2), 1.0)


# ---------------------------------------------------------
# Main analysis
# ---------------------------------------------------------

def analyze_document(text: str) -> DocumentAnalysis:

    if not text or not text.strip():
        raise ValueError("Document text is empty.")

    text = clean_text(text)

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    tasks: List[ExtractedTask] = []

    seen = set()

    for line in lines:

        if not is_actionable(line):
            continue

        task_text = extract_task(line)

        if not task_text:
            continue

        # Ignore very short/noisy lines
        if len(task_text.split()) < 3:
            continue

        normalized = task_text.lower()

        if normalized in seen:
            continue

        seen.add(normalized)

        deadline = find_deadline(line)

        priority = detect_priority(
            line,
            deadline
        )

        category = detect_category(line)

        confidence = calculate_confidence(
            line,
            deadline
        )

        tasks.append(
            ExtractedTask(
                task=task_text,
                deadline=deadline,
                priority=priority,
                category=category,
                confidence=confidence,
            )
        )

    # -----------------------------------------------------
    # Document type
    # -----------------------------------------------------

    lower_text = text.lower()

    if "examination" in lower_text or "exam form" in lower_text:
        document_type = "examination_notice"

    elif "placement" in lower_text:
        document_type = "placement_notice"

    elif "scholarship" in lower_text:
        document_type = "scholarship_notice"

    elif "internship" in lower_text:
        document_type = "internship_notice"

    elif "circular" in lower_text:
        document_type = "circular"

    else:
        document_type = "general_notice"

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    if tasks:
        summary = (
            f"This document contains {len(tasks)} "
            f"actionable task(s) requiring attention."
        )
    else:
        summary = (
            "No clear actionable tasks were detected "
            "in this document."
        )

    return DocumentAnalysis(
        document_type=document_type,
        summary=summary,
        tasks=tasks,
    )