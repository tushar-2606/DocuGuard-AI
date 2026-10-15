# Document extraction notes

DocuGuard AI uses **deterministic, rule-based** analysis (regex patterns + explicit date parsing). It does **not** call OpenAI or any paid LLM.

## What is extracted

- Actionable obligations (submit, pay, register, attend, …)
- Compliance rules (mandatory / prohibited / recommended)
- Deadlines associated with those actions when an explicit, validated calendar date is linked to the action
- Explicit local times when a time appears next to an extracted calendar date

## Evidence fields

Each task may include:

| Field | Meaning |
|-------|---------|
| `source_snippet` | Original sentence from the PDF |
| `page_number` | 1-based page when PDF page markers are available |
| `date_explicit` | True when the date was an explicit calendar date |
| `deadline_time` | Explicit local time in `HH:MM` 24-hour format; empty when absent |
| `confidence` | **Heuristic** review score (0–1), **not** a calibrated probability |
| `extraction_method` | Always `rule_based` in this build |
| `review_status` | `pending` / `accepted` / `corrected` / `rejected` |
| `detection_reason` | Human-readable explanation of the match |

## Filters that reduce false positives

Sentences are skipped when classified as:

- No-obligation wording (“do not need to submit…”)
- Hypothetical (“if you wish…”, “for example…”)
- Historical (“was paid…”, “have already submitted…”)
- Generic introductory fluff (“dear students…”, “please note…”)

Near-duplicate tasks are collapsed using normalized text.
Prohibitions such as “must not submit” are retained as `PROHIBITED` rules and are
not converted into completion tasks. A no-obligation statement such as “do not
need to submit” is not treated as a prohibition.

## Relative dates

Relative phrases (“next Friday”, “in two weeks”) are **not** resolved by default because there is no trustworthy document reference date. Only explicit calendar dates are attached.
Ambiguous slash dates (for example, `03/04/2027`) and invalid calendar dates
remain unresolved and are disclosed in the analysis warnings. Times are stored
separately from the existing `YYYY-MM-DD` deadline field.

## Task CSV format

The task export keeps `deadline` as ISO `YYYY-MM-DD` and includes
`deadline_time` as local 24-hour `HH:MM`; either field is empty when the source
does not provide it. Fields containing commas, quotes, or line breaks use
standard CSV quoting. Each saved document upload remains represented, so
re-uploading the same PDF can produce repeated task rows across documents;
extraction deduplication applies within each analysis only.

## Limitations

- Scanned / image-only PDFs need OCR (not enabled in this build).
- Multi-action sentences are split at recognized action conjunctions so each
  action can retain its own nearby deadline. Complex or ambiguous date/action
  relationships are left unresolved rather than guessed.
- Keyword/pattern coverage is biased toward institutional notices (exams, fees, placements).
- Precision/recall depend on document wording; review extracted items before relying on them.

## Synthetic corpus coverage (tests)

See `backend/tests/test_extraction.py` for sentence fragments, compliance
prohibitions, negation, historical/hypothetical statements, per-action and
multiple deadlines, times, invalid/ambiguous dates, duplicate extraction,
priority heuristics, and no-deadline cases. Repeated PDF uploads remain
separate user documents; duplicate task text is collapsed only within each
document analysis.
