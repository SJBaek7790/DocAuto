from doctorville import match_quiz_bank, parse_calendar_cell


def test_match_quiz_bank_one_way():
    bank = {"펙수클루정": {"Q": "A"}}
    legacy = {"우루사": "111"}

    # Safe direction: bank key inside product name
    assert match_quiz_bank("펙수클루정40mg", bank, legacy) is True
    assert match_quiz_bank("우루사", bank, legacy) is True
    # Dangerous direction: product name inside longer bank key MUST NOT match
    assert match_quiz_bank("펙수", bank, legacy) is False


def test_parse_calendar_cell():
    cell_html = """
    <td class="pass">
        <input type="hidden" class="pIdCls" value="108">
        <input type="hidden" class="quizIdCls" value="3564">
        <span class="day">2</span>
        <span class="name">펙수클루정40mg</span>
    </td>
    """
    info = parse_calendar_cell(cell_html)
    assert info["product"] == "펙수클루정40mg"
    assert info["p_id"] == "108"
    assert info["quiz_id"] == "3564"
