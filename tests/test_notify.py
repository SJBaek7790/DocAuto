import pytest
from notify import SEVERITY, SEVERITY_ORDER, severity_of, should_send, build_message, send_telegram


def test_severity_mapping():
    assert severity_of({"status": "success", "verified_by": "modal"}) == "ok"
    assert severity_of({"status": "success"}) == "alert"  # missing verified_by -> unverified -> alert
    assert severity_of({"status": "already_done"}) == "quiet"
    assert severity_of({"status": "no_answer"}) == "action"
    assert severity_of({"status": "failed"}) == "alert"


def test_nested_hmp_and_list_severity():
    # HMP dictionary containing top-level status: already_done, comment: {status: failed},
    # and roulette: [{status: failed, message: "START 버튼이 표시되지 않음"}, {status: failed, message: "네트워크 오류"}]
    hmp_res = {
        "status": "already_done",
        "comment": {"status": "failed", "message": "저장 실패"},
        "roulette": [
            {"status": "failed", "message": "START 버튼이 표시되지 않음"},
            {"status": "failed", "message": "네트워크 오류"},
        ],
    }
    assert severity_of(hmp_res) == "alert"


def test_roulette_expected_failure_quiet():
    # Roulette expected failure "START 버튼이 표시되지 않음" alone evaluates to "quiet"
    res = {
        "status": "already_done",
        "roulette": [{"status": "failed", "message": "START 버튼이 표시되지 않음"}],
    }
    assert severity_of(res) == "quiet"


def test_should_send_actionable_mode():
    quiet_or_ok = {
        "keymedi": {"status": "already_done"},
        "doctorville": {"status": "success", "verified_by": "modal"},
        "hmp": {
            "status": "already_done",
            "roulette": [{"status": "failed", "message": "START 버튼이 표시되지 않음"}],
        },
    }
    assert should_send(quiet_or_ok, "actionable") is False

    actionable_action = {
        "doctorville": {"status": "no_answer", "product": "우루사"},
    }
    assert should_send(actionable_action, "actionable") is True

    actionable_alert = {
        "keymedi": {"status": "failed", "message": "로그인 오류"},
    }
    assert should_send(actionable_alert, "actionable") is True

    assert should_send(quiet_or_ok, "all") is True


def test_build_message_all_mode():
    results = {
        "keymedi": {"status": "already_done", "points": 10},
        "doctorville_bjh7790": {
            "attend": {"status": "success", "verified_by": "ok", "points": 50},
            "quiz": {"status": "no_answer", "product": "우루사"},
        },
    }
    msg = build_message(results, "all", "2026-08-31")
    assert "📋 *일일 자동화 결과*" in msg
    assert "키메디" in msg or "keymedi" in msg
    assert "우루사" in msg


def test_build_message_actionable_mode():
    # Actionable mode with actionable items
    results = {
        "keymedi": {"status": "already_done", "points": 10},
        "doctorville_bjh7790": {
            "attend": {"status": "success", "verified_by": "ok", "points": 50},
            "quiz": {"status": "no_answer", "product": "우루사", "message": "정답 없음"},
        },
    }
    msg = build_message(results, "actionable", "2026-08-31")
    assert "❗ DocAuto (2026-08-31)" in msg
    assert "no_answer" in msg
    assert "우루사" in msg
    assert "quiz_answers.json" in msg

    # Actionable mode with NO actionable items -> returns ""
    quiet_results = {
        "keymedi": {"status": "already_done"},
        "doctorville": {"status": "success", "verified_by": "modal"},
    }
    msg_empty = build_message(quiet_results, "actionable", "2026-08-31")
    assert msg_empty == ""


def test_notify_empty_env_level_fallback():
    quiet_results = {"keymedi": {"status": "already_done"}}
    assert should_send(quiet_results, "") is True
    assert should_send(quiet_results, "  ") is True
    assert should_send(quiet_results, "invalid_level") is True


def test_build_message_actionable_preserves_questions_payload():
    results = {
        "doctorville_bjh7790": {
            "quiz": {
                "status": "no_answer",
                "product": "우루사",
                "message": "정답 미등록\n두번째 줄 메세지",
                "questions": [{"q": "Q1: 질문 내용 첫번째 줄\n질문 내용 두번째 줄", "options": ["A", "B"]}],
            }
        }
    }
    msg = build_message(results, "actionable", "2026-08-31")
    assert "우루사" in msg
    assert "Q1: 질문 내용 첫번째 줄" in msg
    assert "질문 내용 두번째 줄" in msg
    assert "options" in msg
    assert "[\n  {\n" in msg  # verifies indent=2 formatted JSON output


def test_send_telegram_empty_text_returns_true():
    assert send_telegram("") is True
    assert send_telegram(None) is True

