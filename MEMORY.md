# MEMORY.md

DocAuto의 상세 지식 저장소. 셀렉터·파일 포맷·설계 근거·버그 이력·교훈. 운영 규칙은 [CLAUDE.md](CLAUDE.md).
새로 알게 된 내용은 여기에 추가한다. **날짜별 파일·별도 md 생성 금지.** 일일 실행 결과는 텔레그램 히스토리에 남으므로 여기에 로그를 쌓지 않는다.

---

## credentials 스키마

```json
{
  "telegram": { "bot_token": "...", "chat_id": "..." },
  "bjh7790": {
    "email": "bjh7790@gmail.com",
    "doctorville": { "password": "..." },
    "keymedi":     { "id": "bjh7790", "password": "..." },
    "hmp":         { "password": "..." },
    "intermd":     { "id": "bjh7790", "password": "..." }
  },
  "wonju": { "email": "wonju1119@naver.com", "doctorville": { "password": "..." } }
}
```

- 닥터빌: 로그인 id = 계정의 `email`.
- 키메디: `keymedi.id`(이메일 아님) 필수.
- HMP·인터엠디: `id` 생략 시 **계정 키 자체**("bjh7790")를 id로 사용.
- 계정/필드 추가 시 GitHub `CREDENTIALS_JSON` secret도 갱신해야 CI에 반영된다(미갱신으로 인한 실패 이력 있음).

---

## 셀렉터

각 스크립트 상단 docstring이 1차 근거. 아래는 요약.

### 닥터빌 (`doctorville.py`)
- 로그인: `/intro` → `a[href*="mims-account.shop.co.kr"][href*="/login"]` → mims(`input[name="identifier"]`, `input[type="password"]`, `button[type="submit"]:has-text("로그인")`) → `wait_for_url("*doctorville.co.kr*")`.
- 퀴즈 진입: `/product/main` → `.quiz_calender`에서 오늘 날짜 다음 줄 제품명 + `td.today` 내 hidden input `.pIdCls`의 pId → `/product/productView?pId=XXX`.
- 퀴즈 레이어: `#quizLayerPop`(오버레이 `.layer_quiz`) / 문항 `.question_area` 반복(`.txt_question`, `ul.question_choice li input[name="an_N"][value="V"]` + `label`) / 문항수 `#questionCnt` / 제출 `.btn_answer` / 정답 `:text('정답입니다')` / 오답 `:text('오답입니다')` / 이미 완료 `:text('축하드립니다')` / 닫기 `.btn_cancel`.
- 세미나 목록: `span.ico_apply` → `closest('a.list_detail')`의 `seminarId`.
- 세미나 신청: `/seminar/seminarDetail?seminarId=X` → `a.btn_bn`("신청하기") → `button.btn_confirm`(동의) → 텍스트가 "신청취소"로 바뀌면 완료.
- 라이브 입장: 목록 마커 `span.ico_enter` → 상세 `a.btn_bn.btn_enter`("입장하기", `onclick="playOnPopup(...)"` → `window.open`) → Playwright `expect_popup()`.
- 설문: `/seminar/broadcastSeminarPopup?viewType=2&seminarId=X` → `a#surveyEnter` → `button.btn_answer:has-text("설문하기")` → `survey.villeway.com` 새 창.
- 설문 폼: `form[id^="surveyForm"]`, 문항 `li[data-question-number]`, 문항 텍스트 = `label > div` 첫 줄(`[퀴즈]` 배지·후행 `*` 포함), 보기 = `ol li label` 내 `input[type=radio|checkbox]` + `span.col-start-2`, 제출 `input[type=submit][value="제출하기"]`.

### 키메디 (`keymedi.py`)
- 로그인: `input[name="uid"]`, `input[name="password"]`, `button:has-text("로그인")`.
- 출석: "출석체크하기"(미출석) / "출석완료"(완료). **"출석체크하기"를 먼저 확인**하고 최대 3초(500ms×6) 폴링 후 판단.
- 광고 팝업 "광고보고 출석하기" 클릭 필수(안 누르면 미지급, 새 탭 가능).
- 완료 모달: "출석체크가 완료되었습니다" + "확인".

