#!/usr/bin/env python3
"""출석 자동화 스크립트 공용 유틸.

keymedi.py / hmp.py / doctorville.py가 공유하는 credentials 로딩·스크린샷·
폼 로그인 헬퍼. 사이트별 셀렉터와 완료 판정 로직은 각 스크립트에 남긴다.
"""

import json
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
DEFAULT_CREDENTIALS = SCRIPT_DIR.parent / "credentials.json"


def read_credentials(path: Path) -> dict:
    """credentials.json 전체를 dict로 읽어 반환한다."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_screenshot(page, name_stem: str) -> str:
    """logs/<name_stem>_<타임스탬프>.png 저장 후 경로 반환(실패 시 빈 문자열)."""
    LOG_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"{name_stem}_{ts}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


def form_login(
    page,
    id_selector: str,
    pw_selector: str,
    submit_selector: str,
    login_id: str,
    password: str,
    timeout_ms: int,
):
    """로그인 폼이 보이면 채워 제출하고, 폼이 사라질 때까지 기다린다.

    반환값:
        None  — 로그인 폼이 없음 (이미 로그인된 세션)
        True  — 로그인 성공 (폼이 hidden 됨)
        False — 제출 후에도 폼이 남아있음 (로그인 실패)

    keymedi/hmp 공통 패턴. URL 매칭이 아니라 폼 가시성으로 로그인 필요 여부를
    판단하고, 제출 직후 경쟁 상태를 피하려 폼이 hidden 될 때까지 대기한다
    (2026-07-06 keymedi 오판 사례에서 얻은 교훈).
    """
    id_input = page.locator(id_selector)
    try:
        id_input.first.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        return None

    id_input.first.fill(login_id)
    page.fill(pw_selector, password)
    page.click(submit_selector)
    try:
        id_input.first.wait_for(state="hidden", timeout=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        return False
