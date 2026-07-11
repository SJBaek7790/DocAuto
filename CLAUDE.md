# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

의료 포털(닥터빌·키메디·HMP) 일일 자동화 루틴.
- 출석체크 / 오늘의 퀴즈 / 세미나 신청을 매일 자동 처리
- 닥터빌은 Claude in Chrome MCP로 브라우저 조작
- **키메디·HMP는 2026-07-07부터 `mcp__Desktop_Commander__start_process`로 Claude가 직접 실행** — `mcp__workspace__bash`는 외부망 차단으로 불가하나 Desktop Commander는 실제 Mac에서 실행되므로 가능함을 확인. 각각 `scripts/keymedi.py`, `scripts/hmp.py` (Playwright, venv 필요)
- 작업 중 새로 알게 된 사항은 `MEMORY.md`에 기록

---

## 계정 범위

| 계정 | 닥터빌 | 키메디 | HMP |
|---|---|---|---|
| `bjh7790@gmail.com` (백승진) | 출석+퀴즈+세미나 | 출석 | 출석 |
| `wonju1119@gmail.com` (정원주, 병리과) | 출석+퀴즈+세미나 | ❌ | ❌ |

---

## 일일 체크리스트

### bjh7790
- 닥터빌 출석체크 (100P) → `https://www.doctorville.co.kr/event/attend`
- 닥터빌 오늘의 퀴즈 (500P) → `quiz_answers.json` 참조 후 제출
- 닥터빌 세미나 신청 → `https://www.doctorville.co.kr/seminar/main` 에서 신청 가능한 세미나 전부 신청
- ~~키메디 출석 (100P)~~ → **Claude 담당 아님.** `scripts/keymedi.py`로 사용자가 직접 실행 (2026-07-06~). Claude는 일일 루틴에서 키메디를 건드리지 않는다. 사용자가 스크립트 실패를 알려오면 그때만 디버깅 지원.
- ~~HMP 캡슐 출석~~ → **Claude 담당 아님.** `scripts/hmp.py`로 사용자가 직접 실행 (2026-07-06~, 아직 실사용 검증 전). Claude는 일일 루틴에서 HMP를 건드리지 않는다. 룰렛 참여(연속 10·20·30일)는 스크립트 미구현 — 연속 출석일수가 10의 배수에 근접하면 사용자에게 수동 확인 안내.

### wonju
- 닥터빌 출석체크 (100P)
- 닥터빌 오늘의 퀴즈 (500P) → bjh7790과 동일 제품·정답
- 닥터빌 세미나 신청

---

## 퀴즈 정답 형식

파일: `quiz_answers.json`

```json
{
  "스피틴": "111",
  "제품명": "314"
}
```

- 숫자 시퀀스: Q1→첫째 자리, Q2→둘째 자리, … (보기 번호)
- O/X 문항: O=1, X=2
- 제품명이 매핑 표에 없으면 → 시도 금지 + 사용자에게 알림(정답 추가 요청)
- pId·문항수는 매일 바뀌므로 "오늘의 퀴즈" 카드 → QUIZ 배지 회사 → 제품 상세 경로로 동적 탐색
- 탐색 경로: `/product/main` → 이달의 퀴즈 섹션 → 오늘 날짜 제품명 확인 → `/product/medicineList`에서 해당 제품 링크 추출 → 상세 페이지(`/product/productView?pId=XXX`)
- 퀴즈 완료 여부: `#btn_quiz_banner`의 className에 `ico_finish` 포함 시 이미 완료
- 정답 선택: `input[name="an_N"][value="V"]` 클릭 후 **`정답 도전` 버튼은 반드시 `mcp__Claude_in_Chrome__computer`로 직접 클릭** (JS click() 타임아웃 발생)

---

## Chrome 프로필

- 프로필 **"승진"** → bjh7790@gmail.com (닥터빌 로그인 유지 — 키메디·HMP는 더 이상 이 Chrome 프로필로 처리하지 않음, Playwright 스크립트가 별도 크리덴셜로 로그인)
- 프로필 **"원주"** → wonju1119@gmail.com (닥터빌 로그인 유지)

계정 전환 절차 불필요. 작업 시 해당 프로필 창으로 전환 후 진행.

### Chrome MCP 브라우저 연결 방법
1. `list_connected_browsers` → 연결된 브라우저 목록 확인
2. `select_browser(deviceId)` → 해당 창으로 전환
3. `tabs_context_mcp(createIfEmpty: true)` → 탭 ID 확보
- 승진 프로필과 원주 프로필이 별도 Chrome 창으로 열려 있으면 각각 다른 deviceId로 표시됨

### HMP·키메디 로그인 (MCP, 참고용 — 더 이상 일일 루틴에서 사용 안 함)
- 자동완성 값이 JS에서 빈 문자열로 읽힘 → JS로 로그인 불가
- `mcp__Claude_in_Chrome__computer`로 스크린샷 확인 후 로그인 버튼 직접 클릭
- 키메디·HMP 모두 더 이상 MCP로 로그인하지 않음 — 아래 "키메디 스크립트 전환", "HMP 스크립트 전환" 참고. 이 항목은 과거 기록 참고용으로만 남겨둠.

