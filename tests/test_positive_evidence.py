import pytest
from notify import severity_of
from hmp import verify_comment_saved

def test_severity_with_verified_by():
    assert severity_of({"status": "success", "verified_by": "modal"}) == "ok"

def test_severity_demotes_missing_verified_by():
    assert severity_of({"status": "success"}) == "alert"

def test_verify_comment_saved():
    html_with_nick = "<div id='cmtDiv'><span class='cmtName'>승진</span>: 감사</div>"
    html_without_nick = "<div id='cmtDiv'><span class='cmtName'>다른사람</span>: 감사</div>"
    assert verify_comment_saved(html_with_nick, "승진") is True
    assert verify_comment_saved(html_without_nick, "승진") is False
    assert verify_comment_saved("", "승진") is False
    assert verify_comment_saved(html_with_nick, "") is False

def test_verified_by_contracts_all_10_modules():
    # 1. Doctorville Attend
    res_dv_attend = {"status": "success", "verified_by": "attend_confirmed"}
    assert severity_of(res_dv_attend) == "ok"
    assert res_dv_attend["verified_by"] == "attend_confirmed"

    # 2. Doctorville Quiz
    res_dv_quiz = {"status": "success", "verified_by": ":text('정답입니다')"}
    assert severity_of(res_dv_quiz) == "ok"
    assert res_dv_quiz["verified_by"] == ":text('정답입니다')"

    # 3. Doctorville Seminar Apply
    res_dv_seminar = {"status": "success", "verified_by": "a.btn_bn: 신청취소"}
    assert severity_of(res_dv_seminar) == "ok"
    assert res_dv_seminar["verified_by"] == "a.btn_bn: 신청취소"

    # 4. Keymedi Attend
    res_km = {"status": "success", "verified_by": "modal: 출석체크가 완료되었습니다"}
    assert severity_of(res_km) == "ok"
    assert res_km["verified_by"] == "modal: 출석체크가 완료되었습니다"

    # 5. HMP Capsule
    res_hmp_cap = {"status": "success", "verified_by": "popup: 10rewardPopup"}
    assert severity_of(res_hmp_cap) == "ok"
    assert res_hmp_cap["verified_by"] == "popup: 10rewardPopup"

    # 6. HMP Roulette
    res_hmp_roul = {"status": "success", "verified_by": "alt: 100캡슐 당첨"}
    assert severity_of(res_hmp_roul) == "ok"
    assert "alt:" in res_hmp_roul["verified_by"]

    # 7. HMP Comment
    res_hmp_cmt = {"status": "success", "verified_by": "nickname_verified: 승진"}
    assert severity_of(res_hmp_cmt) == "ok"
    assert res_hmp_cmt["verified_by"].startswith("nickname_verified:")

    # 8. HMP Post
    res_hmp_post = {"status": "success", "verified_by": "rtn_code_100"}
    assert severity_of(res_hmp_post) == "ok"
    assert res_hmp_post["verified_by"] == "rtn_code_100"

    # 9. Seminar Live Entry
    res_live = {"status": "success", "verified_by": "popup_acquired"}
    assert severity_of(res_live) == "ok"
    assert res_live["verified_by"] == "popup_acquired"

    # 10. Seminar Survey
    res_survey = {"status": "success", "verified_by": "completion_screen_verified"}
    assert severity_of(res_survey) == "ok"
    assert res_survey["verified_by"] == "completion_screen_verified"
