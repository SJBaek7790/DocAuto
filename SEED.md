# Seed: 인터엠디 퀴즈 + 닥터빌 세미나 설문조사
**Version:** 1.1

## Changelog
- 1.0: Initial spec
- 1.1: 실제 DOM 정찰 결과 반영(2026-07-27). 설문은 **페이지 단위 순차 제출** 구조임이 확인되어 "전 문항 확인 후 제출" 기준을 페이지 단위로 완화(criteria 13·14 수정). 인터엠디·설문 셀렉터 확정.

## 확인된 DOM (2026-07-27 실측)
### 인터엠디
- 로그인: `#memberId`, `#memberPw`, `button.loginForm__btn--login`. 성공 시 `/home.do`.
- 캡차 `#captchaText`는 부모 `div.fail`(display:none) 안에 숨겨져 있고 로그인 실패 누적 시에만 노출된다. **보이면 즉시 `failed`로 중단한다(캡차를 풀지 않는다).**
- 퀴즈 진입: `a#quizBtn` 클릭 → 같은 페이지에 퀴즈 레이어(`.quizPop__quiz`) 표시.
- 문항: `h2.pollSurvey__title`(앞에 `span.pollSurvey__quiz`="퀴즈" 접두), 보기: `div.pollSurvey__body span.inputbox__radio label` 안의 `input[type=radio]` + `span.text`.
- 제출: `button#saveBtn`("정답 제출하기"). 결과: `[data-cont="state2"]`(정답)/`[data-cont="state4"]`(오답)/`[data-cont="state3"]`(선물상자형 정답).
- 이미 참여: `p.quizOverlap[data-cont="over"]` 가시 상태.

### 닥터빌 설문
- 방송 팝업 `/seminar/broadcastSeminarPopup?viewType=2&seminarId=<ID>` 안의 `a#surveyEnter`("설문 참여") → 안내/동의 레이어의 `button.btn_answer:has-text("설문하기")` → `survey.villeway.com` 새 창(`expect_popup`).
- 설문 폼: `form[id^="surveyForm"]`, 문항 `li[data-question-number]`, 문항 텍스트는 `label > div`의 첫 줄(선행 `[퀴즈]` 배지·후행 `*` 포함), 보기 `ol li label` 안의 `input[type=radio|checkbox]` + `span.col-start-2`.
- 제출: `input[type=submit][value="제출하기"]`. 페이지는 순차 진행형(제출 후 다음 페이지 렌더링).

## Intent
DocAuto 일일 자동화에 두 기능을 추가한다. (1) 인터엠디(intermd.co.kr) "오늘의 퀴즈"를 텔레그램으로 미리 받아둔 정답 보기 텍스트로 자동 제출한다. (2) 닥터빌 라이브 세미나 입장 후 제공되는 설문조사(survey.villeway.com)를 문제은행 기반으로 자동 응답·제출한다. 둘 다 기존 패턴(Playwright + JSON 결과 + 텔레그램 요약 + 문제은행 파일)을 그대로 따른다.

## Ontology
- **인터엠디 정답(IntermdAnswer)**: 오늘의 퀴즈 정답 *보기 텍스트의 일부 문자열*. 하루 1문항 전제. 이력이 아니므로 파일에는 항상 최신 값 1개만 존재(덮어쓰기). 저장 위치 `intermd_answer.json` = `{"answer": "<텍스트>", "updated_at": "<ISO8601>"}`.
- **인터엠디 인박스 메시지**: 텔레그램 본문 중 `인터엠디:<정답텍스트>` 또는 `인터엠디 <정답텍스트>` 로 시작하는 줄. 기존 닥터빌 legacy 시퀀스 파싱보다 **먼저** 판정한다.
- **설문(Survey)**: 입장에 성공한 세미나 1건에 대해 1회 제출 가능한 설문. 1페이지=객관식 다문항, 2페이지=주관식 다문항, 마지막에 제출.
- **설문 문제은행(SurveyBank)**: 세미나 무관 단일 파일 `survey_answers.json`. `{ "<공백정규화된 문항텍스트>": "<정답/답변 텍스트>" }`. 객관식·주관식 구분 없이 같은 dict. 객관식 값은 보기 라벨 텍스트, 주관식 값은 입력할 문장.
- **미등록 문항**: 문제은행에 문항 텍스트가 없거나(주관식), 있어도 저장값이 오늘 보기 중 어느 것과도 매칭되지 않는(객관식) 문항. 1개라도 있으면 **해당 세미나 설문은 제출하지 않는다**.
- **설문 완료 상태**: `scripts/state/seminar_entered.json`의 계정별 `survey_done: [seminarId...]` 배열. 재실행 시 중복 제출 방지.

