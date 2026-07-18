# MEMORY.md

실행 중 확인된 사실·예외 패턴을 축적하는 파일. 새로 알게 된 내용은 여기에 추가. 날짜별 파일 생성 금지.

> **아키텍처 (2026-07-14~):** GitHub Actions cron에서 `scripts/daily_runner.py`가 무인 실행한다. 운영 지침은 `CLAUDE.md`, 구현은 `AUTOMATION.md` 참조. **아래 "과거 실행 방식(이력용)" 이하의 Chrome in Chrome MCP / Desktop Commander / computer-use 관련 기록은 전환 이전(2026-06-23~07-10) 내용으로, 현재 루틴과 무관하다.** 일일 실행 결과는 이제 텔레그램 히스토리에 남으므로 이 파일에 날짜별 로그를 더 쌓지 않는다.

---

## 스크립트 버그 수정 이력

### doctorville.py
| 버그 | 원인 | 수정 |
|---|---|---|
| `networkidle` 타임아웃 | 백그라운드 요청으로 networkidle 미도달 | `wait_until="load"` + `DEFAULT_TIMEOUT_MS` 30000 |
| mims 로그인 감지 실패 | `wait_for_load_state("load")`가 SSO 전환보다 먼저 끝남 | `wait_for_url("*doctorville.co.kr*")`로 교체 (2026-07-09) |
| 퀴즈 레이어 ID 오류 | `#applyInfo` 대기했으나 실제 ID는 `#quizLayerPop` | 전면 교체 |
| 결과 팝업 셀렉터 오류 | `"text=정답입니다, ..."` 쉼표 다중 셀렉터 + text= 혼용 불가 | `:text('정답입니다')` 단일 셀렉터 |
| 퀴즈 already_done 미인식 | 이미 제출 시 레이어가 "축하드립니다" 뷰로 열려 `.btn_answer` 없음 → failed | `:text('축하드립니다')` 감지 시 `already_done` |

**퀴즈 레이어 구조 (2026-07-10 DOM 확인):** 팝업 `#quizLayerPop`(오버레이 `.layer_quiz`) / 라디오 `input[name="an_N"][value="V"]` / 제출 `.btn_answer` / 닫기 `.btn_cancel` / 완료 시 "축하드립니다" 텍스트.

### keymedi.py
- 첫 성공: 2026-07-06 (세 번째 시도). 수정 순서 = ① `externally-managed-environment` → venv ② 로그인 URL 매칭 오판 → 폼 가시성 체크 ③ 클릭 직후 경쟁 상태 오판 → 폼 hidden 대기.
- already_done 오판(2026-07-12~14): 달력에 과거 "출석완료" 버튼이 여러 개 존재 → "출석체크하기"를 **먼저** 확인해야 함. 오늘 버튼이 뷰포트 밖이면 `is_visible()` False가 되므로 가시성 대신 count>0 + scroll 후 클릭.
- **재발(2026-07-16, 4번째):** 위 수정에도 불구하고 미출석 상태에서 again already_done 오판 발생(사용자가 직접 확인). opus 자문 결과 root cause로 지목된 것: 바로 위 `wait_for_selector('button:has-text("출석체크하기"), button:has-text("출석완료")')`가 OR 매칭이라 과거 날짜 "출석완료" 버튼만 먼저 DOM에 붙어도 즉시 리턴되고, 그 순간 바로 `attend_btn.count()`를 체크하면 오늘 버튼이 아직 마운트 전이라 0으로 읽힐 수 있음. 수정: 즉시 판단하지 않고 최대 3초(500ms×6) 폴링 후 판단 + already_done 분기에 스크린샷 저장 추가(이전에는 이 분기가 스크린샷을 안 남겨서 오판이 나도 사후 검증이 불가능했음). **주의: 폴링은 타이밍 문제만 해결한다.** 만약 다음에 또 재발하면 셀렉터/텍스트 자체가 바뀌었을 가능성이 높으니, 이번엔 스크린샷이 남으므로 `logs/keymedi_*_already_done_*.png`로 확인할 것.
  - **로컬 실행 검증(2026-07-16 저녁):** 실제로 실행해보니 이미 이날 아침 cron으로 출석이 완료된 상태라 already_done이 나왔고, 저장된 스크린샷으로 실제 "출석완료" 버튼 상태임을 육안 확인 — 이 결과 자체는 참(진짜 완료)이었다. **미출석 상태에서의 폴링 로직 자체는 이번엔 검증하지 못함** — 다음에 미출석 상태(자정 직후 등)에서 한 번 더 확인 필요.

