# 화물운송종사자격 모의시험

가입 없이 닉네임만 입력하면 바로 쓰는 **화물운송종사자격시험 모의시험·해설·오답 복습** 웹 프로그램입니다.
서버 없이 GitHub Pages로 배포하며, 기록은 각자의 브라우저에만 저장됩니다.

**접속 주소: <https://wjdwpgh-source.github.io/cargo-driver-mock-exam/>** (휴대폰에서는 '홈 화면에 추가'로 앱처럼 쓸 수 있습니다)

> **베타 운영 중**: 문제 1,200문항(법규 375 · 화물취급 225 · 안전운행 375 · 운송서비스 225)이 모두 운영자 검수를 마쳐(2026-10-20~22) 시험에 나옵니다. 틀린 정답·해설이 보이면 해설 아래 '오류 신고'로 알려 주세요.

> 현재 개발 단계: **v1.1.0 (8단계 확장)** – 즉시 채점·해설 · 💡 힌트 · 결과 다시보기 · 내 기록·그래프 · 오답노트·복습 재시험 · 백업/불러오기·초기화 · 글자 크기 · 오프라인 동작 · 도움말 + **집중 학습(과목·난이도별) · ☆ 북마크 · 취약 과목 분석**
> 문제 데이터: 1,200문항 검수 완료(verified 1,200) – PRD 최종 목표 수량 달성
> 테스트(6단계): 자동 테스트 14묶음 전부 통과 (`docs/테스트보고서.md`) – 실제 기기 수동 점검·사람 표본 검수·베타 테스트 남음
> GitHub 배포(7단계) 진행 중 → 베타 테스트 → 검수 완료 후 v1.0.0 공개
>


## 내 PC에서 실행하기
1. 폴더의 **`실행.bat`** 을 더블클릭합니다. (Python 또는 Node.js 필요)
2. 브라우저에서 `http://localhost:8000` 이 열립니다.

`index.html` 을 직접 더블클릭해도 닉네임 기능은 동작하지만, 브라우저 보안 정책 때문에 문제 데이터는 불러오지 못합니다.

## 문제 입력·변환
1. `data/raw/문제_<과목코드>.xlsx`에 1행 = 1문항으로 입력합니다. (새 과목은 `data/raw/문제_양식.xlsx`를 복사해 이름을 바꿉니다: `문제_CARGO.xlsx` 등)
2. 상태: `draft`(초안) → `reviewed`(1차 검수) → `verified`(법령 대조 완료, **이것만 시험에 출제**) / `deprecated`(폐기)
3. 폴더의 **`문제변환.bat`**을 실행하면 검사 후 `data/questions/*.json`이 만들어집니다. 오류가 있으면 행 번호와 함께 알려 주고 아무것도 바꾸지 않습니다.
4. `힌트` 열(선택, 200자)에는 정답을 직접 말하지 않는 실마리를 적습니다. 비워 두면 앱이 틀린 보기 하나를 지워 주며, 힌트를 고쳐도 문제 버전은 바뀌지 않습니다.
5. 과목 코드: `LAW` 법규 · `CARGO` 화물취급요령 · `SAFE` 안전운행 · `SERVICE` 운송서비스

## 문제 검수
1. 폴더의 **`검수표만들기.bat`** → `검수\검수표_날짜.xlsx`가 만들어집니다(아직 검수가 끝나지 않은 문항만, 먼저 볼 '1차 80' 표시, 법규는 국가법령정보센터 조문 바로가기. 전체 문항이 필요하면 `python tools\make_review_sheet.py --all`).
2. 검수표의 노란 칸(검수 판정 · 수정 의견 · 검수자 · 검수일)을 채웁니다. 판정: `1차확인`(→ reviewed) · `법령대조완료`(→ verified, 검수자·검수일 필수) · `수정필요` · `폐기`.
3. **`검수반영.bat`** → 엑셀 원본에 상태·검수자가 반영되고 문제 파일(JSON)까지 변환됩니다. 그다음 `data/questions`의 JSON 4개와 바뀐 엑셀을 GitHub에 올리면 사이트에 반영됩니다.
4. 과목별 verified가 25/15/25/15 이상이면 미리보기 없이 실제 시험이 열립니다(검수표 '진행 현황' 시트에서 확인).

