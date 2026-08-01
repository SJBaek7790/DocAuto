from datetime import datetime
from common import KST
from seminar_survey import evaluate_survey_cutoff, get_survey_cutoff, run_survey, mark_survey_status


def test_evaluate_survey_cutoff_before_deadline():
    item = {
        "id": 5473,
        "title": "Breathe Well Symposium (호흡기)",
        "start": "2026-08-10(월) 13:00 ~ 14:00",
        "entered_at": "2026-08-10T13:05:00+09:00",
    }
    # Deadline is 14:00 + 1h30m = 15:30 KST
    now_kst = datetime(2026, 8, 10, 14, 30, tzinfo=KST)
    res = evaluate_survey_cutoff(item, now_kst)
    assert res == "not_ready"


def test_evaluate_survey_cutoff_after_deadline():
    item = {
        "id": 5473,
        "title": "Breathe Well Symposium (호흡기)",
        "start": "2026-08-10(월) 13:00 ~ 14:00",
        "entered_at": "2026-08-10T13:05:00+09:00",
    }
    # 16:00 KST > 15:30 KST cutoff
    now_kst = datetime(2026, 8, 10, 16, 0, tzinfo=KST)
    res = evaluate_survey_cutoff(item, now_kst)
    assert res == "closed"


def test_get_survey_cutoff_start_end():
    item = {
        "start": "2026-08-10(월) 13:00 ~ 14:00",
    }
    cutoff = get_survey_cutoff(item)
    assert cutoff == datetime(2026, 8, 10, 15, 30, tzinfo=KST)


def test_fallback_cutoff_start_only():
    item = {
        "start": "2026-08-10(월) 13:00",
    }
    # start + 3h = 16:00 KST
    cutoff = get_survey_cutoff(item)
    assert cutoff == datetime(2026, 8, 10, 16, 0, tzinfo=KST)

    before_now = datetime(2026, 8, 10, 15, 0, tzinfo=KST)
    after_now = datetime(2026, 8, 10, 16, 30, tzinfo=KST)
    assert evaluate_survey_cutoff(item, before_now) == "not_ready"
    assert evaluate_survey_cutoff(item, after_now) == "closed"


def test_fallback_cutoff_entered_at_only():
    item = {
        "entered_at": "2026-08-10T13:00:00+09:00",
    }
    # entered_at + 3h = 16:00 KST
    cutoff = get_survey_cutoff(item)
    assert cutoff == datetime(2026, 8, 10, 16, 0, tzinfo=KST)

    before_now = datetime(2026, 8, 10, 15, 0, tzinfo=KST)
    after_now = datetime(2026, 8, 10, 16, 30, tzinfo=KST)
    assert evaluate_survey_cutoff(item, before_now) == "not_ready"
    assert evaluate_survey_cutoff(item, after_now) == "closed"


def test_naive_datetime_conversion():
    item = {
        "start": "2026-08-10(월) 13:00 ~ 14:00",
    }
    # Cutoff: 15:30 KST
    # Pass naive datetime (no tzinfo)
    naive_before = datetime(2026, 8, 10, 14, 30)
    naive_after = datetime(2026, 8, 10, 16, 0)

    assert evaluate_survey_cutoff(item, naive_before) == "not_ready"
    assert evaluate_survey_cutoff(item, naive_after) == "closed"


def test_incomplete_bank_message_includes_title(tmp_path, monkeypatch):
    from seminar_survey import resolve_page, add_missing_to_bank

    bank_file = tmp_path / "survey_answers.json"

    # Simulate missing survey answer
    questions = [
        {
            "question": "[퀴즈] 새로운 문항",
            "kind": "choice",
            "name": "q1",
            "options": [{"text": "보기1"}, {"text": "보기2"}],
        }
    ]
    plan, missing = resolve_page(questions, {})
    assert len(missing) == 1

    item = {
        "id": 5473,
        "title": "Breathe Well Symposium (호흡기)",
        "start": "2026-08-10(월) 13:00 ~ 14:00",
    }

    added = add_missing_to_bank(bank_file, missing)
    pages_done = 0
    prefix = f"[{item['title']}] " if item.get("title") else ""
    msg = (
        f"{prefix}{pages_done + 1}페이지에 미등록 문항 {len(missing)}건 — 제출하지 않음"
        f"(survey_answers.json에 {added}건 빈 값 추가)."
    )
    assert "Breathe Well Symposium (호흡기)" in msg


def test_mark_survey_status_closed():
    state = {
        "version": 2,
        "accounts": {
            "bjh7790": {
                "entered": [{"id": 5473, "title": "Test"}],
                "survey": {}
            }
        }
    }
    mark_survey_status(state, "bjh7790", 5473, "closed")
    assert state["accounts"]["bjh7790"]["survey"]["5473"] == "closed"
