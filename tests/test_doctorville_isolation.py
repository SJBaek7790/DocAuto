from pathlib import Path
from unittest.mock import MagicMock, patch
import doctorville

def test_doctorville_run_task_fault_isolation(monkeypatch, tmp_path):
    """attend 실패 시에도 quiz와 seminar가 독립적으로 계속 실행되어야 한다."""
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"bjh7790": {"email": "bjh7790@gmail.com", "doctorville": {"id": "user", "password": "pw"}}}', encoding="utf-8")

    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright = MagicMock()
    mock_playwright.__enter__.return_value.chromium.launch.return_value = mock_browser

    monkeypatch.setattr(doctorville, "sync_playwright", lambda: mock_playwright)
    monkeypatch.setattr(doctorville, "ensure_logged_in", lambda page, creds: True)
    monkeypatch.setattr(doctorville.common, "goto_with_retry", lambda *args, **kwargs: None)
    monkeypatch.setattr(doctorville, "save_screenshot", lambda page, tag: f"mock_{tag}.png")

    def failing_attend(page, creds):
        raise RuntimeError("attend network crash: net::ERR_CONNECTION_CLOSED")

    def successful_quiz(page, creds):
        return {"status": "success", "product": "test_product", "points": 500, "verified_by": "mock"}

    def successful_seminar(page, creds, account="bjh7790"):
        return {"status": "no_target", "count": 0, "applied": []}

    monkeypatch.setattr(doctorville, "task_attend", failing_attend)
    monkeypatch.setattr(doctorville, "task_quiz", successful_quiz)
    monkeypatch.setattr(doctorville, "task_seminar", successful_seminar)

    result = doctorville.run(
        account="bjh7790",
        credentials_path=creds_file,
        headless=True,
        tasks=["attend", "quiz", "seminar"],
    )

    assert result["attend"]["status"] == "failed"
    assert "attend network crash" in result["attend"]["message"]
    assert result["quiz"]["status"] == "success"
    assert result["quiz"]["product"] == "test_product"
    assert result["seminar"]["status"] == "no_target"