### HMP (`hmp.py`)
- 로그인: `input[name="memId"]`, `input[name="passwd"]`, `button.btn_login:has-text("로그인")`.
- 캡슐: 신 UI "오늘의 캡슐 받기" 텍스트 / 구 UI `#capsuleBtn`·`#capsuleBtnComplete` 폴백 — **가시성으로 판단**.
- 완료 팝업: `[id="10rewardPopup"]` 내 "확인" (숫자 시작 id라 속성 셀렉터 필수).
- 룰렛: "룰렛 참여하기"(`onclick="roueletteAttendYnPopup(N)"`) → 확인 팝업 `.pop.cont` 처리 → `#startAbled` → `POST /ajax/event/rouelettePercentage.hm` → 결과 팝업 이미지 alt(`[마일리지] X 캡슐 적립 완료`).
- 댓글: `a[onclick*="goDetail"]` 전체에서 boardSeq 수집 → **내림차순 상위 8개 순회** → `knowCommBoardDetail.hm?boardSeq=X` → "댓글" 토글 클릭 → `#cmtDiv` 바깥의 빈 `form.cmtForm textarea[name="cmtCntnt"]`에 "감사합니다" → `button[onclick*="saveCmt"]` → confirm → alert "저장 완료". 내 닉네임은 `form.cmtForm span` 첫 요소.
- 글쓰기: `button.btnWrite` → `#writePopupDiv` → `#_topicNm` → `label:has-text("여행/취미")`(= `input[name="topicGbn"][value="TOPIC_13"]`) → `#title` → `iframe#innoditor_0` body + `#innoditorSource_0` → `#tag` "화이팅" Enter → `.botSubmit button[onclick*="saveBoard"]` → confirm → alert. AJAX: `POST /ajax/knowcomm/insertKnowCommBoard.hm`, `rtn_code==100` 성공.
- 글쓰기 중복 방지(2026-08-03 추가): `knowCommMyInfoPopup.hm?schGbn=BOARD` = "나의 작성 글" 목록. `knowCommMyInfo.hm`의 `$KnowCommMyInfo.openMyPopup('BOARD')`이 `window.open` 하는 URL이며 직접 GET으로도 열린다. 표 컬럼 `카테고리/협진과/제목/조회수/답변/좋아요/등록일자`, 마지막 `td`가 등록일자(`2026.08.03` 형식, 최신순). 오늘 날짜(KST)가 있으면 `already_done`(`verified_by: my_post_list_date_match`). 목록을 못 읽으면 fail-open으로 글쓰기 진행.
  - 배경: 체크가 없어서 daily CI와 로컬 실행이 겹치면 같은 글이 하루 3건까지 올라갔다(2026.08.03 실측: boardSeq 2525548·2525532·2525001).
  - 대안이었던 `POST /ajax/knowcomm/getKnowCommMyInfoMonthChart.hm`도 `thisMonthActList[].monthDt`(`20260803`) + `boardCnt`로 같은 판정이 가능하다. 목록 표가 사람이 검증하기 쉬워 그쪽을 택했다.
- 댓글은 이 중복 방지 대상이 **아니다**. 매일 다른 게시물에 1건 다는 것이 의도된 동작이라 날짜 기반 skip을 넣으면 하루치 지식내공 적립이 사라진다.

### 인터엠디 (`intermd.py`)
- 로그인: `#memberId`, `#memberPw`, `button.loginForm__btn--login` → `/home.do`.
- 퀴즈: `a#quizBtn` → 문항 `h2.pollSurvey__title`, 보기 `div.pollSurvey__body span.inputbox__radio label > input[type=radio]` + `span.text`.
- 제출 `button#saveBtn` / 정답 `[data-cont="state2"]`·`[data-cont="state3"]`(선물상자) / 오답 `[data-cont="state4"]` / 이미 참여 `p.quizOverlap[data-cont="over"]`.
- 캡차 `#captchaText`는 평소 부모 `div.fail`이 display:none. 노출되면 **풀지 않고 즉시 `failed`**.

---

## 데이터 파일 포맷

