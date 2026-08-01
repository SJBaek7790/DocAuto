import json
from doctorville import load_quiz_answers_legacy, _record_answers, _evict_answers, _evict_legacy_answers

def test_load_quiz_answers_legacy(tmp_path, monkeypatch):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")
    monkeypatch.setattr("doctorville.LEGACY_ANSWERS_PATH", legacy_file)
    
    data = load_quiz_answers_legacy()
    assert data == {"에빅사": "111"}

def test_record_answers(tmp_path, monkeypatch):
    bank_file = tmp_path / "quiz_answers.json"
    bank_file.write_text(json.dumps({"에빅사": {"Q1": "A1"}}), encoding="utf-8")
    monkeypatch.setattr("doctorville.QUIZ_ANSWERS_PATH", bank_file)

    # Empty pairs should not touch file
    _record_answers("에빅사", [])
    
    _record_answers("에빅사", [("Q2", "A2")])
    content = bank_file.read_text(encoding="utf-8")
    updated = json.loads(content)
    assert updated["에빅사"] == {"Q1": "A1", "Q2": "A2"}
    assert content.endswith("\n")

def test_evict_answers(tmp_path, monkeypatch):
    bank_file = tmp_path / "quiz_answers.json"
    bank_file.write_text(json.dumps({"펙수클루정": {"Q1": "WRONG_A1", "Q2": "RIGHT_A2"}}), encoding="utf-8")
    monkeypatch.setattr("doctorville.QUIZ_ANSWERS_PATH", bank_file)

    # Evict Q1 from bank
    _evict_answers("펙수클루정", ["Q1"])
    content = bank_file.read_text(encoding="utf-8")
    updated = json.loads(content)
    assert updated["펙수클루정"] == {"Q2": "RIGHT_A2"}
    assert content.endswith("\n")

def test_evict_legacy_answers(tmp_path, monkeypatch):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111", "우루사": "222"}), encoding="utf-8")
    monkeypatch.setattr("doctorville.LEGACY_ANSWERS_PATH", legacy_file)

    _evict_legacy_answers("에빅사")
    content = legacy_file.read_text(encoding="utf-8")
    updated = json.loads(content)
    assert updated == {"우루사": "222"}
    assert content.endswith("\n")


from unittest.mock import MagicMock, patch
import sys
import doctorville

def test_task_quiz_no_answer_payload(monkeypatch):
    mock_page = MagicMock()

    monkeypatch.setattr("doctorville._get_today_quiz_product", lambda p: ("테스트제품", "123", "999"))
    monkeypatch.setattr("doctorville._get_product_pid", lambda p, prod: "123")
    monkeypatch.setattr("doctorville.load_quiz_answers", lambda: {})
    monkeypatch.setattr("doctorville.load_quiz_answers_legacy", lambda: {})
    monkeypatch.setattr("doctorville.save_screenshot", lambda p, tag: "dummy.png")

    mock_banner = MagicMock()
    mock_banner.get_attribute.return_value = ""

    mock_layer = MagicMock()

    mock_q_area = MagicMock()
    mock_q_area.locator.side_effect = lambda sel: (
        MagicMock(inner_text=lambda: "Q1. 질문내용") if ".txt_question" in sel
        else MagicMock(count=lambda: 2, nth=lambda i: MagicMock(
            locator=lambda s: (
                MagicMock(inner_text=lambda: f"보기{i+1}") if "label" in s
                else MagicMock(get_attribute=lambda attr: f"val{i+1}")
            )
        ))
    )

    mock_q_areas = MagicMock()
    mock_q_areas.count.return_value = 1
    mock_q_areas.nth.return_value = mock_q_area

    mock_close_btn = MagicMock()
    mock_close_btn.is_visible.return_value = False

    def layer_locator(sel):
        if ".question_area" in sel:
            return mock_q_areas
        if ".btn_cancel" in sel or ".btn_close" in sel:
            return mock_close_btn
        return MagicMock()

    mock_layer.locator.side_effect = layer_locator

    def page_locator(sel):
        if sel == "#btn_quiz_banner":
            return mock_banner
        if sel == "#quizLayerPop":
            return mock_layer
        return MagicMock()

    mock_page.locator.side_effect = page_locator

    res = doctorville.task_quiz(mock_page, {"email": "a", "password": "b"})

    assert res["status"] == "no_answer"
    assert "questions" in res
    assert res["questions"] == [
        {
            "question": "Q1. 질문내용",
            "options": ["보기1", "보기2"],
            "recorded_answer_not_matched": None,
        }
    ]
    assert "\n" not in res["message"]


def test_main_seminar_task_notifications(monkeypatch):
    mock_run = MagicMock(return_value={
        "site": "doctorville",
        "account": "bjh7790",
        "seminar": {"status": "success", "applied": [101], "count": 1}
    })
    mock_should_send = MagicMock(return_value=True)
    mock_build_msg = MagicMock(return_value="[Seminar Alert] Applied 1 seminar")
    mock_send_tg = MagicMock(return_value=True)

    monkeypatch.setattr("doctorville.run", mock_run)
    monkeypatch.setattr("notify.should_send", mock_should_send)
    monkeypatch.setattr("notify.build_message", mock_build_msg)
    monkeypatch.setattr("notify.send_telegram", mock_send_tg)

    test_args = ["doctorville.py", "--account", "bjh7790", "--task", "seminar"]
    monkeypatch.setattr(sys, "argv", test_args)

    with patch("sys.exit") as mock_exit:
        doctorville.main()
        mock_exit.assert_called_with(0)

    assert mock_should_send.called
    assert mock_build_msg.called
    assert mock_send_tg.called
    assert mock_send_tg.call_args[0][0] == "[Seminar Alert] Applied 1 seminar"


