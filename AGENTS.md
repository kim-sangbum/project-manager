# AGENTS.md

This file provides guidance to AI coding agents (Antigravity/Gemini, Claude Code, Cursor, Codex, etc.) when working with code in this repository.

## Agent Roles & Collaboration Model

This repository operates under a strict two-agent collaborative workflow:

1. **Antigravity (Gemini) — Product Planner & Architect**:
   - Focuses strictly on product planning, requirement refinement (`/interview-me`), architecture, data modeling, and UI/UX design.
   - **Does NOT modify implementation source code directly.**
   - Synthesizes user requirements and design decisions into **high-precision, self-contained Implementation Prompts for Claude Code**.

2. **Claude Code — Engineering & Implementation**:
   - Receives the implementation prompts prepared by Antigravity.
   - Writes the actual code, updates scripts, executes tests, and handles git commits.

---

## Working with the user

- **Mandatory Interview Rule (`/interview-me`)**:
  - If a user's request leaves out **why** it is wanted (purpose, target user, context) or **when it counts as done** (completion criteria, definition of done), you **MUST** run the `/interview-me` skill before planning, drafting specs, or writing code.
  - Do not silently fill in ambiguous requirements with your own assumptions.
  - Ask **one focused question at a time**, attached with your best guess and confidence level (per `/interview-me` methodology).
  - *Exceptions*: Small, unambiguous, and direct operations (e.g. "restart the app", "fix this typo", rename a label) do not require an interview.
- **Requirement Proposals**:
  - For open design/requirement questions, present options with a recommended answer prefixed with `(Recommended)` or `(추천)`. The user often replies with a choice number or "추천".

---

## What this project is

A **sample** Streamlit web app + planning artifacts for a semiconductor-fab engineer staffing simulator. It computes "FTE 확보" (FTE freed) per part → 그룹 → SITE → team when AX automation and part bundling (조직개편) are applied. The real product will be built later inside the company (DevOps); this repo is the pre-build sample. The user writes in Korean; UI text and docs are Korean.

`SPEC.md` is the source of truth for every rule (marked [확정]/[제안]/[미정], with a decision log and KEEP list in ch.13). Read the relevant SPEC section before changing calculation logic, and record new decisions there. Open questions for the user live in `REVIEW.md`.

---

## Commands

```bash
.venv\Scripts\python -m streamlit run app/streamlit_app.py      # run app (http://localhost:8501)
.venv\Scripts\python -m pytest -q tests                          # all tests
.venv\Scripts\python -m pytest -q tests/test_engine.py -k bridge # single test
python tools/excel/build_all.py                                  # regenerate templates/*.xlsx
```

---

## Core Architecture & Rules

- **Input = one Excel workbook with 5 sheets** (`templates/시뮬레이터_입력_샘플.xlsx`):
  1. **업무구분**: task master + `{year} 목표` common-AX columns.
  2. **파트별 업무·실적**: yearly snapshot (연도+파트+코드). (입력) 빈도/단위/건당, 파트 목표, (입력) 자동화율, (실측) 빈도/건당.
  3. **조직변경**: 1 row = 1 part: 연도, 구분(계획/실적), 변경 유형(신설/폐지/병합/그룹 이동/파트 묶음), 대상 파트, 결과 (적용처).
  4. **인원**: yearly snapshot (연도+파트), 전입/전출/신입/퇴직, 최소 인원 (최소 2는 2인 필수와 동일).
  5. **설비**: Process 챔버/설비 대수 per part-year.
- **Engine (`app/sim/engine.py`)**: Pure calculation, no Streamlit. `shift_need` + `office_need` $\rightarrow$ 필요 인원. FTE 확보 = `(총원 − 재배치 대상) − 필요 인원`.
- **Navigation**: `[📊 대시보드]`, `[🏢 그룹보드]`, `[⚙️ 기준정보]`.
- **Terminology**:
  - 그룹 = 조직 단위 (파트는 정확히 하나의 그룹에 속함).
  - 라인 = 물리적 Fab 라인 (파트와 N:M 관계).
  - 묶음 (B1...) = 파트 간 시뮬레이션 통합 운영.
  - "감축"이라는 단어는 UI에 노출하지 않으며 항상 **"FTE 확보"**로 표현.
- **UI & Control Layout Rules (Strict)**:
  1. **그리드 비율 임의 분할 금지**: 설정창이나 컨트롤 배치 시 `[1.1, 1.4, 0.8]` 같은 비대칭 컬럼 사용을 금지하며, 반드시 `st.columns(4, vertical_alignment="bottom")` 균등 4열 표준을 준수합니다. (예외: 폼 하단 액션바 `[1.5, 8.5]` = 버튼 + 안내 한 줄)
  2. **수직 정렬 통일**: 컨트롤이 들어가는 모든 `st.columns`는 예외 없이 `vertical_alignment="bottom"`을 명시하여 입력 필드의 밑변(Baseline)을 일치시킵니다.
  3. **32px 컴팩트 규격 준수**: 드롭다운, 버튼, 세그먼트 컨트롤의 높이는 32px 컴팩트 디자인 토큰을 유지합니다 (`app/ui.py`의 `COMPACT_CSS`, `DESIGN.md` 'Form & Table Density').
  4. **설명 텍스트 규칙**: 개별 컬럼 내 임의의 `st.caption` 삽입을 금지하고 위젯 `help=`(툴팁) 또는 폼 하단 단일 안내선으로 일원화합니다.
  5. **고밀도 테이블 유지**: 테이블 셀 패딩 `3px 8px`, 폰트 `12px`를 유지하여 데스크톱 데이터 밀도를 극대화합니다. `st.dataframe`/`st.data_editor`에는 `row_height=ui.TABLE_ROW_H`(26px)를 넘깁니다 (캔버스 표라 CSS로는 행 높이가 바뀌지 않음).