## Acceptance criteria
### A. 인터엠디 퀴즈 (`scripts/intermd.py`)
1. `python3 scripts/intermd.py`가 stdout에 단일 JSON `{"site":"intermd","account":"bjh7790","status":..., ...}`을 출력하고, status는 `success|already_done|no_answer|failed` 중 하나다.
2. `credentials.json`의 `bjh7790.intermd.{id,password}`로 `https://www.intermd.co.kr/login/loginView.do`에 로그인한다. `id`가 없으면 계정 키(`bjh7790`)를 id로 사용한다(HMP와 동일 규칙).
3. 로그인 후 "오늘의 퀴즈" 진입 → 렌더링된 문항 텍스트와 모든 보기 라벨 텍스트를 추출한다.
4. `intermd_answer.json`의 `answer` 문자열이 **공백 정규화 후 부분 포함(substring)** 으로 정확히 1개의 보기에만 매칭되면 그 보기를 선택하고 제출한다 → `status: "success"`.
5. 매칭 0개 또는 2개 이상, 또는 `intermd_answer.json` 부재 → **아무것도 클릭하지 않고** `status: "no_answer"`, 결과 JSON의 `question`/`choices`에 오늘 실제 문항·보기 텍스트를 포함한다.
6. 이미 오늘 퀴즈를 푼 상태면 `already_done`을 반환하고 재제출하지 않는다.
7. `daily_runner.py`가 5번째 항목 `[5/5] 인터엠디`로 실행하고, 텔레그램 요약에 기존 상태 이모지 규칙(✅/☑️/❓/❌)대로 한 줄 표시한다. `no_answer`인 경우 문항·보기 텍스트가 메시지에 포함된다.
8. `scripts/telegram_inbox.py --fetch`가 `인터엠디:프로미나드` 형식 줄을 파싱해 `intermd_answer.json`을 원자적으로 덮어쓰고(append 아님), `✅ 인터엠디 정답 → 프로미나드 저장` 답장을 보낸다. 기존 닥터빌 legacy 메시지 처리 동작은 변경되지 않는다(기존 테스트 통과).
9. `intermd_answer.json`은 git 추적 대상이며 CI 커밋 스텝에 포함된다.

### B. 세미나 설문조사 (`scripts/seminar_survey.py`)
10. `python3 scripts/seminar_survey.py --account all`이 stdout에 계정별 결과 JSON을 출력한다. 세미나별 status는 `success|already_done|no_questions|incomplete_bank|skipped|failed`.
11. 대상 세미나는 `scripts/state/seminar_entered.json`의 당일 `entered` 목록에서, 같은 계정의 `survey_done`에 없는 ID만이다. state 파일이 없거나 날짜가 오늘이 아니면 대상 0건으로 `skipped` 종료(에러 아님).
12. 각 세미나에 대해 `https://www.doctorville.co.kr/seminar/broadcastSeminarPopup?viewType=2&seminarId=<ID>`로 이동 → "설문참여" 클릭 → 개인정보 활용 동의 → `survey.villeway.com` 설문 창을 잡는다. 설문참여 버튼이 없으면 그 세미나는 `no_questions`로 넘어가고 다음 세미나를 계속 처리한다.
13. **페이지 단위 처리**: 각 페이지의 모든 문항을 읽어 문제은행에서 조회한다. 선택형(radio/checkbox)은 저장값이 **숫자만이면 1-based 보기 번호**로, 그 외에는 보기 텍스트에 부분 포함으로 **유일 매칭**될 때만 선택한다. 복수 선택은 `"1,3"` 또는 리스트로 받는다(쉼표 분리는 모든 조각이 숫자일 때만). 입력형(text/textarea)은 저장값을 그대로 입력한다.
14. 어떤 페이지에서든 미등록 문항이 1개라도 있으면 **그 페이지의 제출 버튼을 누르지 않고** 즉시 중단해 `incomplete_bank`를 반환한다(설문은 페이지 순차 제출형이라 앞 페이지를 제출해야 뒷 페이지를 볼 수 있으므로, 전체 사전 검증은 불가능하다 — 페이지 단위가 도달 가능한 최대 안전선이다). 미등록 문항 텍스트와 보기 목록을 결과 JSON에 담고, `survey_answers.json`에 해당 문항 키를 빈 문자열(`""`)로 추가한다. 빈 문자열 값은 항상 "미등록"으로 취급한다.
15. 마지막 페이지까지 전부 응답·제출에 성공하면 `success`를 반환하고, 해당 seminarId를 state의 `survey_done`에 추가 저장한다.
16. 개인정보 활용 동의 모달은 기존 정책대로 항상 동의한다.
17. `.github/workflows/seminar_live.yml`의 마지막 스텝으로 `seminar_survey.py`를 실행하고, 결과를 텔레그램으로 전송한다(`incomplete_bank`가 있으면 미등록 문항 텍스트 포함). `survey_answers.json` 변경분은 CI가 `[skip ci]` 커밋한다.
18. 한 세미나의 실패가 다른 세미나·계정 처리를 중단시키지 않는다.

### C. 공통
19. 기존 `python3 -m pytest`가 전부 통과하고, 신규 순수 함수(인박스 인터엠디 파싱, 보기 매칭, 문제은행 조회, survey_done state 병합)에 단위 테스트가 추가된다.
20. `CLAUDE.md`에 두 기능의 셀렉터·파일 포맷·상태값이 문서화된다.

## Constraints
- Python 3 + Playwright(헤드리스 Chromium), 기존 `scripts/common.py` 헬퍼 재사용. 신규 서드파티 의존성 없음.
- 자격증명은 `credentials.json` / `CREDENTIALS_JSON` secret에서만 읽는다. 코드·저장소에 비밀번호를 하드코딩하지 않는다. **인터엠디 계정 추가는 사용자가 GitHub `CREDENTIALS_JSON` secret을 직접 갱신해야 반영된다.**
- venv 절대경로 하드코딩 금지(`sys.executable` 사용).
- 정답/답변을 추측해서 제출하지 않는다. 불확실하면 미제출.
- 실패 시 `scripts/logs/`에 스크린샷 저장.

## Out of scope
- 인터엠디 출석·기타 적립 항목(퀴즈만).
- 인터엠디 정답 이력 누적·자동 학습(덮어쓰기만).
- 세미나별 설문 문제은행 분리, 설문 응답 결과 통계.
- wonju 계정의 인터엠디(계정 없음).
- 설문 답변의 자동 추론/생성.
