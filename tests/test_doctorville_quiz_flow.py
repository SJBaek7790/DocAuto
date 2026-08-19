import json
from unittest.mock import MagicMock, patch
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import doctorville


def _create_mock_quiz_page(product="우루사", q_texts=None, choices=None, banner_class=""):
    q_texts = q_texts or ["Q1. 질문1", "Q2. 질문2"]
    choices = choices or [["보기1-1", "보기1-2"], ["보기2-1", "보기2-2"]]

    mock_page = MagicMock()

    # 캘린더 및 배너
    mock_banner = MagicMock()
    mock_banner.get_attribute.return_value = banner_class

    # 퀴즈 레이어
    mock_layer = MagicMock()

    # 문항 영역 mock
    mock_areas = []
    for i, (q, chs) in enumerate(zip(q_texts, choices)):
        qa = MagicMock()
        qa.locator.side_effect = lambda sel, _q=q, _chs=chs: (
            MagicMock(inner_text=lambda: _q) if ".txt_question" in sel
            else MagicMock(
                count=lambda: len(_chs),
                nth=lambda idx, _c=_chs: MagicMock(
                    locator=lambda s, _idx=idx, _c=_c: (
                        MagicMock(inner_text=lambda: _c[_idx]) if "label" in s
                        else MagicMock(get_attribute=lambda attr: str(_idx + 1))
                    )
                )
            )
        )
        mock_areas.append(qa)

    mock_q_areas = MagicMock()
    mock_q_areas.count.return_value = len(mock_areas)
    mock_q_areas.nth.side_effect = lambda idx: mock_areas[idx]

    mock_submit_btn = MagicMock()
    mock_submit_btn.count.return_value = 1
    mock_submit_btn.is_visible.return_value = True

    def layer_locator(sel):
        if ".question_area" in sel:
            return mock_q_areas
        if ".btn_answer" in sel:
            return mock_submit_btn
        if ":text('축하드립니다')" in sel:
            return MagicMock(count=lambda: 0)
        return MagicMock(first=MagicMock(is_visible=lambda: False))

    mock_layer.locator.side_effect = layer_locator

    def page_locator(sel):
        if sel == "#btn_quiz_banner":
            return mock_banner
        if sel == "#quizLayerPop":
            return mock_layer
        if 'button:has-text("확인")' in sel:
            return MagicMock(last=MagicMock(is_visible=lambda: True))
        return MagicMock()

    mock_page.locator.side_effect = page_locator
    return mock_page


def test_task_quiz_legacy_promotion_and_eviction(tmp_path, monkeypatch):
    """Legacy 정답으로 성공 시 quiz_answers.json으로 승격되고 legacy에서 제거되는지 검증."""
    quiz_file = tmp_path / "quiz_answers.json"
    legacy_file = tmp_path / "quiz_answers_legacy.json"

    quiz_file.write_text("{}", encoding="utf-8")
    legacy_file.write_text(json.dumps({"우루사": "12"}), encoding="utf-8")

    monkeypatch.setattr(doctorville, "QUIZ_ANSWERS_PATH", quiz_file)
    monkeypatch.setattr(doctorville, "LEGACY_ANSWERS_PATH", legacy_file)
    monkeypatch.setattr(doctorville, "_get_today_quiz_product", lambda p: ("우루사", "pid1", "qid1"))

    page = _create_mock_quiz_page("우루사")
    page.wait_for_selector.side_effect = lambda sel, timeout=None: (
        MagicMock() if ":text('정답입니다')" in sel else None
    )

    res = doctorville.task_quiz(page, {"email": "test@test.com", "password": "pw"})

    assert res["status"] == "success"
    assert res["source"] == "legacy"
    assert res["points"] == 500
    assert res["verified_by"] == ":text('정답입니다')"

    # 족보 파일 승격 확인
    quiz_data = json.loads(quiz_file.read_text(encoding="utf-8"))
    assert quiz_data["우루사"] == {"Q1. 질문1": "보기1-1", "Q2. 질문2": "보기2-2"}

    # Legacy 파일에서 삭제 확인
    legacy_data = json.loads(legacy_file.read_text(encoding="utf-8"))
    assert "우루사" not in legacy_data


