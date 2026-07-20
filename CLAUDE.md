# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드다.

## 프로젝트 개요

의료 포털(닥터빌·키메디·HMP) 일일 자동화 루틴.
- 출석체크 / 오늘의 퀴즈 / 세미나 신청을 매일 자동 처리
- **GitHub Actions cron으로 무인 실행** (`.github/workflows/daily.yml` → `scripts/daily_runner.py`)
- 모든 사이트를 Playwright(헤드리스 Chromium) 스크립트로 조작 — 더 이상 브라우저 MCP나 로컬 수동 실행에 의존하지 않는다
- 실행 결과는 텔레그램 봇으로 요약 전송
- 작업 중 새로 알게 된 사항은 `MEMORY.md`에 기록

> **아키텍처 전환 (2026-07-14):** 과거에는 Claude in Chrome MCP / Desktop Commander로 반자동 실행했으나, 현재는 GitHub Actions에서 완전 무인 실행한다. 과거 방식 기록은 이 문서 맨 아래 "과거 실행 방식(이력용)"과 `MEMORY.md`에 남겨두었다.

---

## 실행 아키텍처

```
GitHub Actions (매일 08:01 KST, cron)
  └─ .github/workflows/daily.yml
       ├─ pip install -r requirements.txt + playwright install chromium
       ├─ secrets.CREDENTIALS_JSON → credentials.json 생성
       └─ python3 scripts/daily_runner.py
            ├─ [1/4] scripts/keymedi.py      (bjh7790)
            ├─ [2/4] scripts/hmp.py          (bjh7790)
            ├─ [3/4] scripts/doctorville.py  --account bjh7790
            ├─ [4/4] scripts/doctorville.py  --account wonju
            └─ 결과 요약 → 텔레그램 전송
```

- 각 사이트 스크립트는 결과를 **한 줄(또는 indent) JSON**으로 stdout에 출력한다.
- `daily_runner.py`가 이를 파싱해 취합하고 텔레그램 메시지로 포맷한다.
- 서브프로세스는 `sys.executable`(현재 인터프리터)로 실행 — 로컬 venv·CI 전역 pip 양쪽에서 동일하게 동작한다. **venv 절대경로를 하드코딩하지 않는다.**
- 실패 항목이 하나라도 있으면 `daily_runner.py`는 exit 1로 종료(Actions job 실패 표시), 텔레그램 전송은 성공/실패와 무관하게 항상 수행된다.

### 공용 모듈 `scripts/common.py`
keymedi/hmp/doctorville가 공유하는 헬퍼:
- `read_credentials(path)` — credentials.json 로드
- `save_screenshot(page, name_stem)` — 실패 시 `scripts/logs/`에 스크린샷 저장
- `form_login(page, id_sel, pw_sel, submit_sel, id, pw, timeout)` — keymedi/hmp 공통 폼 로그인 (폼 가시성으로 판단, 제출 후 폼이 hidden 될 때까지 대기)

---

## 계정 범위

| 계정 | 닥터빌 | 키메디 | HMP |
|---|---|---|---|
| `bjh7790@gmail.com` (백승진) | 출석+퀴즈+세미나 | 출석 | 캡슐 출석 |
| `wonju1119@naver.com` (정원주, 병리과) | 출석+퀴즈+세미나 | ❌ | ❌ |

---

## 일일 자동화 항목

| 사이트 | 계정 | 작업 | 포인트 | 스크립트 |
|---|---|---|---|---|
| 닥터빌 | bjh7790, wonju | 출석체크 | 100P | `doctorville.py --task attend` |
| 닥터빌 | bjh7790, wonju | 오늘의 퀴즈 | 500P | `doctorville.py --task quiz` |
| 닥터빌 | bjh7790, wonju | 세미나 신청 | — | `doctorville.py --task seminar` |
| 키메디 | bjh7790 | 출석 | 100P | `keymedi.py` |
| HMP | bjh7790 | 캡슐 출석 | 10캡슐 | `hmp.py` |
| HMP | bjh7790 | 지식커뮤니티 댓글 | 지식내공 | `hmp.py` (내장) |
| HMP | bjh7790 | 지식커뮤니티 글쓰기 | 지식내공 | `hmp.py` (내장) |