## 폴더 구성
| 경로 | 내용 |
|---|---|
| `index.html` | 첫 화면 |
| `src/` | 화면·기능 소스 (`store.js` 기록 저장, `questions.js` 문제 불러오기, `app.js` 화면 전환) |
| `data/config.json` | 시험 규격(과목·문항 수·시간·합격 점수) |
| `src/exam.js` | 출제·채점 로직 |
| `src/notes.js` | 오답노트 등록·오류 신고 주소 |
| `src/records.js` | 내 기록 집계 |
| `src/review.js` | 복습 재시험·오답노트 관리 로직 |
| `src/study.js` | 북마크·집중 학습·취약 과목 분석 로직 (v1.1.0) |
| `src/backup.js` | 백업·불러오기·초기화 로직 |
| `src/ui/exam-view.js` | 시험 화면·결과(다시보기) 화면 |
| `src/ui/records-view.js` | 내 기록 화면 (SVG 그래프) |
| `src/ui/review-view.js` | 오답노트·복습 설정·풀이·결과 화면 (풀이 화면은 집중 학습과 공용) |
| `src/ui/study-view.js` | 집중 학습 설정·결과, 북마크 목록 화면 |
| `src/ui/data-view.js` | 기록 관리(백업·불러오기·초기화) 화면 |
| `src/ui/help-view.js` | 도움말·글자 크기 화면 |
| `sw.js` | 오프라인 동작 (파일 구성이 바뀌면 `VERSION` 올리기) |
| `manifest.webmanifest`, `images/icon-*.png` | 휴대폰 홈 화면 추가용 정보·아이콘 |
| `data/questions/` | 과목별 문제 JSON (`LAW`, `CARGO`, `SAFE`, `SERVICE`) |
| `data/samples/` | 개발 확인용 샘플 문제 (`tools/make_samples.py`로 생성) |
| `data/raw/` | 문제 원본 엑셀 (`문제_양식.xlsx`, `문제_LAW.xlsx` …) |
| `tools/` | `convert.py` 변환, `validate.py` 검사, `make_template.py` 양식 생성, `make_samples.py` 샘플 생성, `make_review_sheet.py` 검수표 생성, `apply_review.py` 검수 결과 반영 |
| `tests/` | 단위 테스트(`unit.test.js`), 브라우저 테스트(`e2e_s1.py`, `e2e_s2.py`, `e2e_s3.py`, `e2e_s4.py`, `e2e_s5.py`, `e2e_s6.py`, `e2e_s7.py`, `e2e_preview.py`, `e2e_hint.py`, `e2e_tc.py`, `e2e_study.py`) |
| `docs/개발일지.md` | 스프린트별 개발 기록 |
| `.github/` | 자동 검사·배포(`workflows/validate-deploy.yml`), 오류 신고 양식 |
| `LICENSE`, `DATA_LICENSE.md`, `CONTRIBUTING.md` | 라이선스(코드 MIT · 데이터 CC BY-NC-SA 4.0), 참여 방법 |

## 테스트
폴더의 **`테스트실행.bat`**을 더블클릭하면 아래 테스트를 모두 실행하고 결과를 요약합니다(= `python tests/run_all.py`).
처음 한 번만 `pip install openpyxl playwright` 와 `python -m playwright install chromium` 이 필요합니다.

```bash
npm test                # 또는: node --test tests/unit.test.js
python tests/e2e_s1.py  # 로컬 서버(8000) 실행 후, Playwright 필요
python tests/e2e_s2.py
python tests/e2e_s3.py
python tests/e2e_s4.py
python tests/e2e_s5.py
python tests/e2e_s6.py
python tests/e2e_s7.py
python tests/e2e_preview.py   # 검수 미리보기 모드
python tests/e2e_hint.py      # 힌트 기능
python tests/e2e_tc.py        # 6단계: 빠진 TC·성능·외부 요청·기기별 화면·접근성(axe)
python tests/test_tools.py  # 문제 변환·검사 도구
```

## 문서
- 계획서 최종본: `화물운송종사자격증.MD`
- 개발계획서(PRD): `docs/개발계획서.md` (최신판. 로컬 작업 폴더에는 판별 `개발계획서_vX.PRD`)
- 개발일지: `docs/개발일지.md`
- 테스트 결과 보고서: `docs/테스트보고서.md` (수동 점검표 포함)
- 베타 테스트 안내: `docs/베타테스트_안내.md`

## 참여·오류 신고
`CONTRIBUTING.md`를 참고하세요. 문제 오류는 해설 아래 **오류 신고** 버튼이나 Issues의 '문제 오류 신고' 양식으로 알려 주세요.

## 라이선스
- 프로그램 소스코드: MIT (`LICENSE`)
- 문제·해설·힌트 데이터(`data/`): CC BY-NC-SA 4.0 (`DATA_LICENSE.md`) – 출처 표시, 비영리, 같은 조건으로 공유

## 안내
비공식 학습용 프로그램이며 한국교통안전공단과 관계가 없습니다. 시험 규정은 한국교통안전공단 공지를 확인하세요. 문제는 화면에 표시된 '문제 기준일'의 법령·자료로 작성했습니다. 개인정보와 접속 기록을 수집하지 않습니다.