---

## 개인정보 동의 정책

세미나 신청 시 "개인정보 활용 동의" 모달 → **항상 `동의합니다.` 클릭**.
(성함·근무형태·진료과·근무처·이메일 제3자 제공, 12개월 보유 — 사용자 사전 승인)
- JS 셀렉터: `button.btn_confirm` → `.click()`으로 자동 처리 가능

---

## HMP 캡슐 출석 상세 (과거 MCP 처리 방식, 참고용 — 2026-07-06부터 스크립트로 이관)

- 기본: 출석체크 버튼 클릭 (`https://www.hmp.co.kr/event/attendanceRouletteMain.hm`)
- 로그인 후 "오늘의 캡슐 받기" 버튼 → `mcp__Claude_in_Chrome__computer`로 클릭
- 완료 팝업: "[마일리지] 10 캡슐 적립 완료" → 확인 클릭
- 연속 10·20·30일 달성 시 룰렛 참여 버튼 활성화 → 활성화되어 있으면 룰렛도 클릭
- 연속 출석 일수 현황 → `MEMORY.md` 참조

현재는 `scripts/hmp.py`가 이 로직을 대체한다 (룰렛 제외 — 아래 "HMP 스크립트 전환" 참고). Claude가 일일 루틴에서 이 섹션의 절차를 다시 실행하지 않는다.

---

## 자동화 구현 원칙

- 브라우저 조작: Claude in Chrome MCP (`mcp__Claude_in_Chrome__*`)
- JS click()이 막히는 버튼(퀴즈 제출, 키메디·HMP 로그인 등)은 `mcp__Claude_in_Chrome__computer`로 직접 클릭
- 크리덴셜: `credentials.json` (로컬 전용, 버전 관리 제외)
- 미지원 퀴즈 제품 발견 시 → 시도 금지 + 사용자에게 즉시 알림(정답 추가 요청)
- 작업 결과(성공/실패/포인트)는 실행 후 요약 출력

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
2. `a.btn_bn` 텍스트가 "신청하기"이면 `.click()`
3. `button.btn_confirm` 출현 시 `.click()` (개인정보 동의)
4. `a.btn_bn` 텍스트가 "신청취소"로 바뀌면 완료
5. JS 타임아웃 발생 시 → 페이지 재진입 후 버튼 상태 재확인

## 키메디 스크립트 전환 (2026-07-06~)

키메디 출석은 더 이상 Claude in Chrome MCP로 처리하지 않는다. 매번 도메인 차단이 들쭉날쭉하고(하루는 되고 하루는 막힘), MCP 조작 자체가 스크린샷·DOM조회로 토큰을 많이 쓰기 때문에 `scripts/keymedi.py` (Playwright)로 이관했다. **이 작업은 사용자가 본인 Mac에서 직접 실행한다 — Claude가 대신 실행해주는 게 아니다** (Claude의 bash 사용막은 외부망이 허용목록으로 제한되어 있어 keymedi.com에 애초에 접근이 안 됨, 2026-07-05 확인).

### 셀렉터 (2026-07-05, 실제 로그인 세션에서 DOM 직접 조회로 확인)
- 로그인 폼: `input[name="uid"]`, `input[name="password"]`, 제출 버튼은 텍스트 "로그인"
- 출석 버튼: 미출석 시 텍스트 "출석체크하기", 출석 완료 시 텍스트 "출석완료"로 바뀜 (별도 class 없음, 텍스트로만 구분 가능)
- 광고 팝업: "광고보고 출석하기" 버튼 클릭 필수 (안 누르면 포인트 미지급) — 클릭 시 새 탭(광고)이 뜨는 경우가 있어 스크립트에서 별도 처리
- 완료 모달: "출석체크가 완료되었습니다. (100포인트 적립 완료!)" + "확인" 버튼

### 사용법 (venv 필수 — 2026-07-06 확정)
macOS Homebrew Python은 `externally-managed-environment`로 시스템 전역 pip 설치를 막는다 (PEP 668). `--break-system-packages`로 우회 가능하지만 매일 실행되는 개인 자동화 스크립트에는 venv가 더 안전 — 최초 1회만 설정:
```bash
cd ~/Desktop/DocAuto
python3 -m venv venv
source venv/bin/activate
pip install playwright
playwright install chromium
python3 scripts/keymedi.py --headed   # 최초 1회는 --headed로 눈으로 확인 권장
deactivate
```
이후 매일 실행 (activate 불필요, venv의 python 바이너리를 직접 호출):
```bash
~/Desktop/DocAuto/venv/bin/python3 ~/Desktop/DocAuto/scripts/keymedi.py
```
cron/launchd 등록 시에도 반드시 `venv/bin/python3` 절대경로를 사용할 것 — 시스템 `python3`로 등록하면 매번 `ModuleNotFoundError: No module named 'playwright'` 재발.