**HMP 룰렛(연속 10·20·30일) 자동화는 `hmp.py`에 구현되어 있다(2026-07-14~).** 참여 시 뜨는 확인 팝업(`.pop.cont`) 처리를 포함한 흐름은 `hmp.py` 상단 주석과 `MEMORY.md` 참조.

---

## credentials.json 형식

로컬 전용, gitignore 대상. GitHub Actions에서는 `CREDENTIALS_JSON` secret으로 주입한다.

```json
{
  "telegram": { "bot_token": "...", "chat_id": "..." },
  "bjh7790": {
    "email": "bjh7790@gmail.com",
    "doctorville": { "password": "..." },
    "keymedi":     { "id": "bjh7790", "password": "..." },
    "hmp":         { "password": "..." }
  },
  "wonju": {
    "email": "wonju1119@naver.com",
    "doctorville": { "password": "..." }
  }
}
```

- 닥터빌 로그인 id는 계정의 `email`, 비밀번호는 `doctorville.password`.
- 키메디는 `keymedi.id`(이메일 아님, 예: "bjh7790") + `keymedi.password`.
- HMP는 `hmp.password`만 있으면 되고, `id`가 없으면 **계정 키 자체("bjh7790")를 로그인 id로 사용**한다.

---

## GitHub Actions 배포

### Secrets (Repo → Settings → Secrets → Actions)
| Secret | 내용 |
|---|---|
| `CREDENTIALS_JSON` | `credentials.json` 전체 내용(JSON string) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 수신 chat id |

> 텔레그램 토큰/chat_id는 `CREDENTIALS_JSON` 안에도 있지만, 워크플로우는 별도 env로도 주입한다. `daily_runner.py`는 환경변수를 우선 사용하고 없으면 credentials.json에서 읽는다.

### 스케줄 / 수동 실행
- cron: `1 23 * * *` (UTC 23:01 = KST 08:01)
- 수동 실행: Actions 탭 → "일일 의료 포털 자동화" → **Run workflow**
- 실패 시 `scripts/logs/`의 스크린샷이 artifact로 업로드됨(7일 보관).

---

## 로컬 실행 (디버깅)

macOS Homebrew Python은 PEP 668로 전역 pip 설치를 막으므로 venv 사용:

```bash
cd ~/Desktop/DocAuto
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
deactivate
```

이후 실행 (venv python 절대경로 직접 호출):
```bash
# 전체 루틴 (텔레그램 전송 포함)
venv/bin/python3 scripts/daily_runner.py
venv/bin/python3 scripts/daily_runner.py --no-telegram   # 전송 생략
venv/bin/python3 scripts/daily_runner.py --headed        # 브라우저 창 표시

# 개별 사이트
venv/bin/python3 scripts/keymedi.py --headed
venv/bin/python3 scripts/hmp.py --headed
venv/bin/python3 scripts/doctorville.py --account bjh7790 --task quiz --headed
```

첫 실행이나 셀렉터 변경 의심 시 반드시 `--headed`로 눈으로 확인할 것.

---

## Claude의 역할

무인 실행이므로 일상적으로 개입하지 않는다. Claude가 할 일:
1. **퀴즈 정답 추가** — 텔레그램에 "정답 추가 필요" 알림이 오면 `quiz_answers.json`에 해당 제품 정답을 추가.
2. **실패 디버깅** — 텔레그램 실패 메시지 + Actions artifact 스크린샷을 보고 원인 진단 후 스크립트 수정.
3. **HMP 룰렛 수동 확인 안내** — 연속 출석일수가 10의 배수에 근접하면 사용자에게 안내.
4. 미지원 퀴즈 제품은 **시도하지 않는다** — 스크립트가 `no_answer`로 처리하고 알림을 보냄.

---

## 퀴즈 정답 형식 (문제은행 방식, 2026-07-19~)

