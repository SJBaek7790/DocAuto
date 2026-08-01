import pytest
from daily_runner import build_execution_plan
from notify import should_send

def test_build_execution_plan():
    creds = {
        "telegram": {},
        "bjh7790": {"doctorville": {}, "hmp": {}, "keymedi": {}},
        "wonju": {"doctorville": {}}
    }
    plan = build_execution_plan(creds)
    assert "keymedi" in plan
    assert "doctorville_bjh7790" in plan
    assert "doctorville_wonju" in plan
    assert "hmp" in plan
    assert "precheck_quiz" in plan

    # Verify script and args detail
    assert plan["keymedi"]["script"] == "keymedi.py"
    assert plan["doctorville_bjh7790"]["script"] == "doctorville.py"
    assert "--account" in plan["doctorville_bjh7790"]["args"]
    assert "bjh7790" in plan["doctorville_bjh7790"]["args"]
    assert plan["doctorville_wonju"]["script"] == "doctorville.py"
    assert "wonju" in plan["doctorville_wonju"]["args"]
    assert plan["hmp"]["script"] == "hmp.py"
    assert plan["precheck_quiz"]["script"] == "doctorville.py"
    assert "--task" in plan["precheck_quiz"]["args"]
    assert "precheck_quiz" in plan["precheck_quiz"]["args"]

def test_should_send_actionable_zero_calls():
    quiet_results = {
        "keymedi": {"status": "already_done"},
        "hmp": {
            "status": "already_done",
            "roulette": [{"status": "failed", "message": "START 버튼이 표시되지 않음"}]
        },
        "doctorville_bjh7790": {
            "attend": {"status": "already_done"},
            "quiz": {"status": "already_done"}
        },
        "precheck_quiz": {"status": "already_done"}
    }
    assert should_send(quiet_results, "actionable") is False