### `quiz_answers.json` (닥터빌 문제은행)
`{제품명: {문항텍스트: 정답보기텍스트}}`. 위치·번호 미사용, 실행 시점 렌더링 텍스트를 공백 정규화 후 매칭.
- 제품명은 **상세페이지 표기와 정확히 일치**해야 한다("대웅징코샷" vs "대웅징코샷정240mg" 불일치로 no_answer 이력).
- 미매칭 문항이 하나라도 있으면 통째 `no_answer` + 텔레그램에 오늘 문항·보기 JSON 전문 포함.
- O/X도 화면 라벨 텍스트 그대로 저장.
- 제출 성공 시 화면의 `{문항: 정답}`을 자동 학습·커밋(`chore: update quiz answers bank and legacy eviction from run [skip ci]`).

### `quiz_answers_legacy.json` (구형식 폴백)
`{제품명: "111"}` 문자열. 리스트 형식 사용 안 함. 문제은행 매칭 실패 시에만 사용.
처리 순서: `quiz_answers.json` → `quiz_answers_legacy.json` → `no_answer`.

**오답 eviction:** `:text('오답입니다')` 감지 시 해당 키를 **두 파일 모두에서 삭제**. 사후 커밋 스텝이 두 파일을 함께 `git add` 해야 `git pull --rebase`가 미커밋 변경으로 exit 128 나는 것을 막는다.

### `intermd_answer.json`
`{"answer": "...", "updated_at": "..."}`. 최신 1건만 덮어쓴다.
매칭: 숫자만이면 **1-based 보기 번호**, 아니면 공백 정규화 후 **부분 포함 + 유일 매칭**(완전 일치 1건이면 우선). 0건·2건 이상이면 `no_answer`. 하루 1문항 전제 — 2문항 이상 감지 시 미시도.
> 최신 1건 구조라, 실행 시각(14:00 KST) 이후 도착한 정답은 다음 날 엉뚱한 문항에 대조된다(무해하나 하루 손실).

### `survey_answers.json` (설문 문제은행)
`{정규화된 문항텍스트: 값}`. 세미나 무관 단일 파일. 키는 `[퀴즈]` 배지·후행 `*` 제거 + 공백 정규화.
- 선택형: 숫자만 → 1-based 보기 번호. 아니면 보기 텍스트 부분 포함 + 유일 매칭.
- 복수 선택: `"1,3"` 또는 `["1","3"]`. **쉼표 분리는 모든 조각이 숫자일 때만** — 쉼표 포함 보기 텍스트를 그대로 써도 안전.
- 주관식: 입력할 문장 그대로. 빈 문자열은 항상 "미등록".
- 척도형 5점 = 매우 만족 / 만족 / 보통 / 불만족 / 매우 불만족.
> 번호 방식은 위치 기반이라 다른 세미나에서 보기 순서가 바뀌면 오답이 된다. 흔들릴 수 있는 문항은 텍스트로 적는 편이 안전하다.

### `scripts/state/seminar_entered.json` (State v2)
`{"version": 2, "date": "YYYY-MM-DD", "accounts": {"bjh7790": {"entered": [{"id": 5473, "title": "...", "start": "2026-08-10(월) 13:00 ~ 14:00", "entered_at": "ISO시간"}], "survey": {"5473": "done"}, "blocks": {"lunch": [], "evening": [], "manual": []}}}}`
- `version: 2` 스키마 적용 (v1 파일 로드 시 자동 마이그레이션).
- `parse_dd_date`: `"2026-08-10(월) 13:00 ~ 14:00"` 형식 텍스트를 KST 타임존 파싱.
- 마감 계산 (`evaluate_survey_cutoff`): 마감 시각 = 세미나 종료 + 90분 (폴백: 시작/입장 시각 + 3시간).
- 마감 시각 전 = `not_ready` (`quiet`), 마감 시각 후 = `closed` (`quiet`).
- gitignore 대상이며 `actions/cache`로 런 간 유지.

---

## 텔레그램 인박스 설계 (`telegram_inbox.py`)

봇은 알림 봇과 동일(`TELEGRAM_BOT_TOKEN` 재사용, 새 시크릿 없음). `getUpdates` 폴링.

흐름: `getUpdates`(offset 없이) → **chat_id 필터** → 줄 단위 파싱 → 파일 갱신 → 답장 → **워크플로우가 커밋·푸시** → `--confirm-offset`으로 확정.

