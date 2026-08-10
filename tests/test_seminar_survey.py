import json

from seminar_survey import (
    add_missing_to_bank,
    load_bank,
    lookup_answer,
    mark_survey_done,
    match_option,
    normalize_question,
    pending_seminar_ids,
    resolve_page,
)


def test_normalize_question_strips_quiz_badge_and_star():
    assert normalize_question("[퀴즈]렉사프로는 무엇입니까?*") == "렉사프로는 무엇입니까?"
    assert normalize_question("  렉사프로는   무엇입니까? ") == "렉사프로는 무엇입니까?"


def test_lookup_answer_treats_empty_as_missing():
    bank = {"질문": "", "질문2": [], "질문3": "답"}
    assert lookup_answer(bank, "질문") is None
    assert lookup_answer(bank, "질문2") is None
    assert lookup_answer(bank, "질문3") == "답"
    assert lookup_answer(bank, "없는질문") is None


def test_lookup_answer_matches_badged_question():
    bank = {"렉사프로는 무엇입니까?": "1번"}
    assert lookup_answer(bank, "[퀴즈]렉사프로는 무엇입니까?*") == "1번"


def test_match_option_unique_only():
    opts = ["체중이 증가했다", "체중 변화가 없었다", "혈당이 감소했다"]
    assert match_option("혈당이 감소", opts) == 2
    assert match_option("체중", opts) is None  # 두 보기에 걸림
    assert match_option("없음", opts) is None


def test_match_option_by_number():
    opts = ["가", "나", "다"]
    assert match_option("1", opts) == 0
    assert match_option("3", opts) == 2
    assert match_option("0", opts) is None
    assert match_option("4", opts) is None


def test_match_option_number_wins_over_text_containing_digit():
    # 보기 텍스트에 숫자가 섞여 있어도 "1"은 언제나 첫 번째 보기를 뜻한다.
    opts = ["1일 2회 복용", "1일 1회 복용"]
    assert match_option("1", opts) == 0


def _choice_q(text, options, base="userQuestions.0.optionIds"):
    return {
        "number": "1",
        "question": text,
        "kind": "choice",
        "name": base,
        "options": [{"text": o, "name": base, "value": str(i), "type": "radio"} for i, o in enumerate(options)],
    }


def test_resolve_page_all_known():
    q = _choice_q("문항1", ["가", "나", "다"])
    plan, missing = resolve_page([q], {"문항1": "나"})
    assert missing == []
    assert plan[0]["kind"] == "choice"
    assert plan[0]["targets"][0]["value"] == "1"


def test_resolve_page_number_answer():
    q = _choice_q("문항1", ["가", "나", "다"])
    plan, missing = resolve_page([q], {"문항1": "2"})
    assert missing == []
    assert plan[0]["targets"][0]["value"] == "1"


def test_resolve_page_comma_separated_numbers():
    q = _choice_q("문항1", ["가", "나", "다"])
    plan, missing = resolve_page([q], {"문항1": "1,3"})
    assert missing == []
    assert [t["value"] for t in plan[0]["targets"]] == ["0", "2"]


def test_resolve_page_comma_in_text_answer_is_not_split():
    q = _choice_q("문항1", ["가, 나 둘 다", "다"])
    plan, missing = resolve_page([q], {"문항1": "가, 나 둘 다"})
    assert missing == []
    assert plan[0]["targets"][0]["value"] == "0"


def test_resolve_page_reports_missing_with_options():
    q = _choice_q("문항1", ["가", "나"])
    plan, missing = resolve_page([q], {})
    assert plan == []
    # 보기에는 입력할 번호가 붙어 나온다.
    assert missing == [{"question": "문항1", "options": ["1. 가", "2. 나"]}]


def test_resolve_page_unmatched_stored_value_is_missing():
    q = _choice_q("문항1", ["가", "나"])
    _, missing = resolve_page([q], {"문항1": "다"})
    assert len(missing) == 1


def test_resolve_page_multi_select_list_value():
    q = _choice_q("문항1", ["가", "나", "다"])
    plan, missing = resolve_page([q], {"문항1": ["가", "다"]})
    assert missing == []
    assert [t["value"] for t in plan[0]["targets"]] == ["0", "2"]


def test_resolve_page_free_text():
    q = {"number": "1", "question": "의견을 적어주세요", "kind": "input", "name": "free.0", "options": []}
    plan, missing = resolve_page([q], {"의견을 적어주세요": "좋았습니다"})
    assert missing == []
    assert plan == [{"kind": "input", "name": "free.0", "value": "좋았습니다"}]


