#!/usr/bin/env python3
"""
닥터빌 라이브 세미나 설문조사 자동 응답 스크립트.

seminar_live.py로 입장에 성공한 세미나는 방송 팝업에서 설문에 참여할 수 있다.
이 스크립트는 당일 입장 이력(scripts/state/seminar_entered.json)을 읽어 아직
설문하지 않은 세미나만 골라, 문제은행(survey_answers.json) 기반으로 응답한다.

용법:
    python3 seminar_survey.py                     # 두 계정 순회 (헤드리스)
    python3 seminar_survey.py --account bjh7790
    python3 seminar_survey.py --seminar-id 5473   # 상태 무시하고 특정 세미나만
    python3 seminar_survey.py --headed
    python3 seminar_survey.py --no-telegram

문제은행 (survey_answers.json, 세미나 구분 없는 단일 파일):
    { "<문항 텍스트>": "<보기 번호 또는 답변 텍스트>" }
    - 선택형: 값이 숫자만이면 1-based 보기 번호("2" = 두 번째 보기).
      숫자가 아니면 보기 텍스트에 부분 포함으로 "유일 매칭"될 때만 선택한다.
      복수 선택은 "1,3" 또는 ["1", "3"].
    - 입력형(주관식): 저장값을 그대로 입력한다.
    - 값이 빈 문자열("")이면 항상 미등록으로 취급한다.
    - 번호는 위치 기반이라 같은 문항이라도 세미나마다 보기 순서가 다르면 오답이
      될 수 있다. 순서가 흔들릴 만한 문항은 텍스트로 적어두는 편이 안전하다.

미등록 문항이 하나라도 있으면 그 페이지를 제출하지 않고 중단한다
(status=incomplete_bank). 설문은 페이지 순차 제출형이라 뒷 페이지는 앞 페이지를
제출해야 볼 수 있으므로, 페이지 단위 검증이 도달 가능한 최대 안전선이다.

DOM 근거 (2026-07-27 실측):
    방송 팝업: /seminar/broadcastSeminarPopup?viewType=2&seminarId=<ID>
      → a#surveyEnter("설문 참여") → button.btn_answer:has-text("설문하기")
      → survey.villeway.com 새 창(expect_popup)
    설문 폼:  form[id^="surveyForm"], 문항 li[data-question-number],
      문항 텍스트 = label > div 첫 줄, 보기 = ol li label 안의
      input[type=radio|checkbox] + span.col-start-2
    제출:     input[type=submit][value="제출하기"]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import common
import doctorville
import seminar_live
import daily_runner

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEOUT_MS = doctorville.DEFAULT_TIMEOUT_MS
DEFAULT_BANK_FILE = SCRIPT_DIR.parent / "survey_answers.json"
DEFAULT_STATE_FILE = SCRIPT_DIR / "state" / "seminar_entered.json"
BROADCAST_URL = "https://www.doctorville.co.kr/seminar/broadcastSeminarPopup?viewType=2&seminarId={sid}"
MAX_PAGES = 10  # 무한 루프 방지 (실측 설문은 1~2페이지)


# ---------------------------------------------------------------------------
# 순수 함수 (테스트 대상)
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_question(text: str) -> str:
    """문항 텍스트를 문제은행 키 형태로 정규화한다.

    화면 텍스트에는 `[퀴즈]` 배지와 필수 표시 `*`가 붙는데, 같은 문항이 세미나에
    따라 배지 유무만 다르게 나오는 경우가 있어 둘 다 제거하고 키로 삼는다.
    """
    t = normalize(text)
    t = re.sub(r"^\[퀴즈\]\s*", "", t)
    return t.rstrip("*").strip()


def load_bank(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def lookup_answer(bank: dict, question: str):
    """문제은행에서 문항의 답을 찾는다. 미등록이면 None.

    빈 문자열·빈 리스트는 "채워 넣기 대기 중"이므로 미등록으로 취급한다.
    """
    value = bank.get(normalize_question(question))
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return items or None
    return None


def match_option(answer: str, options: list[str]) -> int | None:
    """저장값에 해당하는 보기 인덱스. 판정 불가면 None.

    저장값이 숫자만이면 **1-based 보기 번호**로 해석한다("2" = 두 번째 보기).
    그 외에는 보기 텍스트에 부분 포함으로 유일 매칭될 때만 인정한다.

    번호 방식은 위치 기반이라, 같은 문항이라도 세미나에 따라 보기 순서가 다르면
    엉뚱한 보기를 고른다. 순서가 흔들릴 가능성이 있는 문항은 텍스트로 적어둘 것.
    """
    a = normalize(answer)
    if not a:
        return None
    if a.isdigit():
        idx = int(a) - 1
        return idx if 0 <= idx < len(options) else None
    norm = [normalize(o) for o in options]
    exact = [i for i, o in enumerate(norm) if o == a]
    if len(exact) == 1:
        return exact[0]
    hits = [i for i, o in enumerate(norm) if a in o]
    return hits[0] if len(hits) == 1 else None


def resolve_page(questions: list[dict], bank: dict) -> tuple[list[dict], list[dict]]:
    """페이지의 문항들을 문제은행과 대조해 (적용계획, 미등록문항)을 만든다."""
    plan, missing = [], []
    for q in questions:
        text = q.get("question", "")
        answer = lookup_answer(bank, text)
        options = [normalize(o["text"]) for o in q.get("options", [])]

        if answer is None:
            missing.append({
                "question": normalize_question(text),
                "options": [f"{i + 1}. {o}" for i, o in enumerate(options)],
            })
            continue

        if q.get("kind") == "input":
            if isinstance(answer, list):
                answer = " ".join(answer)
            plan.append({"kind": "input", "name": q["name"], "value": answer})
            continue

        # 복수 선택은 리스트(["1", "3"])뿐 아니라 "1,3" 형태도 받는다.
        if isinstance(answer, str) and "," in answer:
            parts = [p.strip() for p in answer.split(",")]
            answer = parts if all(p.isdigit() for p in parts if p) else answer
        wanted = answer if isinstance(answer, list) else [answer]
        indices = []
        for w in wanted:
            idx = match_option(w, options)
            if idx is None:
                indices = None
                break
            indices.append(idx)
        if indices is None:
            missing.append({
                "question": normalize_question(text),
                "options": [f"{i + 1}. {o}" for i, o in enumerate(options)],
            })
            continue
        plan.append({
            "kind": "choice",
            "targets": [q["options"][i] for i in indices],
        })
    return plan, missing


def add_missing_to_bank(bank_path: str | Path, missing: list[dict]) -> int:
    """미등록 문항을 빈 값으로 문제은행에 추가한다. 추가된 개수 반환."""
    bank_path = Path(bank_path)
    bank = load_bank(bank_path)
    added = 0
    for m in missing:
        key = m["question"]
        if key not in bank:
            bank[key] = ""
            added += 1
    if added:
        from telegram_inbox import write_json_atomic
        write_json_atomic(bank_path, dict(sorted(bank.items())))
    return added


def pending_seminar_ids(state: dict, account: str) -> list[int]:
    """당일 입장했으나 아직 설문하지 않은 세미나 ID 목록."""
    acc = (state or {}).get("accounts", {}).get(account, {})
    done = set(acc.get("survey_done", []))
    return [sid for sid in acc.get("entered", []) if sid not in done]


def mark_survey_done(state: dict, account: str, seminar_id: int | str, path=None) -> None:
    acc = state.setdefault("accounts", {}).setdefault(account, {})
    done = acc.setdefault("survey_done", [])
    sid = int(seminar_id)
    if sid not in done:
        done.append(sid)
    if path is not None:
        seminar_live.save_state(state, path)


# ---------------------------------------------------------------------------
# 브라우저 동작
# ---------------------------------------------------------------------------

def read_questions(survey_page) -> list[dict]:
    """현재 설문 페이지의 문항·보기·입력란을 읽는다."""
    return survey_page.evaluate(
        """() => Array.from(document.querySelectorAll('li[data-question-number]')).map(li => {
            const head = li.querySelector('label > div');
            const question = head ? (head.innerText || '').split('\\n')[0] : '';
            const options = Array.from(li.querySelectorAll('input[type=radio], input[type=checkbox]')).map(inp => {
                const lbl = inp.closest('label');
                const span = lbl ? lbl.querySelector('span') : null;
                // 만족도 척도형 문항은 보기 텍스트가 input을 감싼 label이 아니라
                // 같은 id를 가리키는 별도 label[for]에 들어 있다.
                let text = span ? span.innerText : '';
                if (!(text || '').trim() && inp.id) {
                    const outer = document.querySelector('label[for="' + inp.id + '"]:not(:has(input))');
                    if (outer) text = outer.innerText;
                }
                return { text, name: inp.name, value: inp.value, type: inp.type };
            });
            const free = li.querySelector('textarea, input[type=text]');
            return {
                number: li.getAttribute('data-question-number'),
                question,
                kind: options.length ? 'choice' : (free ? 'input' : 'unknown'),
                name: free ? free.name : (options[0] || {}).name || '',
                options,
            };
        })"""
    )


def dismiss_alerts(survey_page, max_rounds: int = 3) -> list[str]:
    """설문 창의 headlessui 모달(알림)을 닫는다. 닫은 메시지 목록을 반환.

    임시저장 초안이 있으면 "작성 중인 정보를 불러왔습니다" 알림이 뜨는데, 이 모달의
    backdrop이 포인터 이벤트를 가로채 제출 버튼 클릭이 타임아웃된다(2026-07-28 실측).
    """
    closed = []
    for _ in range(max_rounds):
        # 모달 루트는 크기가 0이라 is_visible()이 False다. 존재 여부로만 판단한다.
        dialog = survey_page.locator('[role="dialog"][data-headlessui-state="open"]')
        if dialog.count() == 0:
            break
        text = normalize(dialog.first.inner_text())
        btn = dialog.first.locator('button:has-text("확인"), button:has-text("닫기")')
        if btn.count() == 0:
            btn = dialog.first.locator("button")
        if btn.count() == 0:
            break
        btn.first.click()
        survey_page.wait_for_timeout(1000)
        closed.append(text)
    return closed


def apply_plan(survey_page, plan: list[dict]) -> None:
    for step in plan:
        if step["kind"] == "input":
            survey_page.locator(f'[name="{step["name"]}"]').first.fill(step["value"])
            continue
        for t in step["targets"]:
            survey_page.locator(
                f'input[name="{t["name"]}"][value="{t["value"]}"]'
            ).first.check(force=True)


def open_survey(page, seminar_id) -> tuple[object, str]:
    """방송 팝업에서 설문 창을 연다. (설문 페이지, 실패 사유) 중 하나를 반환."""
    common.goto_with_retry(
        page, BROADCAST_URL.format(sid=seminar_id), wait_until="domcontentloaded", timeout_ms=DEFAULT_TIMEOUT_MS
    )
    page.wait_for_timeout(3000)

    enter = page.locator("a#surveyEnter")
    if enter.count() == 0 or not enter.first.is_visible():
        return None, "설문 참여 버튼이 없음(설문 미제공 또는 종료)."
    enter.first.click()
    page.wait_for_timeout(2000)

    # 개인정보 활용 동의 안내 레이어 — 정책상 항상 동의한다.
    start = page.locator('button.btn_answer:has-text("설문하기")')
    if start.count() == 0:
        return None, "설문 안내 레이어에서 '설문하기' 버튼을 찾지 못함."
    try:
        with page.expect_popup(timeout=DEFAULT_TIMEOUT_MS) as popup_info:
            start.first.click()
        survey_page = popup_info.value
    except PlaywrightTimeoutError:
        return None, "설문 창(팝업)이 열리지 않음 — 이미 참여했거나 마감되었을 수 있음."

    # 제출 confirm이 뜨는 경우 Playwright 기본값은 자동 취소(dismiss)라 제출이
    # 조용히 무산된다(intermd.py에서 실측된 문제). 설문은 항상 수락한다.
    survey_page.on("dialog", lambda d: d.accept())
    survey_page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    survey_page.wait_for_timeout(5000)
    dismiss_alerts(survey_page)
    return survey_page, ""


def run_survey(page, seminar_id, bank_path: Path) -> dict:
    """세미나 1건의 설문을 처리한다."""
    result = {"seminarId": int(seminar_id), "status": "failed", "message": ""}
    survey_page, err = open_survey(page, seminar_id)
    if survey_page is None:
        result["status"] = "no_questions"
        result["message"] = err
        return result

    try:
        pages_done = 0
        for _ in range(MAX_PAGES):
            questions = read_questions(survey_page)
            if not questions:
                if pages_done:
                    result["status"] = "success"
                    result["pages"] = pages_done
                    result["message"] = f"설문 제출 완료({pages_done}페이지)."
                else:
                    result["status"] = "no_questions"
                    result["message"] = "설문 창에 문항이 없음."
                return result

            bank = load_bank(bank_path)
            plan, missing = resolve_page(questions, bank)
            if missing:
                added = add_missing_to_bank(bank_path, missing)
                result["status"] = "incomplete_bank"
                result["missing"] = missing
                result["message"] = (
                    f"{pages_done + 1}페이지에 미등록 문항 {len(missing)}건 — 제출하지 않음"
                    f"(survey_answers.json에 {added}건 빈 값 추가)."
                )
                return result

            apply_plan(survey_page, plan)
            dismiss_alerts(survey_page)
            submit = survey_page.locator('input[type=submit][value="제출하기"]')
            if submit.count() == 0:
                result["message"] = f"{pages_done + 1}페이지에서 제출 버튼을 찾지 못함."
                result["screenshot"] = common.save_screenshot(survey_page, f"survey_{seminar_id}_nosubmit")
                return result
            submit.first.click()
            survey_page.wait_for_timeout(5000)
            pages_done += 1

            if not survey_page.is_closed():
                dismiss_alerts(survey_page)

            if survey_page.is_closed():
                result["status"] = "success"
                result["pages"] = pages_done
                result["message"] = f"설문 제출 완료({pages_done}페이지, 창 자동 종료)."
                return result

        result["message"] = f"페이지가 {MAX_PAGES}회를 넘어 중단."
        return result
    finally:
        try:
            if not survey_page.is_closed():
                survey_page.close()
        except Exception:
            pass


def run_account(
    account: str,
    credentials_path: Path,
    bank_path: Path,
    headless: bool,
    seminar_ids: list,
    state: dict = None,
    state_file: Path = None,
) -> dict:
    output = {"site": "doctorville_survey", "account": account, "status": "skipped", "surveys": []}

    if not seminar_ids:
        output["message"] = "설문 대상 세미나 없음."
        return output

    try:
        creds = doctorville.load_credentials(credentials_path, account)
    except KeyError as e:
        output["status"] = "failed"
        output["message"] = str(e)
        return output

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale="ko-KR", ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            page.goto(doctorville.ATTEND_URL, wait_until="load")
            if not doctorville.ensure_logged_in(page, creds):
                output["status"] = "failed"
                output["message"] = "로그인 실패"
                return output

            for sid in seminar_ids:
                # 한 세미나의 실패가 나머지를 막지 않도록 개별적으로 감싼다.
                try:
                    r = run_survey(page, sid, bank_path)
                except Exception as e:
                    r = {"seminarId": int(sid), "status": "failed", "message": f"예외 발생: {e}"}
                output["surveys"].append(r)
                if r["status"] == "success" and state is not None:
                    mark_survey_done(state, account, sid, state_file)

            statuses = [r["status"] for r in output["surveys"]]
            output["status"] = "failed" if "failed" in statuses else "success"
            output["message"] = (
                f"성공 {statuses.count('success')}건, 미등록 {statuses.count('incomplete_bank')}건, "
                f"설문없음 {statuses.count('no_questions')}건, 실패 {statuses.count('failed')}건."
            )
        except Exception as e:
            output["status"] = "failed"
            output["message"] = f"예외 발생: {e}"
            output["screenshot"] = common.save_screenshot(page, f"survey_{account}")
        finally:
            browser.close()

    return output


# ---------------------------------------------------------------------------
# 텔레그램 포맷
# ---------------------------------------------------------------------------

STATUS_LABEL = {
    "success": "✅",
    "incomplete_bank": "❓",
    "no_questions": "⏭️",
    "already_done": "☑️",
    "skipped": "⏭️",
    "failed": "❌",
}


def format_telegram_message(results: dict, date_str: str) -> str:
    lines = [f"📝 *세미나 설문조사* ({date_str})", ""]
    missing_all = []
    for account, r in results.items():
        emoji = STATUS_LABEL.get(r.get("status", "failed"), "❓")
        lines.append(f"*{account}* {emoji} {r.get('message', '')}")
        for s in r.get("surveys", []):
            e = STATUS_LABEL.get(s.get("status", "failed"), "❓")
            lines.append(f"  세미나 {s['seminarId']}: {e} {s.get('message', '')}")
            for m in s.get("missing", []):
                missing_all.append(m)
    if missing_all:
        lines.append("")
        lines.append("⚠️ *설문 정답 추가 필요* (`survey_answers.json`)")
        for m in missing_all:
            lines.append(f"• {m['question']}")
            for o in m["options"]:
                lines.append(f"    - {o}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="닥터빌 세미나 설문조사 자동 응답")
    parser.add_argument("--account", default="all", choices=["all", "bjh7790", "wonju"])
    parser.add_argument("--credentials", default=str(SCRIPT_DIR.parent / "credentials.json"))
    parser.add_argument("--bank-file", default=str(DEFAULT_BANK_FILE), help="survey_answers.json 경로")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="seminar_entered.json 경로")
    parser.add_argument("--seminar-id", action="append", help="상태 무시하고 특정 세미나만 처리(반복 지정 가능)")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    kst = timezone(timedelta(hours=9))
    date_str = datetime.now(kst).strftime("%Y-%m-%d")
    accounts = ["bjh7790", "wonju"] if args.account == "all" else [args.account]

    state = None
    state_file = None
    if not args.seminar_id:
        state_file = Path(args.state_file)
        if not state_file.exists():
            print(json.dumps(
                {"site": "doctorville_survey", "status": "skipped", "message": "입장 이력 파일 없음 — 설문 대상 없음."},
                ensure_ascii=False,
            ))
            sys.exit(0)
        state = seminar_live.load_state(state_file, date_str)

    results = {}
    for account in accounts:
        ids = args.seminar_id if args.seminar_id else pending_seminar_ids(state, account)
        results[account] = run_account(
            account,
            Path(args.credentials),
            Path(args.bank_file),
            headless=not args.headed,
            seminar_ids=ids,
            state=state,
            state_file=state_file,
        )
        print(json.dumps(results[account], ensure_ascii=False))

    print("\n=== 최종 결과 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    if not args.no_telegram and any(r.get("surveys") for r in results.values()):
        daily_runner.load_telegram_credentials(args.credentials)
        ok = daily_runner.send_telegram(format_telegram_message(results, date_str))
        print(f"[telegram] {'성공' if ok else '실패'}")

    sys.exit(1 if any(r.get("status") == "failed" for r in results.values()) else 0)


if __name__ == "__main__":
    main()