- **offset 확정을 맨 마지막에 하는 이유:** `getUpdates?offset=N` 호출 순간 이전 업데이트가 서버에서 영구 삭제된다. 커밋 성공 후 확정해야 중간에 죽어도 다음 실행에 다시 읽힌다(중복 처리는 같은 값 덮어쓰기라 멱등).
- **chat_id 인증은 필수.** 없으면 봇 이름을 아는 누구나 저장소에 쓸 수 있다. 불일치 메시지는 답장 없이 버리고 offset만 확정.
- 파싱 순서: **인터엠디(`인터엠디:X` / `인터엠디 X`)를 먼저** 판정 → 그 다음 닥터빌 legacy(`<제품명> <시퀀스>`). 그래서 `인터엠디 4`가 legacy 제품명으로 오인되지 않는다.
- legacy 문법: `line.rsplit(None, 1)`(제품명에 공백 허용), 시퀀스 `^[0-9oOxX]+$` 길이 1~10, `o`/`x` 소문자 정규화, 기존 키 덮어쓰기.
- 문제은행에 없는 제품명도 거부하지 않고 저장 + 경고 답장(`⚠️ … 오타 확인`).
- 피기백 실행: 두 워크플로우 **맨 앞** 스텝, `continue-on-error: true`. 최대 공백 18:30→다음날 14:00(getUpdates 24시간 보존 한도 내). 두 워크플로우 모두 `permissions: contents: write` 필요.
- **채택 안 함 — 텔레그램 → GitHub 직접 트리거:** `setWebhook`은 URL과 `secret_token`만 설정 가능하고 커스텀 `Authorization` 헤더를 못 붙인다. GitHub API는 `Bearer <PAT>`를 요구하므로 릴레이(Worker 등) 없이는 불가능.
- **채택 안 함 — 오답 피드백 기반 정답 탐색:** 오답 문구가 틀린 문항 번호를 알려줘 3~5회면 전 문항 확보 가능하나, 하루 기회가 3회뿐.

---

## 외부 cron (cron-job.org → workflow_dispatch)

GitHub `schedule`은 지연(최대 80분)·누락이 잦아 external cron (cron-job.org)을 주 트리거로 사용한다. PAT 만료 시 401로 실패하므로 cron-job.org 실패 알림 및 PAT 만료일을 관리할 것.

**PAT (fine-grained):** repository access = `SJBaek7790/DocAuto`만, permissions = **Actions: Read and write** + Metadata(자동).

**1) DocAuto seminar block (`seminar_block.yml`):**
- URL: `https://api.github.com/repos/SJBaek7790/DocAuto/actions/workflows/seminar_block.yml/dispatches`
- Method / Body: `POST` / `{"ref":"main"}`
- Headers: `Accept: application/vnd.github+json`, `Authorization: Bearer <PAT>`, `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`
- Timezone: `Asia/Seoul`
- Schedule: Minutes `0,30` / Hours `11,12,13,14,17,18,19,20,21` (하루 18회)

**2) DocAuto daily (`daily.yml`):**
- URL: `https://api.github.com/repos/SJBaek7790/DocAuto/actions/workflows/daily.yml/dispatches`
- Method / Body: `POST` / `{"ref":"main"}`
- Headers: `Accept: application/vnd.github+json`, `Authorization: Bearer <PAT>`, `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`
- Timezone: `Asia/Seoul`
- Schedule: Minutes `0` / Hours `15` (15:00 KST 주 실행)
- 백스톱: GitHub schedule `0 7 * * *` (16:00 KST) 남김

---

## 중앙 알림 게이트 및 Severity (`scripts/notify.py`)

알림 게이트는 `NOTIFY_LEVEL` 환경변수(미설정/빈값 시 `"all"` [default] 또는 `"actionable"`)에 따라 텔레그램 메시지 발송 여부를 정한다.

- **Severity 계층:** `alert` (3) > `action` (2) > `ok` (1) > `quiet` (0).
- `actionable` 모드: 전체 severity가 `action` (2) 이상일 때만 전송 (개입 필요 항목 및 오류만 추출).
- `all` 모드: 모드와 무관하게 모든 실행 결과 요약 전송.
- **성공의 양성 증거 (`verified_by`):** `status: "success"`는 `verified_by` 필드가 동반되어야 `ok` (1)로 평가되며, 미비 시 `unverified` (`alert`, 3)로 강등된다.


