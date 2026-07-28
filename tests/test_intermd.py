import json

from intermd import load_answer, match_choice, normalize, strip_question_prefix


def test_normalize_collapses_whitespace():
    assert normalize("  a   b \n c ") == "a b c"


def test_strip_question_prefix_removes_badge_and_star():
    assert strip_question_prefix("퀴즈\n발레 용어는?*") == "발레 용어는?"
    assert strip_question_prefix("[퀴즈] 발레 용어는?") == "발레 용어는?"


CHOICES = [
    "Promenade (프로미나드)",
    "Cambré (캄브레)",
    "Développé (데벨로페)",
    "Fondu (퐁듀)",
]


def test_match_choice_substring():
    assert match_choice("프로미나드", CHOICES) == 0
    assert match_choice("퐁듀", CHOICES) == 3


def test_match_choice_exact_wins_over_ambiguous_substring():
    choices = ["O", "OX 아님", "X"]
    assert match_choice("O", choices) == 0


def test_match_choice_accepts_1_based_number():
    assert match_choice("4", CHOICES) == 3
    assert match_choice(" 1 ", CHOICES) == 0


def test_match_choice_number_out_of_range():
    assert match_choice("5", CHOICES) is None
    assert match_choice("0", CHOICES) is None


def test_match_choice_returns_none_when_absent_or_ambiguous():
    assert match_choice("없는보기", CHOICES) is None
    assert match_choice("", CHOICES) is None
    assert match_choice("공통", ["공통 A", "공통 B"]) is None


def test_load_answer_missing_file(tmp_path):
    assert load_answer(tmp_path / "nope.json") == ""


def test_load_answer_reads_answer(tmp_path):
    p = tmp_path / "intermd_answer.json"
    p.write_text(json.dumps({"answer": "프로미나드"}), encoding="utf-8")
    assert load_answer(p) == "프로미나드"


def test_load_answer_empty_value(tmp_path):
    p = tmp_path / "intermd_answer.json"
    p.write_text(json.dumps({"answer": ""}), encoding="utf-8")
    assert load_answer(p) == ""
