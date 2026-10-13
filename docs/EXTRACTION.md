# Document extraction notes

DocuGuard AI uses **deterministic, rule-based** analysis (regex patterns + explicit date parsing). It does **not** call OpenAI or any paid LLM.

## What is extracted

- Actionable obligations (submit, pay, register, attend, …)
- Compliance rules (mandatory / prohibited / recommended)
- Deadlines associated with those actions when an explicit calendar date is nearby

## Evidence fields

Each task may include:

| Field | Meaning |
|-------|---------|
| `source_snippet` | Original sentence from the PDF |
| `page_number` | 1-based page when PDF page markers are available |
| `date_explicit` | True when the date was an explicit calendar date |
| `confidence` | **Heuristic** review score (0–1), **not** a calibrated probability |
| `extraction_method` | Always `rule_based` in this build |
| `review_status` | `pending` / `accepted` / `corrected` / `rejected` |
| `detection_reason` | Human-readable explanation of the match |

## Filters that reduce false positives

Sentences are skipped when classified as:

- Negated (“do not need to submit…”)
- Hypothetical (“if you wish…”, “for example…”)
- Historical (“was paid…”, “have already submitted…”)
- Generic introductory fluff (“dear students…”, “please note…”)

Near-duplicate tasks are collapsed using normalized text.

## Relative dates

Relative phrases (“next Friday”, “in two weeks”) are **not** resolved by default because there is no trustworthy document reference date. Only explicit calendar dates are attached.

## Limitations

- Scanned / image-only PDFs need OCR (not enabled in this build).
- Complex multi-clause sentences may attach only the first matching deadline.
- Keyword/pattern coverage is biased toward institutional notices (exams, fees, placements).
- Precision/recall depend on document wording; review extracted items before relying on them.

## Synthetic corpus coverage (tests)

See `backend/tests/test_extraction.py` for cases covering clear deadlines, multi-deadline wording, negation, hypothetical language, historical dates, duplicates, and empty/no-action documents.