### hmp.py
- 셀렉터 리뉴얼(2026-07-07): 구 `#capsuleBtn`/`#capsuleBtnComplete` ID 사라짐 → "오늘의 캡슐 받기" 텍스트 + `wait_until="load"` + `wait_for_timeout(2000)` 병행. 구 ID는 fallback 유지.
- CSS 셀렉터에 `text=` 혼용 시 파싱 오류 → locator 분리.
- 완료 팝업 `#10rewardPopup`은 숫자 시작 ID → `[id="10rewardPopup"]` 속성 셀렉터.
- 관찰: 페이지 진입만으로 자동 출석 처리되는 경우가 있어 스크립트 클릭→팝업 흐름이 될 때·안 될 때가 갈림. 팝업 감지 실패 시 페이지 상태 변화로 완료를 판정하는 대안 검토 여지.
- **지식커뮤니티 댓글 자동화 추가 (2026-07-15):** `_run_comment()` — `knowCommHome.hm` 최상단 게시물 boardSeq 추출(onclick regex) → `knowCommBoardDetail.hm?boardSeq=XXXX` GET 이동 → `#cmtDiv .cmtName` 에 내 닉네임 있으면 already_done → `textarea[name="cmtCntnt"]`에 "감사합니다" → `form.cmtForm button[onclick*="saveCmt"]` 클릭 → confirm 수락 → 성공 alert "저장 완료". 내 닉네임은 `form.cmtForm span` 첫 번째 요소에서 동적으로 읽음.
- **지식커뮤니티 글쓰기 자동화 추가 (2026-07-15):** `_run_post()` — `knowCommHome.hm` → `button.btnWrite` 클릭 → `#writePopupDiv` 팝업 대기 → `#_topicNm` 클릭(드롭다운 열기) → `input[name="topicGbn"][value="TOPIC_13"]`(여행/취미) → `#title` "오늘도 화이팅" → iframe `#innoditor_0` body + `#innoditorSource_0` textarea에 `{요일}요일이네요. 다들 화이팅하세요.` → `#tag` "화이팅" Enter → `.botSubmit button[onclick*="saveBoard"]` → confirm 수락 → 성공 alert "게시글이 작성 완료 됐습니다.". already_done 체크 없음(하루 1회 실행 전제). AJAX 엔드포인트: `POST /ajax/knowcomm/insertKnowCommBoard.hm`, rtn_code==100 성공.
- **GitHub Actions headed 실행 (2026-07-15):** Ubuntu CI에는 물리 디스플레이가 없으므로 `xvfb-run -a` 를 통해 가상 프레임버퍼(Xvfb)를 띄운 뒤 `--headed` 로 Chromium을 실행. workflow에 `sudo apt-get install -y xvfb` 단계 추가, 실행 커맨드를 `xvfb-run -a python3 scripts/daily_runner.py --headed` 로 변경.
- **댓글 strict mode violation (2026-07-16):** 게시물에 기존 댓글이 있으면 그 댓글의 답글/수정 폼도 `textarea[name="cmtCntnt"]`를 가져서(값이 기존 댓글 텍스트로 채워진 채) 매칭이 2개 이상 되어 예외 발생(`_run_comment`, 실제 로그: 3개 매칭 — 빈 것 2개 + "언제나 화이팅" 텍스트로 채워진 것 1개). `.first`만으로는 불충분(기존 댓글 수정 폼을 잘못 잡아 덮어쓸 위험, opus 자문 지적). 1차 수정: 새 댓글 폼을 `#cmtDiv`(기존 댓글 목록 컨테이너) 바깥 + textarea 값이 비어있는 `form.cmtForm`으로 스코프.
  - **1차 수정만으로는 부족했음(로컬 실행으로 발견, 2026-07-16):** 댓글 0개인 게시물에서도 "새 댓글 입력창을 찾을 수 없음"으로 계속 실패. 디버그 스크립트로 실제 DOM 조회 결과, `form.cmtForm`은 정확히 1개 존재하지만 **기본 상태에서 `textarea[name="cmtCntnt"]`가 `is_visible()=False`** — "댓글" 토글 버튼을 눌러야 펼쳐짐. 이전 07-15 성공 사례는 어쩌다 이미 펼쳐진 상태였을 가능성. 2차 수정: 폼 스코핑 전에 `button:has-text("댓글")` 토글을 먼저 클릭해서 펼친 뒤 탐색. 로컬 실행으로 실제 댓글 작성 성공 확인 완료(게시물 2515921, "저장 완료").
