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
    r"\bdon['’]t (?:need to|have to|submit|apply|pay|register|attend)\b",
    r"\bdo not (?:need to|have to|submit|apply|pay|register|attend)\b",
    r"\b(?:mustn['’]t|shouldn['’]t|should not)\b",
    r"\b(?:cannot|can['’]t)\b",
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
    """Return sentence-like units with their source page number."""
    current_page: Optional[int] = None
    results: List[Tuple[Optional[int], str]] = []
    page_lines: List[str] = []

    def flush_page() -> None:
        if not page_lines:
            return
        paragraph = " ".join(line.strip() for line in page_lines if line.strip())
        protected = re.sub(
            r"\b(?:e\.g|i\.e|Mr|Mrs|Ms|Dr|Prof)\.",
            lambda match: match.group().replace(".", "<DOT>"),
            paragraph,
            flags=re.IGNORECASE,
        )
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'(])", protected):
            sentence = sentence.replace("<DOT>", ".").strip()
            if sentence:
                results.append((current_page, sentence))
        page_lines.clear()

    for raw in text.split("\n"):
        line = raw.strip()
        marker = PAGE_MARKER_RE.match(line)
        if marker:
            flush_page()
            current_page = int(marker.group(1))
        elif re.match(
            r"^(?:[•\-*]\s+|(?!\d{4}\.\s)\d+[\).]\s+)",
            line,
        ):
            flush_page()
            page_lines.append(line)
        elif line:
            page_lines.append(line)
        elif page_lines:
            flush_page()
    flush_page()
    return results


def _is_valid_calendar_date(year: int, month: int, day: int) -> bool:
    if month < 1 or month > 12 or day < 1 or day > 31:
        return False
    try:
        return day <= calendar.monthrange(year, month)[1]
    except ValueError:
        return False


def _explicit_date_pattern() -> re.Pattern:
    month = (
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    )
    return re.compile(
        rf"\b(?:"
        rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{month})\s*,?\s*\d{{4}}"
        rf"|(?:{month})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}"
        rf"|\d{{4}}-\d{{2}}-\d{{2}}"
        rf"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{4}}"
        rf")\b",
        flags=re.IGNORECASE,
    )


def _explicit_time_pattern() -> re.Pattern:
    return re.compile(
        r"(?<!\d)(\d{1,2})(?::([0-5]\d))?\s*"
        r"(a\.?m\.?|p\.?m\.?)\b|(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)",
        flags=re.IGNORECASE,
    )


def _normalize_explicit_time(text: str) -> Optional[str]:
    match = _explicit_time_pattern().fullmatch(text.strip())
    if not match:
        return None
    if match.group(4) is not None:
        hour, minute = int(match.group(4)), int(match.group(5))
    else:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3).lower().replace(".", "")
        if hour < 1 or hour > 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    return f"{hour:02d}:{minute:02d}"


def _time_near_date(text: str, start: int, end: int) -> str:
    pattern = _explicit_time_pattern()
    nearby = [
        (match, end + match.start())
        for match in pattern.finditer(text[end : end + 20])
    ]
    nearby.extend(
        (match, start - (len(text[:start]) - match.start()))
        for match in pattern.finditer(text[max(0, start - 20) : start])
    )
    if not nearby:
        return ""
    match, _ = min(nearby, key=lambda candidate: abs(candidate[1] - end))
    return _normalize_explicit_time(match.group()) or ""


def _extract_date_details(text: str) -> List[Tuple[str, str, bool, str]]:
    results = []
    seen = set()
    for match in _explicit_date_pattern().finditer(text):
        original = match.group().strip()
        normalized = _normalize_explicit_date(original)
        if not normalized:
            continue
        time = _time_near_date(text, match.start(), match.end())
        key = (normalized, time)
        if key not in seen:
            seen.add(key)
            results.append((original, normalized, True, time))
    return results


def extract_dates(text: str, allow_relative: bool = False) -> List[Tuple[str, str, bool]]:
    """
    Returns list of (original_text, YYYY-MM-DD, is_explicit).
    Relative dates are only resolved when allow_relative=True AND a trustworthy
    reference context is provided by the caller (currently unused / off by default).
    """
    results: List[Tuple[str, str, bool]] = []
    seen_iso = set()

    for original, iso, is_explicit, _ in _extract_date_details(text):
        if iso not in seen_iso:
            seen_iso.add(iso)
            results.append((original, iso, is_explicit))

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
        if a <= 12 and b <= 12 and a != b:
            return None
        if a > 12:
            d, m = a, b
        elif b > 12:
            m, d = a, b
        else:
            d, m = a, b
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
    details = find_deadline_details(text)
    if details:
        return details[0], details[1]
    return "", False