파일: `quiz_answers.json`

```json
{
  "우루사": {
    "담석 예방 목적으로 체중 감소 중 우루사(UDCA)를 처방할 수 있는 근거로 적절한 것은?": "UDCA는 담즙 내 콜레스테롤 농도를 낮춰 담석 생성을 억제한다.",
    "다음 중 체중감소로 인한 담석 생성 예방을 위한 우루사(UDCA) 사용 권고 용량으로 가장 적절한 것은?": "300mg 하루 2회"
  },
  "제품명": {}
}
```

- **이전 방식(보기 번호 시퀀스 문자열, 예: `"111"`)은 폐기됨(2026-07-19).** 같은 제품이라도 날짜마다 문항 수·순서가 다르고, "커뮤니티에 정답 공유 시 패널티" 경고로 보아 보기 순서도 사용자별로 섞일 가능성이 높아 위치 기반 매칭은 근본적으로 안전하지 않음.
- 정답은 **문항 텍스트 → 정답 보기 텍스트**의 문제은행(dict)으로 저장한다. 위치(Q1/Q2/…)나 보기 번호에 의존하지 않고, 실행 시점에 화면에 렌더링된 문항·보기 텍스트를 그대로 조회해 매칭한다.
- 문항 텍스트는 `.txt_question`, 보기 텍스트는 `.question_choice label`에서 추출(공백 정규화 후 비교).
- 제품이 없거나, 제품은 있으나 오늘 문항의 텍스트가 은행에 없거나, 기록된 정답 텍스트가 오늘 보기 중 어느 것과도 일치하지 않으면 → 시도 금지 + `no_answer` 반환. 이때 텔레그램 알림 메시지에 **오늘 실제 문항/보기 텍스트 전체가 JSON으로 포함**되므로, 그대로 복사해 `quiz_answers.json`에 정답만 채워 넣으면 된다.
- O/X 문항도 동일 원칙: 저장값은 실제 보기 라벨 텍스트("O"/"X" 등 화면 표기 그대로).
- pId·문항수는 매일 바뀌므로 "오늘의 퀴즈" 카드 → 제품 상세 경로로 동적 탐색
- **탐색 경로(2026-07-20 수정):** `/product/main` → 이달의 퀴즈 캘린더(`.quiz_calender`) → 오늘 날짜 다음 줄에서 제품명 추출 + 오늘 셀(`td.today`) 내 hidden input `.pIdCls`에서 pId 직접 추출 → 상세(`/product/productView?pId=XXX`). **`/product/medicineList`에서 이름으로 검색하던 이전 방식은 폐기.** medicineList는 의약품 전용 목록이라 모비케어 같은 의료기기(`/product/instrumentList` 카테고리)는 등록돼 있지 않아 pId 조회 실패 → 퀴즈 시도 자체가 안 됨(`failed: medicineList에서 pId를 찾지 못함`). 캘린더 셀의 `pIdCls`는 카테고리와 무관하게 항상 존재해 더 안정적. medicineList 검색은 폴백으로만 유지.
- 퀴즈 레이어 DOM(`.question_area` 반복 구조, 2026-07-19 확인): 문항당 `<span class="questionN">QN</span><p class="txt_question">...</p><ul class="question_choice"><li><input name="an_N" value="V"><label>보기텍스트</label></li>...</ul>`, 실제 문항 수는 hidden input `#questionCnt`로도 확인 가능.

---

## 사이트별 셀렉터 요약

셀렉터의 상세 확인 근거와 수정 이력은 각 스크립트 상단 docstring과 `MEMORY.md` 참조.

### 닥터빌 (doctorville.py)
- 로그인: 인트로(`/intro`) → `a[href*="mims-account.shop.co.kr"][href*="/login"]` 추출 → mims 로그인(`input[name="identifier"]`, `input[type="password"]`, `button[type="submit"]:has-text("로그인")`)
- 퀴즈 레이어: `#quizLayerPop` / 라디오 `input[name="an_N"][value="V"]` / 제출 `.btn_answer` / 완료 시 레이어 내 "축하드립니다" 텍스트(→ already_done) / 닫기 `.btn_cancel`
- 세미나 목록: `span.ico_apply` → `a.list_detail`의 `seminarId`
- 세미나 신청: `/seminar/seminarDetail?seminarId=XXXX` → `a.btn_bn`("신청하기") → 개인정보 동의 `button.btn_confirm`

