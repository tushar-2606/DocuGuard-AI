import re
from datetime import datetime
from typing import List, Optional, Tuple

from dateparser.search import search_dates
from app.models.schemas import (
    DocumentAnalysis,
    ExtractedDeadline,
    ExtractedRule,
    ExtractedTask,
)


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

DEADLINE_KEYWORDS = [
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


def find_deadline(text: str) -> str:
    """
    Only returns a date when the surrounding text strongly
    indicates that the date is a deadline/due date.
    """
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    for sentence in sentences:
        lower = sentence.lower()
        if not any(keyword in lower for keyword in DEADLINE_KEYWORDS):
            continue

        dates = extract_dates(sentence)
        if dates:
            return dates[0][1]

    return ""


# ---------------------------------------------------------
# Actionable sentence detection
# ---------------------------------------------------------

ACTION_PATTERNS = [
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


def is_actionable(sentence: str) -> bool:
    lower = sentence.lower()
    return any(re.search(pattern, lower) for pattern in ACTION_PATTERNS)


def get_action_keyword(sentence: str) -> str:
    lower = sentence.lower()
    for pattern in ACTION_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            return match.group().strip()
    return "action"


# ---------------------------------------------------------
# Rules detection
# ---------------------------------------------------------

PROHIBITED_PATTERNS = [
    r"\bmust not\b",
    r"\bshall not\b",
    r"\bprohibited\b",
    r"\bstrictly forbidden\b",
    r"\bnot allowed\b",
    r"\bdo not\b",
    r"\bnever\b",
    r"\bunder no circumstances\b",
    r"\bwill not be permitted\b",
    r"\bno student shall\b",
]

MANDATORY_PATTERNS = [
    r"\bis mandatory\b",
    r"\bshall be mandatory\b",
    r"\bcompulsory\b",
    r"\bstrictly required\b",
    r"\brequired to comply\b",
    r"\bmust adhere\b",
    r"\bmust comply\b",
    r"\bcompliance is mandatory\b",
    r"\bfailure to .* will result\b",
    r"\bpenalty\b",
    r"\bmust strictly\b",
]

RECOMMENDED_PATTERNS = [
    r"\badvised to\b",
    r"\brecommended to\b",
    r"\bencouraged to\b",
    r"\bit is suggested\b",
    r"\bshould ensure\b",
    r"\bguidelines require\b",
    r"\bstudents are requested\b",
]


def detect_rule(sentence: str) -> Optional[Tuple[str, str, str]]:
    """
    Returns (rule_type, matched_keyword, clean_text) or None
    """
    lower = sentence.lower().strip()

    for pattern in PROHIBITED_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            return ("PROHIBITED", match.group(), sentence.strip())

    for pattern in MANDATORY_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            return ("MANDATORY", match.group(), sentence.strip())

    for pattern in RECOMMENDED_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            return ("RECOMMENDED", match.group(), sentence.strip())

    return None


# ---------------------------------------------------------
# Extract task wording
# ---------------------------------------------------------

def extract_task(sentence: str) -> str:
    sentence = sentence.strip()

    # Remove bullets/numbers
    sentence = re.sub(r"^[\s•\-*]+", "", sentence)
    sentence = re.sub(r"^\d+[\).\s]+", "", sentence)

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
        score = sum(1 for keyword in keywords if keyword in lower)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


# ---------------------------------------------------------
# Confidence
# ---------------------------------------------------------

def calculate_confidence(sentence: str, deadline: str) -> float:
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

    # Split into clean lines/sentences
    raw_lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    tasks: List[ExtractedTask] = []
    rules: List[ExtractedRule] = []
    deadlines: List[ExtractedDeadline] = []

    seen_tasks = set()
    seen_rules = set()
    seen_deadlines = set()

    for line in raw_lines:
        line_clean = line.strip()
        if len(line_clean) < 8:
            continue

        # 1. Check for Rules first (Prohibited, Mandatory, Recommended)
        rule_info = detect_rule(line_clean)
        if rule_info:
            rule_type, trigger_keyword, rule_full_text = rule_info
            rule_summary = re.sub(r"^[\s•\-*]+", "", rule_full_text)
            rule_summary = re.sub(r"^\d+[\).\s]+", "", rule_summary).strip()
            norm_rule = rule_summary.lower()

            if norm_rule not in seen_rules and len(rule_summary.split()) >= 3:
                seen_rules.add(norm_rule)
                rule_cat = detect_category(line_clean)
                confidence = 0.90 if rule_type == "PROHIBITED" else 0.85

                if rule_type == "PROHIBITED":
                    reason = f"Detected as a prohibited compliance rule because the statement contains strict prohibition pattern ('{trigger_keyword}')."
                elif rule_type == "MANDATORY":
                    reason = f"Detected as a mandatory rule because the statement contains compulsory institutional obligation ('{trigger_keyword}')."
                else:
                    reason = f"Detected as a recommended guideline because the statement contains advisory language ('{trigger_keyword}')."

                rules.append(
                    ExtractedRule(
                        rule=rule_summary,
                        rule_type=rule_type,
                        category=rule_cat,
                        confidence=confidence,
                        detection_reason=reason,
                        source_snippet=line_clean,
                    )
                )

        # 2. Check for Actionable Tasks
        if is_actionable(line_clean):
            task_text = extract_task(line_clean)
            if task_text and len(task_text.split()) >= 3:
                normalized = task_text.lower()
                if normalized not in seen_tasks:
                    seen_tasks.add(normalized)
                    deadline = find_deadline(line_clean)
                    priority = detect_priority(line_clean, deadline)
                    category = detect_category(line_clean)
                    confidence = calculate_confidence(line_clean, deadline)
                    action_verb = get_action_keyword(line_clean)

                    reason_parts = [f"Detected actionable action verb '{action_verb}'"]
                    if deadline:
                        reason_parts.append(f"with deadline '{deadline}'")
                    if category != "General":
                        reason_parts.append(f"in category '{category}'")
                    reason = (
                        "Detected as an actionable task because the sentence contains "
                        + ", ".join(reason_parts)
                        + "."
                    )

                    tasks.append(
                        ExtractedTask(
                            task=task_text,
                            deadline=deadline,
                            priority=priority,
                            category=category,
                            confidence=confidence,
                            detection_reason=reason,
                            source_snippet=line_clean,
                        )
                    )

                    # Also register as a Deadline item if deadline date is present
                    if deadline and deadline not in seen_deadlines:
                        seen_deadlines.add(deadline)
                        deadlines.append(
                            ExtractedDeadline(
                                deadline_date=deadline,
                                description=task_text,
                                confidence=confidence,
                                detection_reason=f"Detected deadline tied to actionable task '{task_text}'.",
                                source_snippet=line_clean,
                            )
                        )

        # 3. Check for standalone Deadlines
        elif any(keyword in line_clean.lower() for keyword in DEADLINE_KEYWORDS):
            extracted = extract_dates(line_clean)
            if extracted:
                for orig_date, iso_date in extracted:
                    if iso_date not in seen_deadlines:
                        seen_deadlines.add(iso_date)
                        clean_desc = extract_task(line_clean)
                        deadlines.append(
                            ExtractedDeadline(
                                deadline_date=iso_date,
                                description=clean_desc if clean_desc else "Important institutional deadline",
                                confidence=0.80,
                                detection_reason=f"Detected deadline date '{orig_date}' with contextual deadline indicator.",
                                source_snippet=line_clean,
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

    parts = []
    if tasks:
        parts.append(f"{len(tasks)} actionable task(s)")
    if rules:
        parts.append(f"{len(rules)} compliance rule(s)")
    if deadlines:
        parts.append(f"{len(deadlines)} key deadline(s)")

    if parts:
        summary = f"This document contains {', '.join(parts)} requiring attention."
    else:
        summary = "No clear actionable tasks or rules were detected in this document."

    return DocumentAnalysis(
        document_type=document_type,
        summary=summary,
        tasks=tasks,
        rules=rules,
        deadlines=deadlines,
    )