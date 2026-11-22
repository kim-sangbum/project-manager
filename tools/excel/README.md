# 샘플 엑셀 생성 도구

`templates/` 폴더의 엑셀 파일(샘플과 빈 양식)을 만드는 Python 스크립트예요.

## 실행

```bash
pip install openpyxl
python tools/excel/build_all.py            # templates/ 에 6개 파일을 다시 만들어요
python tools/excel/make_input.py out/      # 하나만, 다른 폴더로
```

## 스크립트

| 스크립트 | 만드는 파일 |
|---|---|
| `make_dict.py` | (데이터만) 샘플 업무 목록 `ROWS`, 코드 규칙(`codes()`), 업무구분 행(`dict_records`) |
| `make_input.py` | `시뮬레이터_입력_샘플.xlsx`, `시뮬레이터_입력양식.xlsx` — 웹앱이 가져오는 입력 파일. 샘플 데이터만 만들고 쓰기는 **웹앱과 같은 작성기 `app/sim/xlsx.py`** (내보내기·양식·샘플의 열이 기준정보 화면과 같아요). 조사 엑셀용 업무구분 시트(`survey_dict_sheet`)도 여기 |
| `make_survey.py` | `조사_일일기록양식.xlsx`, `조사_정기업무설문양식.xlsx` |
| `make_freq.py` | `파트별업무실적_집계_샘플.xlsx`, `파트별업무실적_집계양식.xlsx` — 일일 기록·설문 → '파트별 업무·실적'(화면 열), 조사 목적 기준/실적 |
| `sample_org.py` | (데이터만) 샘플 조직: 18개 파트, 신설·폐지, 챔버 수, 조직변경(신설·묶음·폐지), 인원 변동 |

## 샘플 조직을 바꾸려면

`sample_org.py`를 고친 뒤 `build_all.py`를 다시 실행해요. 파트 ID(P001…)는 `PARTS` 순서대로 매겨져요.

## 샘플 업무 사전을 바꾸려면

`make_dict.py`의 `ROWS`를 고친 뒤 `build_all.py`를 다시 실행해요. 업무 코드(예: `E-EV-003`)는 `ROWS` 순서대로 직군·TYPE별로 매겨지니, 중간에 줄을 끼워 넣으면 뒤쪽 코드가 바뀌어요.

## 확인

openpyxl은 수식 값을 계산하지 않아요. 엑셀로 열면 계산되고, 각 시트 마지막 '입력 검사' 열이 모두 `OK`여야 해요.
`tests/test_engine.py`의 `test_excel_formulas_balanced`(수식 괄호 짝 — 틀리면 엑셀이 파일을 못 열어요)와 `test_excel_columns_match_screen`(엑셀 열 = 화면 열 + 입력 검사)도 돌려요.