### 키메디 (keymedi.py)
- 로그인: `input[name="uid"]`, `input[name="password"]`, `button:has-text("로그인")`
- 출석: 미출석 "출석체크하기" / 완료 "출석완료" (텍스트로만 구분) — **"출석체크하기"를 먼저 확인**(달력형 페이지에 과거 "출석완료"가 여러 개 존재해 오판 위험)
- 광고 팝업: "광고보고 출석하기" 클릭 필수(안 누르면 미지급, 새 탭 뜰 수 있음)
- 완료 모달: "출석체크가 완료되었습니다" + "확인"

### HMP (hmp.py)
- 로그인: `input[name="memId"]`, `input[name="passwd"]`, `button.btn_login:has-text("로그인")`
- 캡슐 버튼: 신 UI "오늘의 캡슐 받기" 텍스트 / 구 UI `#capsuleBtn`(미완료)·`#capsuleBtnComplete`(완료) — **가시성(is_visible)으로 판단**
- 완료 팝업: `[id="10rewardPopup"]` 내부 "확인" (id가 숫자로 시작해 `[id="..."]` 속성 셀렉터 필요)
- **댓글 (`_run_comment`):** `a[onclick*="goDetail"]` 첫 번째 → boardSeq 추출 → `knowCommBoardDetail.hm?boardSeq=XXXX` → `textarea[name="cmtCntnt"]` "감사합니다" → `form.cmtForm button[onclick*="saveCmt"]` → confirm 수락 → alert "저장 완료". already_done: `#cmtDiv .cmtName` 중 내 닉네임(`form.cmtForm span` 첫 번째) 존재 시.
- **글쓰기 (`_run_post`):** `button.btnWrite` → `#writePopupDiv` → `#_topicNm` 클릭(드롭다운) → `input[name="topicGbn"][value="TOPIC_13"]`(여행/취미) → `#title` "오늘도 화이팅" → `iframe#innoditor_0` body + `#innoditorSource_0` textarea에 `{요일}요일이네요. 다들 화이팅하세요.` → `#tag` "화이팅" Enter → `.botSubmit button[onclick*="saveBoard"]` → confirm → alert "게시글이 작성 완료 됐습니다.". already_done 체크 없음.
- **GitHub Actions headed 실행:** `xvfb-run -a python3 scripts/daily_runner.py --headed` (Xvfb 가상 디스플레이 필요, workflow에서 `sudo apt-get install -y xvfb` 선행)

---

## 닥터빌 세미나 신청 DOM 패턴

신청가능 세미나 추출:
```js
Array.from(document.querySelectorAll('span.ico_apply')).map(span => {
  const aEl = span.closest('a.list_detail');
  return { seminarId: new URL(aEl.href).searchParams.get('seminarId'), title: aEl.innerText.trim() };
})
```

신청 흐름 (각 seminarId마다 반복):
1. `/seminar/seminarDetail?seminarId=XXXX` 이동
2. `a.btn_bn` 텍스트가 "신청하기"이면 클릭
3. `button.btn_confirm` 출현 시 클릭 (개인정보 동의)
4. `a.btn_bn` 텍스트가 "신청취소"로 바뀌면 완료

---

## 라이브 세미나 수동 입장 (2026-07-20~)

**daily 루틴과 무관한 수동 전용 기능.** `.github/workflows/seminar_live.yml`을 Actions 탭에서
**Run workflow**로 직접 실행할 때만 동작하며, cron에는 포함되지 않는다.

- 스크립트: `scripts/seminar_live.py`
- 동작: `/seminar/main`에서 현재 "입장하기"가 뜬(=신청 완료 + 방송 중) 라이브 세미나를 모두 찾아,
  각 세미나 상세 페이지에서 입장 → 팝업 창(스트리밍 화면)에서 `--stay-seconds`초(기본 20초) 대기 → 팝업 닫기를 반복.
