from app.services.ai_service import analyze_document


CLEAR_DEADLINE = """
--- Page 1 ---
Students must submit the examination form by 15 March 2026.
The last date for fee payment is 20 March 2026.
"""

MULTI_DEADLINE = """
--- Page 1 ---
Submit hall ticket request by 10 April 2026 and pay the exam fee by 12 April 2026.
"""

NEGATED = """
--- Page 1 ---
Students do not need to submit the form again.
There is no need to pay additional fees.
"""

HYPOTHETICAL = """
--- Page 1 ---
If you wish to apply for the scholarship, you could submit documents.
For example, students might need to upload transcripts.
"""

HISTORICAL = """
--- Page 1 ---
The fee was paid on 15 January 2025.
Students have already submitted their forms previously.
"""

NO_ACTION = """
--- Page 1 ---
This circular informs students about the library renovation schedule.
The library will remain closed on weekends for maintenance.
"""

REPEATED = """
--- Page 1 ---
Students must register for the course by 01 May 2026.
Students must register for the course by 01 May 2026.
"""


def test_clear_deadlines_extracted():
    result = analyze_document(CLEAR_DEADLINE)
    assert len(result.tasks) >= 1
    deadlines = {t.deadline for t in result.tasks if t.deadline}
    assert "2026-03-15" in deadlines or any(d.deadline_date == "2026-03-15" for d in result.deadlines)
    assert all(t.source_snippet for t in result.tasks)
    assert all(t.extraction_method == "rule_based" for t in result.tasks)


def test_page_numbers_preserved():
    result = analyze_document(CLEAR_DEADLINE)
    assert any(t.page_number == 1 for t in result.tasks)


def test_negated_instructions_skipped():
    result = analyze_document(NEGATED)
    assert result.tasks == []
    assert any("negated" in w.lower() for w in result.warnings)


def test_hypothetical_skipped():
    result = analyze_document(HYPOTHETICAL)
    assert result.tasks == []


def test_historical_skipped():
    result = analyze_document(HISTORICAL)
    assert result.tasks == []


def test_no_actionable_content():
    result = analyze_document(NO_ACTION)
    assert result.tasks == []
    assert result.deadlines == []


def test_deduplicates_repeated_obligations():
    result = analyze_document(REPEATED)
    assert len(result.tasks) == 1


def test_warnings_disclose_rule_based():
    result = analyze_document(CLEAR_DEADLINE)
    assert any("rule-based" in w.lower() or "not a large language model" in w.lower() for w in result.warnings)


def test_multi_deadline_paragraph():
    result = analyze_document(MULTI_DEADLINE)
    # At least one actionable task; may attach one deadline from the sentence
    assert len(result.tasks) >= 1
    assert any(t.deadline for t in result.tasks) or len(result.deadlines) >= 1