- **글쓰기 토픽 선택 실패 (2026-07-16):** `input[name="topicGbn"][value="TOPIC_13"]` 직접 클릭이 "element is not visible"로 15초 타임아웃(스크린샷상 "여행/취미" pill 자체는 렌더링되어 보임 — 커스텀 스타일링을 위해 실제 `<input>`이 시각적으로 숨겨진 패턴으로 추정, opus 자문). 수정: 보이는 라벨 텍스트(`label:has-text("여행/취미")`)를 우선 클릭, 못 찾으면 `force=True`로 폴백, 클릭 후 `is_checked()`로 실제 선택 여부 검증 후 필요시 재시도. **로컬 실행으로 실제 성공 확인 완료** ("글 작성 완료: '오늘도 화이팅' (목요일)").

공통 로그인/스크린샷/폼로그인 로직은 `scripts/common.py`로 추출(2026-07-14).

### daily_runner.py
- 텔레그램 전송 400 Bad Request(2026-07-15): 원인은 메시지 길이 초과, 파싱 오류가 아니었음. hmp.py 룰렛 실패 시 넘어오는 Playwright 예외(call log 포함, 건당 최대 ~2400자)를 축약 없이 그대로 넣어 메시지 전체가 Telegram sendMessage 4096자 제한을 넘김 → 400. `_short()`로 각 task 메시지를 첫 줄·200자로 축약 + `send_telegram()`에 4096자 안전망 추가, `HTTPError`는 응답 body까지 로그로 남기도록 수정(다음에 같은 종류 오류가 나도 원인이 로그에 바로 보이게).
- **실행 순서 변경(2026-07-16):** 키메디 → 닥터빌(bjh7790) → 닥터빌(wonju) → HMP 순으로 변경(기존: 키메디 → HMP → 닥터빌×2). HMP를 맨 뒤로 미룸(사용자 요청).
- **닥터빌 120초 타임아웃(2026-07-15~16 실제 발생):** 출석+퀴즈+세미나 3단계를 순차 실행하고 세미나는 신청 가능 건수만큼 반복 순회하는 구조라 기존 120초 제한을 두 계정 모두 초과해 "타임아웃 (120초)" failed로 강제 종료됨. `run_script()`에 `timeout` 파라미터를 추가하고 닥터빌 호출만 240초로 늘림(키메디/HMP는 기존 120초 유지). 참고: 실패 시점 스크린샷(`doctorville_quiz_layer_open_*.png`)은 퀴즈 레이어가 정상적으로 열린 직후 항상 찍히는 디버그샷이라 그 자체가 실패 지점을 가리키진 않음 — 타임아웃은 스크립트 전체 소요 시간 문제였을 가능성이 높음(세미나 신청 가능 건수가 많은 날 특히 취약, 다음에도 재발하면 세미나 루프 자체의 소요 시간을 로그로 남길 것).

