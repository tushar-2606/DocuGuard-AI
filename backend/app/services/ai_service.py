"""
Deterministic rule-based document intelligence.

Confidence scores are heuristic signals for review prioritization — they are
NOT calibrated probabilities and must not be presented as LLM certainty.
"""

from __future__ import annotations

import calendar
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
    "Meeting",
    "General",
]

PAGE_MARKER_RE = re.compile(r"^--- Page (\d+) ---$")

NEGATION_PATTERNS = [
    r"\bno need (?:to|for)\b",
    r"\bnot required\b",
    r"\bdo not (?:need to|have to|submit|apply|pay|register|attend)\b",
    r"\bneed not\b",
    r"\bwithout (?:having to|needing to)\b",
    r"\bexempt(?:ed)? from\b",
    r"\boptional(?:ly)?\b(?!.*\bmust\b)",
]

HYPOTHETICAL_PATTERNS = [
    r"\bif (?:you|students?|applicants?)\b",
    r"\bin case (?:of|you)\b",
    r"\bshould you (?:wish|want|choose)\b",
    r"\bfor example\b",
    r"\be\.g\.\b",
    r"\bsuch as\b",
    r"\bwould be (?:required|needed)\b",
    r"\bmight (?:need|be required)\b",
    r"\bcould (?:submit|apply|pay)\b",
]

HISTORICAL_PATTERNS = [
    r"\bpreviously\b",
    r"\bin the (?:past|previous year|last academic year)\b",
    r"\bwas (?:submitted|paid|completed|held)\b",
    r"\bhave (?:already )?(?:been )?(?:submitted|paid|completed)\b",
    r"\bearlier notice\b",
]

INTRO_PATTERNS = [
    r"^this (?:notice|circular|document|letter)\b",
    r"^dear (?:students?|all|sir|madam)\b",
    r"^please (?:note|find|be informed)\b",
    r"^subject\s*:",
    r"^ref(?:erence)?\s*:",
    r"^regarding\s*:",
]

DEADLINE_KEYWORDS = [
    "deadline",
    "last date",
    "due date",
    "submit by",
    "submission date",
    "apply by",
    "pay by",
    "on or before",
    "latest by",
    "must be completed by",
    "complete by",
    "due on",
    "closes on",
]

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
    r"\bschedule\b",
    r"\bmeet\b",
]


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def iter_page_lines(text: str) -> List[Tuple[Optional[int], str]]:
    """Yield (page_number, line) pairs from text with --- Page N --- markers."""
    current_page: Optional[int] = None
    results: List[Tuple[Optional[int], str]] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        marker = PAGE_MARKER_RE.match(line)
        if marker:
            current_page = int(marker.group(1))
            continue
        results.append((current_page, line))
    return results


def _is_valid_calendar_date(year: int, month: int, day: int) -> bool:
    if month < 1 or month > 12 or day < 1 or day > 31:
        return False
    try:
        return day <= calendar.monthrange(year, month)[1]
    except Exception:
        return False


def extract_dates(text: str, allow_relative: bool = False) -> List[Tuple[str, str, bool]]:
    """
    Returns list of (original_text, YYYY-MM-DD, is_explicit).
    Relative dates are only resolved when allow_relative=True AND a trustworthy
    reference context is provided by the caller (currently unused / off by default).
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
        rf"|\d{{4}}-\d{{2}}-\d{{2}}"
        rf"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{4}}"
        rf")\b",
        flags=re.IGNORECASE,
    )

    results: List[Tuple[str, str, bool]] = []
    seen_iso = set()

    for match in explicit_date.finditer(text):
        original = match.group().strip()
        iso = _normalize_explicit_date(original)
        if iso and iso not in seen_iso:
            seen_iso.add(iso)
            results.append((original, iso, True))

    if results or not allow_relative:
        return results

    matches = search_dates(
        text,
        languages=["en"],
        settings={
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DAY_OF_MONTH": "first",
            "STRICT_PARSING": True,
        },
    )
    if not matches:
        return results

    for original, parsed_date in matches:
        if not parsed_date:
            continue
        iso = parsed_date.strftime("%Y-%m-%d")
        if iso not in seen_iso:
            seen_iso.add(iso)
            results.append((original.strip(), iso, False))

    return results


def _normalize_explicit_date(original: str) -> Optional[str]:
    text = original.strip()

    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        y, m, d = map(int, iso_match.groups())
        if _is_valid_calendar_date(y, m, d):
            return f"{y:04d}-{m:02d}-{d:02d}"
        return None

    slash = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if slash:
        a, b, y = map(int, slash.groups())
        # Prefer day/month/year when first part > 12; else assume month/day/year
        if a > 12:
            d, m = a, b
        elif b > 12:
            m, d = a, b
        else:
            d, m = a, b  # institutional notices often use DD/MM/YYYY
        if _is_valid_calendar_date(y, m, d):
            return f"{y:04d}-{m:02d}-{d:02d}"
        return None

    normalized = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized.replace(",", " ")).strip()
    for date_format in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            parsed = datetime.strptime(normalized, date_format)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def find_deadline(text: str) -> Tuple[str, bool]:
    """Return (iso_date, date_explicit) for the first deadline-linked date."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        lower = sentence.lower()
        if not any(keyword in lower for keyword in DEADLINE_KEYWORDS):
            # Also accept "by <date>" near action verbs
            if not re.search(r"\bby\b.+\d", lower):
                continue
        dates = extract_dates(sentence, allow_relative=False)
        if dates:
            return dates[0][1], dates[0][2]
    return "", False


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