---

## 버그·수정 이력

### doctorville.py
| 버그 | 원인 | 수정 |
|---|---|---|
| `networkidle` 타임아웃 | 백그라운드 요청으로 미도달 | `wait_until="load"` + 타임아웃 30s |
| mims 로그인 감지 실패 | `wait_for_load_state("load")`가 SSO 전환보다 먼저 끝남 | `wait_for_url("*doctorville.co.kr*")` |
| 퀴즈 레이어 ID 오류 | `#applyInfo`가 아니라 `#quizLayerPop` | 전면 교체 |
| 결과 팝업 셀렉터 | 쉼표 다중 셀렉터 + `text=` 혼용 불가 | `:text('정답입니다')` 단일 |
| 퀴즈 already_done 미인식 | 제출 완료 시 "축하드립니다" 뷰라 `.btn_answer` 없음 | `:text('축하드립니다')` → `already_done` |
| pId 조회 실패 | `/product/medicineList` 검색은 의약품 전용 — 모비케어 등 의료기기 미등록 | 캘린더 `td.today .pIdCls`에서 직접 추출(medicineList는 폴백만) |

### keymedi.py
- 첫 성공 2026-07-06. 수정 순서: venv 전환 → 로그인 URL 매칭 대신 폼 가시성 → 클릭 후 폼 hidden 대기.
- **already_done 오판 4회 반복.** 달력에 과거 "출석완료"가 여러 개 존재. 결정타는 `wait_for_selector('A, B')` OR 매칭이 과거 버튼만 붙어도 즉시 리턴해 오늘 버튼 마운트 전에 `count()`를 읽은 것. 수정: 3초 폴링 + already_done 분기에도 스크린샷 저장(이전엔 이 분기가 스샷을 안 남겨 사후 검증 불가였다).
- **미출석 상태에서의 폴링 로직은 아직 미검증.** 재발 시 `logs/keymedi_*_already_done_*.png`로 셀렉터 변경 여부부터 확인.

### hmp.py
- 캡슐 셀렉터 리뉴얼(2026-07-07): 구 ID 소멸 → 텍스트 기반 + 구 ID 폴백.
- 페이지 진입만으로 자동 출석되는 경우가 있어 클릭→팝업 흐름이 갈린다.
- **댓글 strict mode violation:** 기존 댓글의 수정/답글 폼도 `textarea[name="cmtCntnt"]`를 가져 2개 이상 매칭. `.first`는 위험(기존 댓글 덮어쓰기). → `#cmtDiv` 바깥 + 값이 빈 폼으로 스코프. 추가로 **기본 상태에서 textarea가 `is_visible()=False`** — "댓글" 토글을 먼저 눌러야 펼쳐진다.
- **댓글이 매일 "이미 작성 완료"였던 이유(2026-07-29):** 목록 첫 링크만 확인했는데 상단 3개가 고정 게시물(공지·[지식스폰서], 실측 2518741·2501691·2496228이 최신글 2522297보다 번호가 낮다). 거기 남은 옛 댓글을 완료 신호로 읽어 매일 아무것도 안 했다. → 내림차순 상위 8개 순회로 수정, 2522445에 작성 성공 확인.
- **글쓰기 토픽 선택 실패:** `input[name="topicGbn"]`이 커스텀 스타일링으로 시각적 숨김 → 보이는 `label:has-text("여행/취미")` 우선 클릭, `force=True` 폴백, `is_checked()` 검증 후 재시도.
- **룰렛 확인 팝업 미처리(2026-07-15):** "룰렛 참여하기" 클릭 후 휠이 아니라 `.pop.cont` 확인 팝업이 먼저 뜰 수 있고, 안 닫으면 재시도 때 "intercepts pointer events" 연쇄 실패. `_run_roulette()`에 팝업 확인 단계 추가(운영망 미검증 — 다음 활성화 때 확인).
- **goto 타임아웃(2026-07-21):** 러너의 일시적 네트워크 지연. `common.goto_with_retry()`(2초 대기 후 최대 2회 재시도) 추가.