---

## 퀴즈 정답 참고

정답은 `quiz_answers.json`이 소스 오브 트루스. 제품명은 상세페이지 표기와 정확히 일치해야 매칭된다.
- **이름 불일치 주의:** 상세페이지가 "대웅징코샷정240mg"으로 뜨면 `quiz_answers.json`의 "대웅징코샷" 키와 매칭 안 됨(2026-07-09 no_answer). 상세 표기 기준으로 키를 추가/보정할 것.
- **위치 기반 저장 방식 폐기(2026-07-19):** 기존엔 보기 번호 시퀀스 문자열("111" 등)로 저장했으나, 사용자가 "같은 약도 날짜마다 문항 수·순서가 다르다"고 지적. 실제로 DOM 조사(2026-07-19, 우루사)한 결과 당일 문항 수는 2개인데 기존 저장값 `"332"`는 3자리 — 이미 어긋나 있었음. 게다가 레이어 안내문에 "커뮤니티에 정답을 공유하는 경우 패널티가 있을 수 있습니다"라는 경고가 있어, 보기 순서 자체도 사용자별/방문별로 섞일 가능성이 있음 → 위치 기반 매칭은 문항 수가 우연히 맞아도 안전하지 않다고 판단.
- **신규 방식: 문제은행(dict).** `quiz_answers.json`을 `{제품명: {문항텍스트: 정답보기텍스트}}`로 전면 변경. `doctorville.py task_quiz()`가 실행 시점에 `.question_area`를 순회하며 `.txt_question`/`.question_choice label` 텍스트를 그대로 조회해 매칭(공백 정규화만 적용, 위치·번호 미사용). 미매칭 문항이 하나라도 있으면 `no_answer`로 통째 스킵하고, 텔레그램 메시지에 오늘 실제 문항/보기 텍스트 전체를 JSON으로 포함시켜 사용자가 바로 정답만 채워 넣을 수 있게 함.
- **마이그레이션:** 기존 18개 제품 키의 구 형식 값은 전부 폐기하고 빈 `{}`로 초기화(2026-07-19). 앞으로 매일 실행 중 처음 마주치는 문항마다 `no_answer` 알림이 오면 그 문항 텍스트+정답을 채워 은행을 채워나가는 방식. 상세 DOM 구조는 `CLAUDE.md` "퀴즈 정답 형식" 섹션 참조.

---

## HMP 연속 출석 이력 (룰렛용 참고 — 갱신 필요)

| 날짜 | 연속 일수 |
|---|---|
| 2026-06-24 | 10일 (룰렛 활성 → 사용자 직접) |
| 2026-06-25 | 11일 |
| 2026-07-03 | 3일 (그 사이 연속 끊김) |
| 2026-07-05 | 5일 |
| 2026-07-06 | 6일 |

룰렛은 연속 10·20·30일에 활성화. **hmp.py에 룰렛 자동화 구현 완료 (2026-07-14).**

### 룰렛 플로우 (2026-07-14 Claude in Chrome MCP로 실제 확인)

