import json
import os
from pathlib import Path
from common import is_recon_enabled
from recon import dump_recon_data

def test_is_recon_enabled(monkeypatch):
    monkeypatch.setenv("RECON", "1")
    assert is_recon_enabled() is True
    monkeypatch.delenv("RECON", raising=False)
    assert is_recon_enabled() is False

def test_dump_recon_data_creates_json_file():
    data = {"url": "https://example.com/survey", "body": "Survey complete"}
    file_path = dump_recon_data("R1", data, page=None)
    
    assert isinstance(file_path, str)
    assert os.path.exists(file_path)
    path_obj = Path(file_path)
    
    assert path_obj.name.startswith("recon_R1_")
    assert path_obj.name.endswith(".json")
    
    # Check outputs are strictly contained within scripts/logs/
    expected_dir = Path(__file__).resolve().parent.parent / "scripts" / "logs"
    assert path_obj.parent.resolve() == expected_dir.resolve()
    
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["url"] == "https://example.com/survey"
    assert loaded["body"] == "Survey complete"
