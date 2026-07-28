from hmp import parse_board_seqs


ONCLICKS = [
    # 목록 상단 고정 게시물(공지·[지식스폰서]) — 번호가 낮다.
    "$KnowCommHome.goDetail('2518741');",
    "$KnowCommHome.goDetail('2501691');",
    "$KnowCommHome.goDetail('2496228');",
    # 실제 최신글
    "$KnowCommHome.goDetail('2522297');",
    "$KnowCommHome.goDetail('2522296');",
]


def test_parse_board_seqs_sorts_newest_first():
    assert parse_board_seqs(ONCLICKS)[:3] == ["2522297", "2522296", "2518741"]


def test_parse_board_seqs_dedupes_and_limits():
    assert parse_board_seqs(ONCLICKS + ONCLICKS, limit=2) == ["2522297", "2522296"]


def test_parse_board_seqs_ignores_unparsable():
    assert parse_board_seqs(["", "goDetail()", None, "$KnowCommHome.goDetail('7');"]) == ["7"]
