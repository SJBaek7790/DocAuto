from pathlib import Path

def test_workflow_files_exist():
    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / ".github/workflows/seminar_block.yml").exists()
    assert not (repo_root / ".github/workflows/seminar_live.yml").exists()
    assert (repo_root / ".github/workflows/daily.yml").exists()

def test_daily_workflow_schedule_string():
    repo_root = Path(__file__).resolve().parent.parent
    daily_content = (repo_root / ".github/workflows/daily.yml").read_text("utf-8")
    assert "0 7 * * *" in daily_content
    assert "NOTIFY_LEVEL" in daily_content

def test_seminar_block_inbox_filter():
    repo_root = Path(__file__).resolve().parent.parent
    block_content = (repo_root / ".github/workflows/seminar_block.yml").read_text("utf-8")
    assert "11" in block_content
    assert "NOTIFY_LEVEL" in block_content