def test_add_missing_to_bank_writes_empty_placeholders(tmp_path):
    bank_path = tmp_path / "survey_answers.json"
    bank_path.write_text(json.dumps({"기존": "값"}), encoding="utf-8")
    added = add_missing_to_bank(bank_path, [{"question": "새문항", "options": ["가"]}, {"question": "기존", "options": []}])
    assert added == 1
    assert load_bank(bank_path) == {"기존": "값", "새문항": ""}


def test_pending_seminar_ids_excludes_done():
    state = {"accounts": {"bjh7790": {"entered": [1, 2, 3], "survey_done": [2]}}}
    assert pending_seminar_ids(state, "bjh7790") == [1, 3]
    assert pending_seminar_ids(state, "wonju") == []


def test_mark_survey_done_is_idempotent():
    state = {"accounts": {"bjh7790": {"entered": [1]}}}
    mark_survey_done(state, "bjh7790", 1)
    mark_survey_done(state, "bjh7790", "1")
    assert state["accounts"]["bjh7790"]["survey"] == {"1": "done"}


# --- canonical(유하게 대조) 매칭 -------------------------------------------

def test_canonical_ignores_space_case_and_punctuation():
    from seminar_survey import canonical_question
    assert canonical_question("edoxaban 30 mg 처방") == canonical_question("Edoxaban 30mg 처방")
    assert canonical_question("‘실제’ 진료에서") == canonical_question("'실제' 진료에서")


def test_canonical_strips_required_and_multiselect_annotations():
    from seminar_survey import canonical_question
    base = "주요 이유는 무엇입니까?"
    assert canonical_question(base + "*(최소 1개 선택)") == canonical_question(base)
    assert canonical_question(base + " (복수 선택 가능)*(최소 1개 선택)") == canonical_question(base)
    assert canonical_question(base + " (복수응답 가능)*(최대 6개 선택)") == canonical_question(base)


def test_lookup_answer_matches_spacing_and_case_variant():
    bank = {"Edoxaban 30mg 처방 경험이 있으십니까?": "2"}
    assert lookup_answer(bank, "edoxaban 30 mg 처방 경험이 있으십니까?") == "2"


def test_lookup_answer_matches_annotation_variant():
    bank = {"주요 이유는 무엇입니까?": "2"}
    assert lookup_answer(bank, "주요 이유는 무엇입니까? (복수 선택 가능)*(최소 1개 선택)") == "2"


def test_lookup_answer_exact_key_wins_over_canonical():
    bank = {"질문 A?": "1", "질문A?": "3"}
    assert lookup_answer(bank, "질문 A?") == "1"


def test_lookup_answer_rejects_conflicting_canonical_collision():
    # 표기만 다른 두 키가 서로 다른 답을 들고 있으면 어느 쪽도 쓰지 않는다.
    bank = {"질문 A?": "1", "질문A?": "3"}
    assert lookup_answer(bank, "질  문  A?") is None


def test_lookup_answer_does_not_fuzzy_match_similar_questions():
    # 실제 문제은행에 있는 difflib 유사도 0.92짜리 서로 다른 문항.
    bank = {"1차 예방 당뇨병 환자에서 스타틴 치료 시작 시 고려 기준은?": "2"}
    assert lookup_answer(bank, "1차 예방 중등도 위험군 환자에서 스타틴 치료 시작 시 고려 기준은?") is None


def test_add_missing_skips_canonical_duplicate(tmp_path):
    bank_path = tmp_path / "survey_answers.json"
    bank_path.write_text(json.dumps({"주요 이유는 무엇입니까?": ""}), encoding="utf-8")
    added = add_missing_to_bank(bank_path, [{"question": "주요 이유는 무엇입니까?*(최소 1개 선택)", "options": []}])
    assert added == 0
    assert list(load_bank(bank_path)) == ["주요 이유는 무엇입니까?"]


# --- 다음/제출하기 버튼 -----------------------------------------------------

def test_classify_advance_label():
    from seminar_survey import classify_advance_label
    assert classify_advance_label("다음") == "next"
    assert classify_advance_label("다음 페이지") == "next"
    assert classify_advance_label("제출하기") == "submit"
    assert classify_advance_label("설문 완료") == "submit"
    assert classify_advance_label("이전") is None
    assert classify_advance_label("임시저장") is None
    assert classify_advance_label("닫기") is None
    assert classify_advance_label("") is None


def test_page_fingerprint_distinguishes_pages():
    from seminar_survey import page_fingerprint
    p1 = [{"number": "1", "question": "문항1"}]
    p2 = [{"number": "2", "question": "문항2"}]
    assert page_fingerprint(p1) == page_fingerprint([{"number": "1", "question": " 문항1 *"}])
    assert page_fingerprint(p1) != page_fingerprint(p2)
