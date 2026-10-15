from datetime import date, timedelta

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
    assert len(result.tasks) == 2
    assert {task.deadline for task in result.tasks} == {"2026-04-10", "2026-04-12"}
    assert all("2026" not in task.task for task in result.tasks)


def test_wrapped_sentences_keep_page_and_evidence():
    result = analyze_document(
        "--- Page 3 ---\n"
        "Students must submit\n"
        "the examination form by 15 March 2027.\n"
        "This circular describes the timetable."
    )
    assert len(result.tasks) == 1
    assert result.tasks[0].page_number == 3
    assert result.tasks[0].deadline == "2027-03-15"
    assert "submit the examination form" in result.tasks[0].source_snippet.lower()


def test_wrapped_year_does_not_split_placement_registration_sentence():
    result = analyze_document(
        "--- Page 1 ---\n"
        "Students who wish to participate in campus placements must register "
        "on the placement portal by 12 October\n"
        "2026. Students must upload the updated resume."
    )

    registration = next(task for task in result.tasks if "register" in task.task.lower())
    assert registration.deadline == "2026-10-12"
    assert "by 12 October 2026" in registration.source_snippet


def test_on_dates_are_associated_only_with_their_action_sentence():
    result = analyze_document(
        "All registered students must attend the placement orientation "
        "session on 16 October 2026 at 10:00 AM. "
        "Students must upload their final resume no later than 14 October 2026. "
        "Registered students must appear for the aptitude test on 20 October 2026. "
        "The career fair will be held on 25 October 2026."
    )

    orientation = next(task for task in result.tasks if "orientation" in task.task.lower())
    resume = next(task for task in result.tasks if "final resume" in task.task.lower())
    aptitude_test = next(task for task in result.tasks if "aptitude test" in task.task.lower())
    assert (orientation.deadline, orientation.deadline_time) == ("2026-10-16", "10:00")
    assert resume.deadline == "2026-10-14"
    assert aptitude_test.deadline == "2026-10-20"


def test_internship_documents_keep_action_context_and_deadline():
    result = analyze_document(
        "Students who have completed an internship must submit their internship "
        "completion certificate and internship report by 18 October 2026."
    )

    internship_task = next(task for task in result.tasks if "internship" in task.task.lower())
    assert internship_task.deadline == "2026-10-18"
    assert "completion certificate" in internship_task.task.lower()
    assert "internship report" in internship_task.task.lower()
    assert "heuristic" in internship_task.detection_reason.lower()


def test_notice_deadlines_do_not_duplicate_task_deadlines():
    result = analyze_document(
        "Important Deadlines Activity Deadline Placement Registration 12 October 2026 "
        "Resume Submission 14 October 2026 Internship Documents 18 October 2026 "
        "Placement Orientation 16 October 2026 at 10:00 AM Aptitude Test "
        "20 October 2026 Training & Placement Cell Student Career Center. "
        "Overall notice deadline: 6 October 2026. "
        "Students must register on the placement portal by 12 October 2026. "
        "Students must upload their final resume no later than 14 October 2026. "
        "Students must attend placement orientation on 16 October 2026 at 10:00 AM. "
        "Students must submit internship completion certificate and internship "
        "report by 18 October 2026. "
        "Students must appear for the aptitude test on 20 October 2026."
    )

    task_deadlines = {
        task.task: (task.deadline, task.deadline_time)
        for task in result.tasks
    }
    assert any("register" in title.lower() and value[0] == "2026-10-12" for title, value in task_deadlines.items())
    assert any("resume" in title.lower() and value[0] == "2026-10-14" for title, value in task_deadlines.items())
    assert any(
        "orientation" in title.lower() and value == ("2026-10-16", "10:00")
        for title, value in task_deadlines.items()
    )
    assert any("internship" in title.lower() and value[0] == "2026-10-18" for title, value in task_deadlines.items())
    assert any("aptitude" in title.lower() and value[0] == "2026-10-20" for title, value in task_deadlines.items())

    deadlines_by_date = {deadline.deadline_date: deadline for deadline in result.deadlines}
    assert len(result.deadlines) == 6
    assert deadlines_by_date["2026-10-12"].description == "Register on the placement portal"
    assert deadlines_by_date["2026-10-14"].description == "Upload their final resume"
    assert deadlines_by_date["2026-10-16"].description == "Attend placement orientation"
    assert deadlines_by_date["2026-10-18"].description.startswith("Submit internship")
    assert deadlines_by_date["2026-10-20"].description == "Appear for the aptitude test"
    assert deadlines_by_date["2026-10-06"].description == "Overall notice deadline"


def test_long_standalone_deadline_uses_a_concise_title():
    result = analyze_document(
        "Important Deadlines Activity Deadline Placement Registration Resume "
        "Submission Internship Documents Placement Orientation Aptitude Test "
        "Training & Placement Cell Student Career Center; the overall notice "
        "deadline is 6 October 2026."
    )

    notice_deadline = next(d for d in result.deadlines if d.deadline_date == "2026-10-06")
    assert notice_deadline.description == "Overall notice deadline"


def test_issue_date_is_not_linked_to_generic_deadline_language():
    result = analyze_document(
        "Training & Placement Cell - Issued: 6 October 2026\n"
        "All final-year students are required to complete the following "
        "activities within the specified deadlines.\n"
        "Students must register on the placement portal by 12 October 2026."
    )

    assert all("following activities" not in task.task.lower() for task in result.tasks)
    registration = next(task for task in result.tasks if "register" in task.task.lower())
    assert registration.deadline == "2026-10-12"
    assert all(deadline.deadline_date != "2026-10-06" for deadline in result.deadlines)