### daily_runner.py
- **텔레그램 400 Bad Request:** 파싱 오류가 아니라 **길이 초과**였다. Playwright 예외(call log 포함 ~2400자)를 그대로 넣어 4096자 한도 초과. `notify.shorten()`(첫 줄·200자) + 4096자 안전망 + `HTTPError` 응답 body 로깅.
- **닥터빌 120초 타임아웃:** 출석+퀴즈+세미나 순차 + 세미나 건수만큼 반복이라 초과. 닥터빌만 240초.
- 실행 순서: 키메디 → 닥터빌×2 → HMP (HMP를 맨 뒤로, 사용자 요청).

### seminar_survey.py
- **headlessui 모달이 제출을 막음:** 임시저장 초안이 있으면 "작성 중인 정보를 불러왔습니다" 모달의 backdrop이 포인터 이벤트를 가로채 제출 클릭이 30초 타임아웃(실패한 실행이 초안을 남겨 재시도할수록 재현). `dismiss_alerts()`를 창 오픈 직후·제출 직전·직후에 호출.
  - **함정: 모달 루트는 크기 0이라 `is_visible()`이 False.** 이 프로젝트에서 "가시성으로 판단"이 정석이던 것과 반대로, 여기서는 `count()`로만 판정해야 한다.
- **척도형 보기 텍스트:** 보기 텍스트가 input을 감싼 label이 아니라 `label[for="<input id>"]`에 있어 전부 빈 문자열이었다 → `label[for]` 폴백 추가.
- **제출 후에도 `a#surveyEnter`가 사라진다** → "이미 참여"와 "마감"이 구분되지 않고 둘 다 `no_questions`.
- 설문은 페이지 순차 제출형이라 전체 사전 검증 불가. **페이지 단위 검증이 도달 가능한 최대 안전선**이라 미등록 1건이면 그 페이지를 제출하지 않고 `incomplete_bank`로 중단한다.

### seminar_live.py (2026-07-20 신규)
- 로컬 sandbox에서 Playwright 시스템 라이브러리 설치 불가(sudo 필요)해 DOM 조사는 Claude in Chrome MCP로 실제 로그인 세션에 붙어 수행했다.
- `playOnPopup` 소스 직접 검사는 도구 필터에 걸려 `usesWindowOpen` 등 구조만 간접 확인.
- 목록에 있어도 방문 시점에 방송 종료/미시작이면 상세에 `a.btn_bn.btn_enter`가 없다 → `skipped` 후 다음 세미나.

---

## 인터엠디 차단 (해결 불가 판정)

- 증상: `#memberId` 20초 타임아웃 → 셀렉터 문제로 오해하기 쉬우나, **artifact 스크린샷은 `403 Forbidden` 한 줄짜리 Apache 페이지**였다.
- 1차 대응(헤더): `locale="ko-KR"` + `Accept-Language` 명시, `detect_block()`으로 차단 문구 감지해 `접속 차단됨(...)` 보고.
- **2026-07-29 확정:** 헤더 조치 후에도 7-28·7-29 연속 403. 같은 시각·같은 코드로 로컬(집 IP)은 정상 제출 → **Azure 데이터센터 IP 대역 차단**. 코드로 해결 불가로 판단해 `daily_runner`에서 제외, 수동 실행 전용.
- 되살리려면 셀프호스티드 러너(맥) 또는 한국 residential 프록시가 필요하다.

---

## 알려진 리스크

1. **구형식 legacy 시도는 하루 3회 기회 중 1회를 태운다.** 위치가 맞은 사례(모비케어 `"123"`, 아림시스 `"112"`)와 어긋난 사례(펙수클루 `"332"`→`"323"` 정정, 커밋 `394d8ec`)가 모두 있다. 안전조건은 방어일 뿐 순서 섞임 자체는 못 막는다.
2. **위치 기반 매칭 전반**(legacy 시퀀스, 설문·인터엠디 번호)은 보기 순서가 섞이면 오답. 퀴즈 레이어에 "커뮤니티 정답 공유 시 패널티" 경고가 있어 사용자별 셔플 가능성이 있다 — 위치 기반 저장을 2026-07-19 폐기한 이유.
3. **PAT 만료 시 401로 조용히 실패.** cron-job.org 실패 알림 필수.
4. **`getUpdates` 24시간 보존.** 인박스 폴링이 하루 넘게 죽으면 그 사이 메시지는 복구 불가.
5. **봇 webhook 충돌.** webhook이 설정되면 `getUpdates`가 409. 현재는 전송 전용.