- 활성화 조건: 연속 10·20·30일 달성 시 "룰렛 참여하기" 버튼이 `is_visible()=True`
- 비활성 조건: 미달성 시 DOM에는 있으나 `is_visible()=False`
- 이미 참여한 경우: 버튼 텍스트가 "참여 완료"로 바뀜
- 클릭 흐름: "룰렛 참여하기" 클릭 → 룰렛 휠 표시 → `#startAbled` 클릭 → `POST /ajax/event/rouelettePercentage.hm` 호출 → 결과 팝업
- 결과 판별: 팝업 내 이미지 alt = `[마일리지] X 캡슐 적립 완료` 또는 상품권 텍스트
- 2026-07-14 실제 결과: 10일 연속 룰렛 → **100캡슐 당첨**
- daily_runner.py 텔레그램 포맷: `🎡 룰렛: ✅ +100캡슐 100캡슐 당첨` 형태로 출력
- **버그(2026-07-15): 참여 확인 팝업 미처리.** "룰렛 참여하기" 클릭(`onclick="roueletteAttendYnPopup(N)"`) 시 곧장 휠이 뜨는 게 아니라 참여 여부를 묻는 확인 팝업(`.pop.cont`, 예: `#popCont1`)이 먼저 뜨는 경우가 있었음. 이걸 처리 안 해서 1차 시도는 `#startAbled` 미표시로 실패하고, 안 닫힌 팝업이 2·3차 재시도 때 버튼을 가려 "intercepts pointer events" 클릭 실패가 연쇄됨. `_run_roulette()`에 "룰렛 참여하기" 클릭 직후 `.pop.cont` 중 visible한 것을 찾아 "확인"/"예" 클릭하는 단계 추가로 수정(운영망에서 미검증 — 다음 룰렛 활성화 시 Actions 결과로 확인 필요).

---

## 교훈 (전환 이후에도 유효)

- **상태 오기재 금지:** 자동화가 막혀 진행 불가한 항목을 "완료"로 표기하지 말 것. 실제 목표(포인트 적립) 달성 시에만 완료 처리(2026-07-02 사고).
- **화면 미반영 ≠ 실패:** 세미나 "신청하기" 클릭 후 버튼 텍스트가 즉시 안 바뀌어도 실제로는 성공한 경우가 많음 → 재진입해 "신청취소" 상태로 확인.
- **퀴즈 placeholder 오판:** `/product/main` "이달의 퀴즈" 캘린더가 오늘자 상품명을 "?"로만 보여줄 수 있음(SPA 로딩 지연) → 재로딩 후 텍스트로 재확인, "?"만 보고 "퀴즈 없음" 단정 금지.
- **세미나 동의 모달 변형:** 대개 `button.btn_confirm`("동의하기"/"동의합니다.") 한 번이면 되지만, 일부 세미나는 2단계 모달(제3자 제공 + 마케팅 선택)로 뜸 → 항상 동의(마케팅은 선택).

---

## 과거 실행 방식 (이력용, 현재 미사용)

아래는 GitHub Actions 전환(2026-07-14) 이전의 반자동 실행 관련 기록이다. 현재 루틴과 무관하며 참고 목적으로만 남긴다.

- **Chrome MCP 도메인 차단:** keymedi.com·hmp.co.kr에 대한 `navigate`가 날마다 다르게 "Navigation to this domain is not allowed"로 거부됨(07-01 정상 → 07-02 차단 → 07-03 정상 …). 이 불안정성이 Playwright 스크립트 전환의 계기였고, 최종적으로 GitHub Actions 무인 실행으로 귀결됨.
- **Desktop Commander 실행:** `mcp__Desktop_Commander__start_process`로 사용자 Mac에서 keymedi.py/hmp.py 직접 실행(외부망 접근 가능). 30초 timeout, 결과 JSON 수신. → daily_runner.py + Actions로 대체됨.
- **Chrome 프로필 판별:** `list_connected_browsers`의 "Browser 1/2" 이름·deviceId 순서는 연결 시점마다 뒤바뀜 → 이름만으로 판단 금지, 로그인된 계정명으로 검증 필요했음. 원주 프로필 창은 매 세션 사용자가 직접 열어야 했음(computer-use는 브라우저 tier "read"·터미널 tier "click" 제약으로 우회 불가).
- **JS click 제약:** 퀴즈 "정답 도전" 버튼, 키메디·HMP 로그인 버튼은 JS `.click()` 타임아웃/자동완성 공란 문제로 `computer` 좌표 클릭이 필요했음. `javascript_tool`의 outerHTML/cookie 반환은 콘텐츠 필터로 차단(`[BLOCKED]`)됨. — 모두 헤드리스 Playwright 전환으로 해소.