def test_unlinked_event_date_is_not_created_as_a_standalone_deadline():
    result = analyze_document("The career fair will be held on 25 October 2026.")

    assert result.tasks == []
    assert result.deadlines == []


def test_equivalent_rules_are_deduplicated_but_distinct_types_are_preserved():
    result = analyze_document(
        "Students must comply with placement policy. "
        "All students are required to comply with the placement policy! "
        "Students must not share placement portal credentials."
    )

    assert len([rule for rule in result.rules if rule.rule_type == "MANDATORY"]) == 1
    assert len([rule for rule in result.rules if rule.rule_type == "PROHIBITED"]) == 1


def test_sentence_fragments_and_keyword_mentions_are_not_tasks():
    result = analyze_document(
        "Students must submit.\n"
        "The report describes the schedule and registration process."
    )
    assert result.tasks == []


def test_compliance_prohibitions_are_rules_not_tasks():
    for statement in (
        "Students must not submit forged documents.",
        "Students mustn't submit forged documents.",
        "Sharing passwords is prohibited.",
        "Phones are not allowed during the examination.",
        "Students should not submit forged documents.",
    ):
        result = analyze_document(statement)
        assert result.tasks == []
        assert len(result.rules) == 1
        assert result.rules[0].rule_type == "PROHIBITED"
        assert result.rules[0].source_snippet == statement


def test_no_obligation_is_not_misclassified_as_a_prohibition():
    result = analyze_document("Students do not need to submit the form again.")
    assert result.tasks == []
    assert result.rules == []

    inability = analyze_document("Students cannot upload the form with this portal.")
    assert inability.tasks == []
    assert inability.rules == []


def test_unrelated_later_date_is_not_attached_to_task():
    result = analyze_document(
        "Students must submit the examination form by 15 March 2027. "
        "The examination will take place on 20 March 2027."
    )
    assert len(result.tasks) == 1
    assert result.tasks[0].deadline == "2027-03-15"
    assert all(deadline.deadline_date != "2027-03-20" for deadline in result.deadlines)


def test_deadline_in_surrounding_prose_is_linked_to_the_task():
    result = analyze_document(
        "Students must submit the placement form; the deadline for this form "
        "is 15 March 2027."
    )

    assert len(result.tasks) == 1
    assert result.tasks[0].deadline == "2027-03-15"


def test_explicit_date_time_is_extracted_and_removed_from_title():
    result = analyze_document(
        "Students must submit the examination form by 15 March 2027 at 5:30 PM."
    )
    task = result.tasks[0]
    assert task.deadline == "2027-03-15"
    assert task.deadline_time == "17:30"
    assert "2027" not in task.task
    assert "5:30 PM" not in task.task
    assert not task.task.lower().endswith(" by")


def test_invalid_and_ambiguous_dates_remain_unresolved():
    invalid = analyze_document(
        "Students must submit the examination form by 31 February 2027."
    )
    ambiguous = analyze_document(
        "Students must submit the examination form by 03/04/2027."
    )
    assert invalid.tasks[0].deadline == ""
    assert ambiguous.tasks[0].deadline == ""
    assert any("Invalid calendar date" in warning for warning in invalid.warnings)
    assert any("Ambiguous date" in warning for warning in ambiguous.warnings)


def test_task_without_deadline_remains_undated():
    result = analyze_document("Students must submit the examination form.")
    assert len(result.tasks) == 1
    assert result.tasks[0].deadline == ""
    assert result.tasks[0].deadline_time == ""


def test_date_without_year_remains_unresolved():
    result = analyze_document("Students must submit the examination form by 15 March.")

    assert len(result.tasks) == 1
    assert result.tasks[0].deadline == ""
    assert result.tasks[0].deadline_time == ""


def test_duplicate_extraction_keeps_one_equivalent_obligation():
    result = analyze_document(
        "Students must register for the course by 01 May 2027. "
        "Students must register for the course by 01 May 2027."
    )
    assert len(result.tasks) == 1


def test_similar_tasks_with_different_objects_and_same_date_are_preserved():
    result = analyze_document(
        "Students must submit the internship certificate by 18 October 2026. "
        "Students must submit the internship report by 18 October 2026."
    )

    assert len(result.tasks) == 2
    assert {task.deadline for task in result.tasks} == {"2026-10-18"}
    assert len(result.deadlines) == 2
    assert {deadline.description for deadline in result.deadlines} == {
        task.task for task in result.tasks
    }


def test_deduplication_ignores_subject_and_articles():
    result = analyze_document(
        "Students must register for the course. Register for course."
    )
    assert len(result.tasks) == 1


def test_priority_and_confidence_are_heuristic_not_keyword_driven_high():
    later_date = (date.today() + timedelta(days=30)).strftime("%d %B %Y")
    soon_date = (date.today() + timedelta(days=3)).strftime("%d %B %Y")
    regular = analyze_document(
        f"Students must submit the examination form by {later_date}."
    ).tasks[0]
    urgent = analyze_document(
        f"Students must urgently submit the examination form by {soon_date}."
    ).tasks[0]
    assert regular.priority == "MEDIUM"
    assert urgent.priority == "HIGH"
    assert 0 < regular.confidence < 0.9
    generic = analyze_document("Submit the form.").tasks[0]
    assert regular.confidence > generic.confidence
    assert "heuristic" in regular.detection_reason.lower()
    assert "probability" not in regular.detection_reason.lower()
