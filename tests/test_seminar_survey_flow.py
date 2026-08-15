from unittest.mock import MagicMock
import seminar_survey
from notify import severity_of


def test_rollup_verified_by_partial_missing_demotes_to_alert():
    """성공한 설문 중 1건이라도 verified_by가 없으면 계정 증거가 생성되지 않아 alert로 강등되어야 함."""
    surveys = [
        {"seminarId": 101, "status": "success", "verified_by": "completion_screen_verified"},
        {"seminarId": 102, "status": "success"},  # verified_by 누락
    ]
    verified = seminar_survey.rollup_verified_by(surveys)
    assert verified == ""

    account_node = {
        "status": seminar_survey.rollup_account_status([s["status"] for s in surveys]),
        "surveys": surveys,
    }
    if verified:
        account_node["verified_by"] = verified

    assert account_node["status"] == "success"
    # notify 게이트에서 unverified (alert)로 강등 판정
    assert severity_of(account_node) == "alert"


def test_dismiss_alerts_handles_headlessui_modals():
    """HeadlessUI 알림 모달이 떠 있을 때 버튼 클릭으로 해제하는지 검증."""
    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.count.return_value = 1
    mock_dialog.first.inner_text.return_value = "작성 중인 정보를 불러왔습니다"

    mock_btn = MagicMock()
    mock_btn.count.return_value = 1
    mock_dialog.first.locator.return_value = mock_btn

    def mock_locator(sel):
        if '[role="dialog"][data-headlessui-state="open"]' in sel:
            return mock_dialog
        return MagicMock(count=lambda: 0)

    mock_page.locator.side_effect = mock_locator

    dismissed = seminar_survey.dismiss_alerts(mock_page, max_rounds=1)
    assert len(dismissed) == 1
    assert "작성 중인 정보를 불러왔습니다" in dismissed[0]
    mock_btn.first.click.assert_called_once()


def test_run_survey_collects_new_text_question_into_survey_text_answers(tmp_path, monkeypatch):
    """새로운 서술형(주관식) 문항을 만나면 survey_text_answers.json에 빈 값('')으로 정상 수집하고 incomplete_bank를 반환하는지 검증."""
    import json
    quiz_file = tmp_path / "survey_quiz_answers.json"
    text_file = tmp_path / "survey_text_answers.json"
    legacy_file = tmp_path / "survey_answers_legacy.json"

    quiz_file.write_text("{}", encoding="utf-8")
    text_file.write_text("{}", encoding="utf-8")
    legacy_file.write_text("{}", encoding="utf-8")

    bank_paths = {
        "quiz": quiz_file,
        "text": text_file,
        "legacy": legacy_file,
    }

    # 설문 팝업 창 mock
    mock_survey_page = MagicMock()
    mock_survey_page.is_closed.return_value = False
    mock_survey_page.evaluate.return_value = [
        {
            "number": "1",
            "question": "본 세미나에 대한 건의사항이나 후기를 자유롭게 작성해주세요.",
            "kind": "input",
            "name": "free.0",
            "options": [],
        }
    ]

    mock_main_page = MagicMock()
    monkeypatch.setattr(seminar_survey, "open_survey", lambda page, sid: (mock_survey_page, "호흡기 최신 지견"))
    monkeypatch.setattr(seminar_survey, "dismiss_alerts", lambda page: [])

    result = seminar_survey.run_survey(
        mock_main_page,
        5500,
        bank_paths=bank_paths,
    )

    # 1. status가 incomplete_bank로 판정되어야 함
    assert result["status"] == "incomplete_bank"
    assert "1페이지에 미등록 문항 1건" in result["message"]
    assert "주관식 1건" in result["message"]
    assert len(result["missing"]) == 1
    assert result["missing"][0]["bank"] == "text"
    assert result["missing"][0]["question"] == "본 세미나에 대한 건의사항이나 후기를 자유롭게 작성해주세요."

    # 2. survey_text_answers.json에 해당 문항이 빈 문자열("")로 저장되었는지 검증
    saved_text_bank = json.loads(text_file.read_text(encoding="utf-8"))
    assert "본 세미나에 대한 건의사항이나 후기를 자유롭게 작성해주세요." in saved_text_bank
    assert saved_text_bank["본 세미나에 대한 건의사항이나 후기를 자유롭게 작성해주세요."] == ""

    # 3. survey_quiz_answers.json이나 legacy_file에는 쓰이지 않아야 함
    assert json.loads(quiz_file.read_text(encoding="utf-8")) == {}
    assert json.loads(legacy_file.read_text(encoding="utf-8")) == {}