def should_skip_sentence(sentence: str) -> Optional[str]:
    """Return a skip reason, or None if the sentence may yield a task."""
    lower = sentence.lower().strip()
    if len(lower) < 8:
        return "too_short"
    if any(re.search(p, lower) for p in INTRO_PATTERNS):
        return "introductory"
    if any(re.search(p, lower) for p in NEGATION_PATTERNS):
        return "negated"
    if any(re.search(p, lower) for p in HYPOTHETICAL_PATTERNS):
        return "hypothetical"
    if any(re.search(p, lower) for p in HISTORICAL_PATTERNS):
        return "historical"
    return None


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


def extract_task(sentence: str) -> str:
    sentence = sentence.strip()
    sentence = re.sub(r"^[\s•\-*]+", "", sentence)
    sentence = re.sub(r"^\d+[\).\s]+", "", sentence)
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


def detect_priority(sentence: str, deadline: str) -> str:
    lower = sentence.lower()
    high_words = [
        "mandatory", "compulsory", "urgent", "immediately", "must",
        "required", "last date", "deadline", "due",
    ]
    medium_words = [
        "important", "recommended", "please", "verify", "complete",
        "register", "apply", "upload", "pay", "submit",
    ]
    if any(word in lower for word in high_words):
        return "HIGH"
    if deadline:
        return "HIGH"
    if any(word in lower for word in medium_words):
        return "MEDIUM"
    return "LOW"


def detect_category(sentence: str) -> str:
    lower = sentence.lower()
    category_keywords = {
        "Examination": ["exam", "examination", "hall ticket", "admit card", "exam form", "semester"],
        "Payment": ["fee", "fees", "payment", "pay", "amount", "deposit"],
        "Documents": ["document", "certificate", "photo", "proof", "upload", "attach"],
        "Registration": ["registration", "register", "enrollment", "enrol"],
        "Placement": ["placement", "campus", "company", "recruitment", "job", "interview"],
        "Internship": ["internship", "intern", "training"],
        "Scholarship": ["scholarship", "financial aid", "stipend"],
        "Attendance": ["attendance", "present", "absent"],
        "Meeting": ["meeting", "conference", "webinar", "seminar"],
        "Academic": ["assignment", "project", "course", "academic", "faculty"],
    }
    best_category = "General"
    best_score = 0
    for category, keywords in category_keywords.items():
        score = sum(1 for keyword in keywords if keyword in lower)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def calculate_confidence(sentence: str, deadline: str, date_explicit: bool) -> float:
    """Heuristic score only — not a calibrated probability."""
    score = 0.50
    if is_actionable(sentence):
        score += 0.15
    if deadline and date_explicit:
        score += 0.18
    elif deadline:
        score += 0.08
    if detect_category(sentence) != "General":
        score += 0.08
    if len(sentence) >= 15:
        score += 0.05
    if should_skip_sentence(sentence):
        score -= 0.25
    return max(0.05, min(round(score, 2), 0.95))