def find_deadline_details(text: str) -> Tuple[str, bool, str]:
    """Return a validated date and time only when the text explicitly links them."""
    date_pattern = _explicit_date_pattern()
    date_matches = list(date_pattern.finditer(text))
    candidates = _extract_date_details(text)
    if len(date_matches) != 1 or len(candidates) != 1:
        return "", False, ""

    date_match = date_matches[0]
    has_explicit_link = bool(
        re.search(
            rf"\b(?:no later than|on or before|by|before|on)\s+{date_pattern.pattern}",
            text[: date_match.end()],
            re.IGNORECASE,
        )
    )
    has_deadline_label = _has_deadline_label_before_date(text, date_pattern)
    if not (has_explicit_link or has_deadline_label):
        return "", False, ""

    _, deadline, explicit, deadline_time = candidates[0]
    return deadline, explicit, deadline_time


def _has_deadline_label_before_date(text: str, date_pattern: re.Pattern) -> bool:
    keywords = "|".join(re.escape(keyword) for keyword in DEADLINE_KEYWORDS)
    return bool(
        re.search(
            rf"\b(?:{keywords})\b[^.!?]{{0,80}}{date_pattern.pattern}",
            text,
            re.IGNORECASE,
        )
    )


def has_ambiguous_calendar_date(text: str) -> bool:
    """Recognize slash dates whose day/month ordering cannot be inferred safely."""
    for match in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text):
        first, second = int(match.group(1)), int(match.group(2))
        if first <= 12 and second <= 12 and first != second:
            return True
    return False


def is_actionable(sentence: str) -> bool:
    if any(re.search(pattern, sentence, re.IGNORECASE) for pattern in PROHIBITED_PATTERNS):
        return False

    if re.search(r"\bcomplete the following activities\b", sentence, re.IGNORECASE):
        return False

    lower = sentence.lower()
    for pattern in ACTION_PATTERNS:
        match = re.search(pattern, lower)
        if not match:
            continue

        prefix = lower[: match.start()]
        directive = bool(
            re.search(
                r"\b(?:must|shall|should|need to|are required to|is required to|"
                r"have to|will|please|requested to)"
                r"(?:\s+(?:urgently|immediately|promptly|quickly))?\s*$",
                prefix,
            )
        )
        imperative = not prefix.strip(" \t,;:") and match.start() <= 2
        subject_action = bool(
            re.search(r"\b(?:students?|applicants?|employees?|you)\s+$", prefix)
        )
        if not (directive or imperative or subject_action):
            continue

        remainder = sentence[match.end() :]
        remainder = _explicit_date_pattern().sub(" ", remainder)
        remainder = _explicit_time_pattern().sub(" ", remainder)
        remainder = re.sub(
            r"\b(?:by|before|on|at|due|deadline|date|last|no later than|"
            r"or before|and|then)\b",
            " ",
            remainder,
            flags=re.IGNORECASE,
        )
        object_words = [
            word
            for word in re.findall(r"[A-Za-z][A-Za-z'-]*", remainder)
            if word.lower() not in {"a", "an", "the", "to", "for"}
        ]
        if object_words:
            return True
    return False


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
    if is_no_obligation(sentence):
        return "negated"
    if any(re.search(p, lower) for p in NEGATION_PATTERNS):
        return "negated"
    if any(re.search(p, lower) for p in HYPOTHETICAL_PATTERNS):
        return "hypothetical"
    if any(re.search(p, lower) for p in HISTORICAL_PATTERNS) and not is_actionable(sentence):
        return "historical"
    return None


def is_no_obligation(sentence: str) -> bool:
    return bool(
        re.search(
            r"\b(?:do not need to|do not have to|don['’]t need to|"
            r"don['’]t have to|need not|not required to|"
            r"no need to|not necessary to|exempt(?:ed)? from)\b",
            sentence,
            re.IGNORECASE,
        )
    )