### 일일 루틴에서 Claude의 역할
**2026-07-07부터: `mcp__Desktop_Commander__start_process`로 Claude가 직접 실행.**
`timeout_ms=30000` (30초) 사용. 결과 JSON을 바로 수신해 해석·디버깅.
`credentials.json`의 `bjh7790.keymedi.id`/`password` 사용 (id는 이메일이 아니라 "bjh7790").

결과는 한 줄 JSON으로 stdout에 출력됨 (`status`: success/already_done/failed). 이 스크립트는 에이전트 샌드박스에서 실제 로그인까지 end-to-end 테스트하지 못했음 — 샌드박스 자체가 브라우저 실행 의존성(libXdamage 등)도 없고 keymedi.com 접근도 안 됐기 때문. 첫 실행에서 실패하면 `--headed`로 재실행해서 어느 단계에서 막히는지 확인 필요.

**2026-07-06 검증 완료.** venv 설정 → 로그인 감지 로직 2회 수정(URL 매칭 → 폼 가시성 체크 → 클릭 후 경쟁 상태로 오판하던 것을 hidden 대기로 수정) 후 실제로 `{"status": "success", "points": 100}` 확인됨. 앞으로 실패하면 이 세 가지 수정 이력을 먼저 참고할 것.

---

## HMP 스크립트 전환 (2026-07-06~)

키메디와 동일한 이유(도메인 차단 들쭉날쭉 + MCP 토큰 소모)로 HMP 캡슐 출석도 `scripts/hmp.py` (Playwright)로 이관했다. **이 작업도 사용자가 본인 Mac에서 직접 실행한다.** keymedi.py와 같은 venv를 그대로 재사용— 별도 venv 불필요.

### 셀렉터 (2026-07-06, 실제 로그인 세션에서 DOM 직접 조회로 확인)
- 로그인 폼: `input[name="memId"]`, `input[name="passwd"]`, 제출 버튼 `button.btn_login` (텍스트 "로그인"). 페이지: `https://www.hmp.co.kr/login/loginForm.hm`. 키메디와 달리 미로그인 시 실제로 `/login/loginForm.hm`으로 리다이렉트되지만, 폼 가시성 체크 방식을 그대로 적용해 더 견고하게 처리함.
- 캡슐 버튼: `#capsuleBtn`(미완료 시 표시) / `#capsuleBtnComplete`(완료 시 표시) — **둘 다 항상 DOM에 존재하고 display로만 토글됨.** `count()`로는 구분 안 되고 반드시 가시성(`is_visible`)으로 판단해야 함.
- 완료 팝업: `#10rewardPopup` 내부 "확인" 텍스트 버튼 (별도 class/id 없음).
- credentials.json의 `bjh7790.hmp`에는 `password`만 있음 (`id` 필드 없음) — 키메디와 동일하게 로그인 자동완성이 이메일이 아닌 "bjh7790"이므로, `id` 필드가 없으면 계정 키 자체를 로그인 id로 사용하도록 스크립트에서 처리.
- **룰렛 참여 버튼은 미구현.** 연속 10·20·30일 달성 시 활성화되는 "룰렛 참여하기" 버튼 3개가 DOM에 항상 존재하지만, 확인 시점(연속 6일)엔 활성/비활성 구분 신호(class·disabled 속성)를 찾지 못함 — 실제 10일째 활성화된 DOM을 확인한 뒤 추가 예정. 그 전까지는 연속 출석일수가 10의 배수에 근접하면 Claude가 사용자에게 수동 확인을 안내한다.

### 사용법
keymedi.py와 같은 venv 사용 (최초 설정은 "키메디 스크립트 전환" 절 참고):
```bash
~/Desktop/DocAuto/venv/bin/python3 ~/Desktop/DocAuto/scripts/hmp.py --headed   # 최초 1회는 --headed로 확인
```
이후 매일:
```bash
~/Desktop/DocAuto/venv/bin/python3 ~/Desktop/DocAuto/scripts/hmp.py
```

### 일일 루틴에서 Claude의 역할
**2026-07-07부터: `mcp__Desktop_Commander__start_process`로 Claude가 직접 실행.**
`timeout_ms=30000` 사용. 실패 시 스크린샷 경로가 JSON에 포함되므로 Claude가 `Read`로 확인 후 디버깅.

**2026-07-06 기준 미검증.** `py_compile` 통과만 확인, 에이전트 샌드박스가 hmp.co.kr에 접근 불가해 end-to-end 테스트 못 함. 첫 실행 결과(성공/실패 불문) 반드시 사용자가 공유하고 확인할 것.

---

## 작업 후 기록 규칙

작업 완료 후 새로 알게 된 사항(UI 변경, 예외, 신규 패턴, 상태값 등)은 `MEMORY.md`에 추가.
반복 패턴이 굳어지면 이 CLAUDE.md에도 반영.