---

## 교훈

- **`already_done` 판정은 "오늘 것"인지 확인해야 한다.** 날짜 개념 없는 흔적(과거 댓글·과거 출석완료 버튼)을 완료 신호로 쓰면 조용히 아무것도 안 하는 자동화가 된다. HMP 댓글·키메디 출석 둘 다 같은 함정에 빠졌다.
- **타임아웃 메시지보다 스크린샷 artifact를 먼저 볼 것** (`gh run download <run-id>`). 인터엠디 403이 셀렉터 타임아웃으로 위장했다.
- **CI는 워킹트리가 아니라 HEAD를 돌린다.** 응답이 "옛 동작" 같으면 코드 로직보다 `git show HEAD:<파일>`부터.
- **분기마다 스크린샷을 남겨라.** 스샷 없는 분기는 오판이 나도 사후 검증이 불가능하다.
- **가시성 판정은 만능이 아니다.** 대부분은 `is_visible()`이 정답이지만, 크기 0인 모달 루트나 커스텀 스타일로 숨긴 input에는 `count()`/`label` 우회가 필요하다.
- **화면 미반영 ≠ 실패.** 세미나 "신청하기" 후 텍스트가 즉시 안 바뀌어도 성공한 경우가 많다 → 재진입해 "신청취소" 확인.
- **퀴즈 placeholder 오판:** 캘린더가 오늘자 제품명을 "?"로 보여줄 수 있다(SPA 로딩 지연). "?"만 보고 "퀴즈 없음" 단정 금지.
- **세미나 동의 모달 변형:** 대개 `button.btn_confirm` 한 번이지만 일부는 2단계(제3자 제공 + 마케팅 선택). 항상 동의.
- **상태 오기재 금지.** 실제 목표(포인트 적립) 달성 시에만 완료 처리(2026-07-02 사고).

---

## 순수 함수 테스트 지점

Playwright 계층은 라벨 텍스트만 추출해 순수 함수에 넘긴다. `tests/`에 단위 테스트 존재.

| 함수 | 위치 |
|---|---|
| `legacy_to_choice_indices` / `parse_wrong_numbers` / `match_quiz_bank` | `doctorville.py` |
| `parse_inbox_line` / `parse_intermd_line` | `telegram_inbox.py` |
| `merge_state` / `parse_dd_date` / `upgrade_to_v2` | `seminar_live.py` |
| `evaluate_survey_cutoff` | `seminar_survey.py` |
| `severity_of` / `should_send` / `build_message` | `notify.py` |
| `list_accounts` / `account_label` / `is_recon_enabled` | `common.py` |
| `match_choice(saved, choices)` | `intermd.py` |

---

## HMP 연속 출석 이력 (룰렛 참고, 갱신 필요)

| 날짜 | 연속 일수 |
|---|---|
| 2026-06-24 | 10일 (룰렛 → 100캡슐 당첨) |
| 2026-07-03 | 3일 (연속 끊김) |
| 2026-07-06 | 6일 |

---

## 과거 실행 방식 (이력용, 현재 미사용)

GitHub Actions 전환(2026-07-14) 이전의 반자동 실행 기록. 현재 루틴과 무관.

- **Chrome MCP 도메인 차단:** keymedi.com·hmp.co.kr `navigate`가 날마다 다르게 거부됨(07-01 정상 → 07-02 차단 → 07-03 정상). 이 불안정성이 Playwright 전환의 계기.
- **Desktop Commander:** 사용자 Mac에서 스크립트 직접 실행(30초 timeout). → daily_runner + Actions로 대체.
- **Chrome 프로필 판별:** `list_connected_browsers`의 "Browser 1/2" 순서가 연결마다 뒤바뀜 → 로그인 계정명으로 검증 필요. 원주 프로필(`Profile 2`)은 매 세션 사용자가 직접 열어야 했음.
- **JS click 제약:** 퀴즈 제출·로그인 버튼은 `computer` 좌표 클릭 필요. `javascript_tool`의 outerHTML/cookie 반환은 콘텐츠 필터로 `[BLOCKED]`. — 모두 Playwright 전환으로 해소.