PROHIBITED_PATTERNS = [
    r"\bmust not\b",
    r"\bmustn['’]t\b",
    r"\bshall not\b",
    r"\bprohibited\b",
    r"\bstrictly forbidden\b",
    r"\bnot allowed\b",
    r"\bdo not\b",
    r"\bdon['’]t\b",
    r"\bshould not\b",
    r"\bshouldn['’]t\b",
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
    if is_no_obligation(sentence):
        return None
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
    sentence = _explicit_date_pattern().sub("", sentence)
    sentence = _explicit_time_pattern().sub("", sentence)
    sentence = re.sub(
        r"\b(?:deadline|last date|due date|submission date)\b\s*[:\-]?\s*$",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    sentence = sentence.strip(" .,:;-")
    sentence = re.sub(
        r"(?:\s+\b(?:by|before|on|at|no later than|on or before)\b)+\s*$",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    sentence = re.sub(r"\s+", " ", sentence)
    sentence = sentence.strip(" .:-")
    action_words = "|".join(pattern[2:-2] for pattern in ACTION_PATTERNS)
    sentence = re.sub(
        rf"^(?:all\s+)?(?:students?|applicants?|employees?|you)\s+"
        rf"(?:(?:must|shall|should|need to|have to|are required to|will)\s+)?"
        rf"(?=(?:{action_words})\b)",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    if sentence:
        sentence = sentence[0].upper() + sentence[1:]
    sentence = sentence.strip(" .:-")
    if len(sentence) > 180:
        sentence = sentence[:177] + "..."
    return sentence


def split_action_clauses(sentence: str) -> List[str]:
    actions = "|".join(
        pattern[2:-2]
        for pattern in ACTION_PATTERNS
    )
    boundary = re.compile(
        rf"(?:\s+(?:and|then)\s+|\s*;\s*)(?=(?:(?:students?|applicants?|you)\s+)?"
        rf"(?:(?:must|shall|should|please|need to)\s+)?"
        rf"(?:(?:urgently|immediately|promptly|quickly)\s+)?(?:{actions})\b)",
        flags=re.IGNORECASE,
    )
    clauses = [part.strip(" ,;") for part in boundary.split(sentence) if part.strip(" ,;")]
    return clauses or [sentence]


def detect_priority(sentence: str, deadline: str, deadline_time: str = "") -> str:
    lower = sentence.lower()
    if re.search(r"\b(?:urgent|immediately|as soon as possible|today|tomorrow)\b", lower):
        return "HIGH"
    if deadline:
        try:
            days_remaining = (datetime.strptime(deadline, "%Y-%m-%d").date() - datetime.now().date()).days
        except ValueError:
            days_remaining = None
        if days_remaining is not None and days_remaining <= 7:
            return "HIGH"

    medium_words = [
        "mandatory", "compulsory", "must", "required", "important",
        "recommended", "please", "verify", "complete", "register",
        "apply", "upload", "pay", "submit", "deadline", "due",
    ]
    if deadline or deadline_time:
        return "MEDIUM"
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
    score = 0.35
    if is_actionable(sentence):
        score += 0.15
    if deadline and date_explicit:
        score += 0.12
    elif deadline:
        score += 0.05
    if detect_category(sentence) != "General":
        score += 0.08
    if len(sentence) >= 60:
        score += 0.05
    elif len(sentence) >= 25:
        score += 0.03
    if re.search(r"\b(?:must|shall|should|required to|please)\b", sentence, re.IGNORECASE):
        score += 0.07
    if should_skip_sentence(sentence):
        score -= 0.20
    return max(0.05, min(round(score, 2), 0.85))


def _normalize_for_dedupe(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = re.sub(r"\s+", " ", text).strip().split()
    ignored = {
        "a", "an", "the", "all", "students", "student", "applicant",
        "applicants", "employee", "employees", "must", "shall", "should",
        "please", "need", "to", "will",
    }
    normalized = [token for token in tokens if token not in ignored]
    normalized = [
        {"registration": "register", "submission": "submit"}.get(token, token)
        for token in normalized
    ]
    return " ".join(normalized)


def _normalize_rule_for_dedupe(text: str) -> str:
    text = re.sub(
        r"^\s*(?:(?:all\s+)?(?:students?|applicants?|employees?|you)\s+)?"
        r"(?:(?:must|shall|should|are required to|is required to|need to|have to)\s+)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _normalize_for_dedupe(text)


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
    standalone_deadlines: List[ExtractedDeadline] = []
    seen_standalone_deadline_dates = set()
    seen_date_warnings = set()
    skipped = {"negated": 0, "hypothetical": 0, "historical": 0, "introductory": 0}

    for page_number, sentence in page_lines:
        if len(sentence) < 8:
            continue

        for match in _explicit_date_pattern().finditer(sentence):
            original_date = match.group().strip()
            if _normalize_explicit_date(original_date):
                continue
            if has_ambiguous_calendar_date(original_date):
                message = f"Ambiguous date '{original_date}' was left unresolved."
            else:
                message = f"Invalid calendar date '{original_date}' was left unresolved."
            if message not in seen_date_warnings:
                seen_date_warnings.add(message)
                warnings.append(message)

        skip_reason = should_skip_sentence(sentence)

        # Preserve compliance prohibitions as rules rather than completion tasks.
        rule_info = detect_rule(sentence)
        if rule_info and skip_reason not in {"historical", "introductory", "too_short"}:
            rule_type, trigger_keyword, rule_full_text = rule_info
            rule_summary = re.sub(r"^[\s•\-*]+", "", rule_full_text)
            rule_summary = re.sub(r"^\d+[\).\s]+", "", rule_summary).strip()
            rule_key = (rule_type, _normalize_rule_for_dedupe(rule_summary))
            if rule_key not in seen_rules and len(rule_summary.split()) >= 3:
                seen_rules.add(rule_key)
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
                        category=detect_category(sentence),
                        confidence=confidence,
                        detection_reason=reason,
                        source_snippet=sentence,
                        page_number=page_number,
                    )
                )

        if skip_reason:
            if skip_reason in skipped:
                skipped[skip_reason] += 1
            continue

        found_actionable_task = False
        for clause in split_action_clauses(sentence):
            if not is_actionable(clause):
                continue
            task_text = extract_task(clause)
            if not task_text or len(task_text.split()) < 2:
                continue

            found_actionable_task = True
            deadline, date_explicit, deadline_time = find_deadline_details(clause)
            normalized = _normalize_for_dedupe(task_text)
            task_key = (normalized, deadline, deadline_time)
            if task_key in seen_tasks:
                continue
            seen_tasks.add(task_key)

            priority = detect_priority(clause, deadline, deadline_time)
            category = detect_category(clause)
            confidence = calculate_confidence(clause, deadline, date_explicit)
            action_verb = get_action_keyword(clause)

            reason_parts = [f"Detected actionable action verb '{action_verb}'"]
            if deadline:
                reason_parts.append(f"with explicit deadline '{deadline}'")
            elif has_ambiguous_calendar_date(clause):
                reason_parts.append("with an unresolved ambiguous calendar date")
            if deadline_time:
                reason_parts.append(f"at {deadline_time}")
            if category != "General":
                reason_parts.append(f"in category '{category}'")
            reason = (
                "Detected as an actionable task because the sentence contains "
                + ", ".join(reason_parts)
                + ". Confidence is a heuristic review score, not a calibrated estimate."
            )

            tasks.append(
                ExtractedTask(
                    task=task_text,
                    description="",
                    deadline=deadline,
                    deadline_time=deadline_time,
                    priority=priority,
                    category=category,
                    confidence=confidence,
                    detection_reason=reason,
                    source_snippet=sentence,
                    page_number=page_number,
                    date_explicit=date_explicit,
                    review_status="pending",
                    extraction_method="rule_based",
                )
            )

            if deadline:
                deadline_key = (deadline, deadline_time, normalized)
                if deadline_key not in seen_deadlines:
                    seen_deadlines.add(deadline_key)
                    deadlines.append(
                        ExtractedDeadline(
                            deadline_date=deadline,
                            deadline_time=deadline_time,
                            description=task_text,
                            confidence=confidence,
                            detection_reason=f"Detected explicit deadline tied to actionable task '{task_text}'.",
                            source_snippet=sentence,
                            page_number=page_number,
                            date_explicit=date_explicit,
                        )
                    )

        standalone_date, standalone_explicit, standalone_time = (
            find_deadline_details(sentence)
            if not found_actionable_task
            else ("", False, "")
        )
        if standalone_date and _has_deadline_label_before_date(
            sentence, _explicit_date_pattern()
        ):
            for orig_date, iso_date, is_explicit, deadline_time in _extract_date_details(sentence):
                if iso_date != standalone_date:
                    continue
                if iso_date in seen_standalone_deadline_dates:
                    continue
                seen_standalone_deadline_dates.add(iso_date)
                clean_desc = extract_task(sentence)
                if len(clean_desc) > 100:
                    clean_desc = "Overall notice deadline"
                else:
                    clean_desc = re.sub(
                        r"\s+(?:is|are|was|were)\s*$",
                        "",
                        clean_desc,
                        flags=re.IGNORECASE,
                    ).strip()
                standalone_deadlines.append(
                    ExtractedDeadline(
                        deadline_date=iso_date,
                        deadline_time=standalone_time or deadline_time,
                        description=clean_desc or "Notice deadline",
                        confidence=0.75 if standalone_explicit else 0.55,
                        detection_reason=(
                            f"Detected explicit deadline date '{orig_date}' "
                            "with contextual deadline indicator."
                        ),
                        source_snippet=sentence,
                        page_number=page_number,
                        date_explicit=standalone_explicit,
                    )
                )

    task_deadline_dates = {task.deadline for task in tasks if task.deadline}
    deadlines.extend(
        deadline
        for deadline in standalone_deadlines
        if deadline.deadline_date not in task_deadline_dates
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
