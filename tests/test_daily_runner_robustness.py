import subprocess
from unittest.mock import MagicMock, patch
from daily_runner import run_script, evaluate_exit_code


def test_run_script_parses_multiline_json_with_preceding_logs():
    """stdout에 앞선 로그 라인이 있고 마지막에 인덴트된 멀티라인 JSON이 출력되어도 정상 파싱되어야 함."""
    stdout_text = """
[1/5] doctorville_bjh7790...
Browser initialized.
{
  "site": "doctorville",
  "account": "bjh7790",
  "attend": {
    "status": "success",
    "verified_by": "today_cell"
  }
}
"""
    mock_proc = MagicMock()
    mock_proc.stdout = stdout_text
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc):
        res = run_script("doctorville.py")

    assert res.get("status") != "failed" or "JSON 파싱 실패" not in res.get("message", "")
    assert res.get("site") == "doctorville"
    assert res.get("attend", {}).get("status") == "success"


def test_evaluate_exit_code_strictly_catches_all_alert_statuses():
    """failed, unverified, blocked 중 하나라도 있으면 1을 반환해야 함."""
    assert evaluate_exit_code({"a": {"status": "unverified"}}) == 1
    assert evaluate_exit_code({"a": {"status": "blocked"}}) == 1
    assert evaluate_exit_code({"a": {"status": "failed"}}) == 1
    assert evaluate_exit_code({"a": {"status": "success"}, "b": {"status": "already_done"}}) == 0
    assert evaluate_exit_code({"a": {"status": "no_answer"}}) == 0