def test_task_quiz_partial_wrong_answers_learning(tmp_path, monkeypatch):
    """오답 문구('2번 오답입니다') 수신 시 1번 문항만 저장되고 legacy는 제거되는지 검증."""
    quiz_file = tmp_path / "quiz_answers.json"
    legacy_file = tmp_path / "quiz_answers_legacy.json"

    quiz_file.write_text("{}", encoding="utf-8")
    legacy_file.write_text(json.dumps({"우루사": "11"}), encoding="utf-8")

    monkeypatch.setattr(doctorville, "QUIZ_ANSWERS_PATH", quiz_file)
    monkeypatch.setattr(doctorville, "LEGACY_ANSWERS_PATH", legacy_file)
    monkeypatch.setattr(doctorville, "_get_today_quiz_product", lambda p: ("우루사", "pid1", "qid1"))

    page = _create_mock_quiz_page("우루사")

    def mock_wait(sel, timeout=None):
        if ":text('정답입니다')" in sel:
            raise PlaywrightTimeoutError("Timeout")
        if ":text('오답입니다')" in sel:
            return MagicMock(inner_text=lambda: "2번 오답입니다.")
        return MagicMock()

    page.wait_for_selector.side_effect = mock_wait

    res = doctorville.task_quiz(page, {"email": "test@test.com", "password": "pw"})

    assert res["status"] == "failed"
    # 맞힌 1번 문항은 quiz_answers.json에 기록
    quiz_data = json.loads(quiz_file.read_text(encoding="utf-8"))
    assert quiz_data["우루사"] == {"Q1. 질문1": "보기1-1"}
    # legacy는 틀렸으므로 삭제
    legacy_data = json.loads(legacy_file.read_text(encoding="utf-8"))
    assert "우루사" not in legacy_data


def test_task_quiz_already_done_on_popup_open(tmp_path, monkeypatch):
    """팝업 열자마자 '축하드립니다' 또는 '내일 다시 만나요'가 있으면 already_done으로 처리."""
    quiz_file = tmp_path / "quiz_answers.json"
    quiz_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(doctorville, "QUIZ_ANSWERS_PATH", quiz_file)
    monkeypatch.setattr(doctorville, "_get_today_quiz_product", lambda p: ("엔블로", "pid1", "qid1"))

    mock_page = MagicMock()
    mock_banner = MagicMock()
    mock_banner.get_attribute.return_value = ""  # 배너에는 ico_finish가 없는 경우

    mock_layer = MagicMock()
    mock_close_btn = MagicMock()
    mock_close_btn.is_visible.return_value = True

    def layer_locator(sel):
        if ":text('축하드립니다')" in sel:
            return MagicMock(count=lambda: 1)
        if ":text('내일 다시 만나요')" in sel:
            return MagicMock(count=lambda: 1)
        if ".btn_cancel" in sel or ".btn_close" in sel or "button:has-text('닫기')" in sel:
            return MagicMock(first=mock_close_btn)
        return MagicMock(count=lambda: 0, first=MagicMock(is_visible=lambda: False))

    mock_layer.locator.side_effect = layer_locator

    def page_locator(sel):
        if sel == "#btn_quiz_banner":
            return mock_banner
        if sel == "#quizLayerPop":
            return mock_layer
        return MagicMock()

    mock_page.locator.side_effect = page_locator

    res = doctorville.task_quiz(mock_page, {"email": "test@test.com", "password": "pw"})

    assert res["status"] == "already_done"
    assert "verified_by" in res
    assert "이미 완료" in res["message"]
    mock_close_btn.click.assert_called()