- 계정: `--account all|bjh7790|wonju` (기본 all = 두 계정 순회). wonju도 닥터빌 세미나 신청을 하므로 포함.
- 결과는 `daily_runner.py`와 별개로 텔레그램에도 전송(`--no-telegram`으로 생략 가능).

### DOM 근거 (2026-07-20, 로그인된 실제 세션에서 확인)
- `/seminar/main` 목록의 입장 가능 마커: `span.ico_enter` (신청 가능 마커 `span.ico_apply`와 동일 구조/위치) →
  `closest('a.list_detail').href`의 `seminarId` 추출.
- 세미나 상세(`/seminar/seminarDetail?seminarId=X`)의 입장 버튼: `a.btn_bn.btn_enter`, 텍스트 "입장하기",
  `onclick="playOnPopup(...)"` — 내부에서 `window.open()`을 호출해 새 창(팝업)으로 스트리밍 화면을 띄운다.
  Playwright `page.expect_popup()`으로 캐치.
- 목록에 있어도 방문 시점에 방송이 끝났거나 아직 시작 전이면 상세 페이지에 `a.btn_bn.btn_enter`가 없을 수 있음 →
  `skipped` 처리 후 다음 세미나로 진행.
- **실제 클릭까지는 검증하지 않음** — 탐색 단계에서 사용자 시청 이력에 영향 줄 수 있어 중단. 첫 실행은 반드시
  `--headed`(로컬) 또는 Actions artifact 스크린샷으로 팝업 진입/종료가 정상인지 확인할 것.

---

## 개인정보 동의 정책

세미나 신청 시 "개인정보 활용 동의" 모달 → **항상 동의**(`button.btn_confirm`).
(성함·근무형태·진료과·근무처·이메일 제3자 제공, 12개월 보유 — 사용자 사전 승인)

---

## 결과 상태값 (JSON status)

| status | 의미 | 텔레그램 |
|---|---|---|
| `success` | 완료(포인트 적립) | ✅ |
| `already_done` | 오늘 이미 완료 | ☑️ |
| `skipped` | `--task` 옵션으로 건너뜀 | ⏭️ |
| `no_answer` | 퀴즈 정답 미등록(미시도) | ❓ |
| `failed` | 예상치 못한 오류 | ❌ |

닥터빌 결과는 `{attend, quiz, seminar}` 중첩 구조, 키메디·HMP는 flat 구조다. 스크립트가 통째로 실패하면(실행 예외·타임아웃) 중첩 키 없이 top-level `{status:"failed", message}`만 반환하며, `daily_runner.py`는 이 경우도 ❌로 정확히 표시한다.

---

## 작업 후 기록 규칙

작업 완료 후 새로 알게 된 사항(UI 변경, 예외, 신규 패턴, 상태값 등)은 `MEMORY.md`에 추가.
반복 패턴이 굳어지면 이 CLAUDE.md에도 반영.

---

## 과거 실행 방식 (이력용, 현재 미사용)

아래는 GitHub Actions 전환 이전 방식이다. **더 이상 일일 루틴에서 사용하지 않는다.** 셀렉터 근거 등 참고 목적으로만 남긴다.

- **Claude in Chrome MCP** (`mcp__claude-in-chrome__*`): 닥터빌·HMP를 브라우저에서 직접 조작. 승진/원주 프로필 창을 각각 열어 처리. JS click()이 막히는 버튼(퀴즈 제출 등)은 `computer`로 좌표 클릭.
- **Desktop Commander** (`mcp__Desktop_Commander__start_process`): 사용자 Mac에서 keymedi.py/hmp.py를 직접 실행(외부망 접근 가능). 30초 timeout, 결과 JSON 수신.
- 이 방식들은 도메인 차단이 들쭉날쭉하고 토큰 소모가 커서 폐기하고 GitHub Actions 무인 실행으로 이관했다.