def _normalize_for_dedupe(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Light stemming-style collapse of common variants
    text = text.replace("registration", "register").replace("submission", "submit")
    return text


def analyze_document(text: str) -> DocumentAnalysis:
    if not text or not text.strip():
        raise ValueError("Document text is empty.")

    text = clean_text(text)
    page_lines = iter_page_lines(text)
    if not page_lines:
        # Fallback when markers are absent
        page_lines = [(None, line.strip()) for line in text.split("\n") if line.strip()]

    tasks: List[ExtractedTask] = []
    rules: List[ExtractedRule] = []
    deadlines: List[ExtractedDeadline] = []
    warnings: List[str] = []

    seen_tasks = set()
    seen_rules = set()
    seen_deadlines = set()
    skipped = {"negated": 0, "hypothetical": 0, "historical": 0, "introductory": 0}

    for page_number, line_clean in page_lines:
        if len(line_clean) < 8:
            continue

        skip_reason = should_skip_sentence(line_clean)

        # Rules: allow prohibition/mandatory language even when skip would apply
        # for tasks (e.g. "must not"), but skip pure historical/intro fluff.
        rule_info = detect_rule(line_clean)
        if rule_info and skip_reason not in {"historical", "introductory", "too_short"}:
            rule_type, trigger_keyword, rule_full_text = rule_info
            rule_summary = re.sub(r"^[\s•\-*]+", "", rule_full_text)
            rule_summary = re.sub(r"^\d+[\).\s]+", "", rule_summary).strip()
            norm_rule = _normalize_for_dedupe(rule_summary)
            if norm_rule not in seen_rules and len(rule_summary.split()) >= 3:
                seen_rules.add(norm_rule)
                confidence = 0.90 if rule_type == "PROHIBITED" else 0.85
                if rule_type == "PROHIBITED":
                    reason = (
                        f"Detected as a prohibited compliance rule because the statement "
                        f"contains strict prohibition pattern ('{trigger_keyword}')."
                    )
                elif rule_type == "MANDATORY":
                    reason = (
                        f"Detected as a mandatory rule because the statement contains "
                        f"compulsory institutional obligation ('{trigger_keyword}')."
                    )
                else:
                    reason = (
                        f"Detected as a recommended guideline because the statement "
                        f"contains advisory language ('{trigger_keyword}')."
                    )
                rules.append(
                    ExtractedRule(
                        rule=rule_summary,
                        rule_type=rule_type,
                        category=detect_category(line_clean),
                        confidence=confidence,
                        detection_reason=reason,
                        source_snippet=line_clean,
                        page_number=page_number,
                    )
                )

        if skip_reason:
            if skip_reason in skipped:
                skipped[skip_reason] += 1
            continue

        if is_actionable(line_clean):
            task_text = extract_task(line_clean)
            if task_text and len(task_text.split()) >= 3:
                normalized = _normalize_for_dedupe(task_text)
                if normalized not in seen_tasks:
                    seen_tasks.add(normalized)
                    deadline, date_explicit = find_deadline(line_clean)
                    priority = detect_priority(line_clean, deadline)
                    category = detect_category(line_clean)
                    confidence = calculate_confidence(line_clean, deadline, date_explicit)
                    action_verb = get_action_keyword(line_clean)

                    reason_parts = [f"Detected actionable action verb '{action_verb}'"]
                    if deadline:
                        kind = "explicit" if date_explicit else "associated"
                        reason_parts.append(f"with {kind} deadline '{deadline}'")
                    if category != "General":
                        reason_parts.append(f"in category '{category}'")
                    reason = (
                        "Detected as an actionable task because the sentence contains "
                        + ", ".join(reason_parts)
                        + ". Confidence is a heuristic score, not a calibrated probability."
                    )

                    tasks.append(
                        ExtractedTask(
                            task=task_text,
                            description="",
                            deadline=deadline,
                            priority=priority,
                            category=category,
                            confidence=confidence,
                            detection_reason=reason,
                            source_snippet=line_clean,
                            page_number=page_number,
                            date_explicit=date_explicit,
                            review_status="pending",
                            extraction_method="rule_based",
                        )
                    )

                    if deadline and deadline not in seen_deadlines:
                        seen_deadlines.add(deadline)
                        deadlines.append(
                            ExtractedDeadline(
                                deadline_date=deadline,
                                description=task_text,
                                confidence=confidence,
                                detection_reason=f"Detected deadline tied to actionable task '{task_text}'.",
                                source_snippet=line_clean,
                                page_number=page_number,
                                date_explicit=date_explicit,
                            )
                        )

        elif any(keyword in line_clean.lower() for keyword in DEADLINE_KEYWORDS):
            extracted = extract_dates(line_clean, allow_relative=False)
            if extracted:
                for orig_date, iso_date, is_explicit in extracted:
                    if iso_date not in seen_deadlines:
                        seen_deadlines.add(iso_date)
                        clean_desc = extract_task(line_clean)
                        deadlines.append(
                            ExtractedDeadline(
                                deadline_date=iso_date,
                                description=clean_desc if clean_desc else line_clean[:160],
                                confidence=0.80 if is_explicit else 0.55,
                                detection_reason=(
                                    f"Detected {'explicit' if is_explicit else 'parsed'} "
                                    f"deadline date '{orig_date}' with contextual deadline indicator."
                                ),
                                source_snippet=line_clean,
                                page_number=page_number,
                                date_explicit=is_explicit,
                            )
                        )

    for reason, count in skipped.items():
        if count:
            warnings.append(
                f"Skipped {count} sentence(s) classified as {reason} "
                f"(negation/hypothetical/historical/intro filters)."
            )

    if not tasks and not rules and not deadlines:
        warnings.append(
            "No actionable tasks, rules, or deadlines were detected. "
            "The document may be informational only, or wording may not match extraction patterns."
        )

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

    warnings.append(
        "Extraction uses deterministic rule-based analysis (not a large language model). "
        "Review extracted items before relying on them."
    )

    return DocumentAnalysis(
        document_type=document_type,
        summary=summary,
        tasks=tasks,
        rules=rules,
        deadlines=deadlines,
        warnings=warnings,
    )
