# Fab 엔지니어 최소 인원 시뮬레이터 (샘플)

반도체 Fab 엔지니어 팀이 **AX 자동화**와 **파트 묶음(조직개편)**을 적용했을 때 **FTE 확보**(교대·오피스, 공정·설비)를 파트 → 그룹 → SITE → 팀으로 계산하는 웹앱의 샘플이에요. 사내 DevOps에서 이어서 개발하기 전 단계의 샘플(기획서 · 샘플 데이터 · 목업 · 샘플 웹앱)이에요.

- 기획서: [`SPEC.md`](SPEC.md) — 모든 결정과 계산 규칙, 결정 이력, 향후 과제(KEEP)
- 확인이 필요한 질문: [`REVIEW.md`](REVIEW.md)
- 설명서: `docs/guide/` (앱 메뉴 📖 가이드), 중장기 로드맵: `docs/ROADMAP.md` (앱 메뉴 🗺️ 로드맵)
- 화면 목업: https://claude.ai/artifact/ChkFugFHP8jnBury7JmWS9 (비공개 링크)

## 실행

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt      # Windows
.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

브라우저에서 http://localhost:8501 이 열려요. 처음에는 `templates/시뮬레이터_입력_샘플.xlsx`를 자동으로 불러와요.

## 폴더

| 위치 | 내용 |
|---|---|
| `app/streamlit_app.py` | 앱 시작점 (상단 메뉴: 📊 대시보드 · 🏢 그룹보드 · ⚙️ 기준정보 (시트 5개: 업무구분 · 파트별 업무·실적 · 조직변경 · 인원 · 설비) · 🗺️ 로드맵 · 📖 가이드) |
| `app/sim/` | 계산 모듈 (화면과 분리) — `data.py` 엑셀 읽기·검사, `engine.py` 필요 인원 계산, `scenario.py` REF/COMPARE·브리지·추이 (묶음은 조직변경 시트의 파트 묶음 계획/실적대로) |
| `app/views/` | 화면별 코드 |
| `docs/` | 설명서(`guide/`)와 로드맵(`ROADMAP.md`) — 앱 화면이 이 마크다운을 그대로 읽어요 |
| `config/settings.json` | 앱 설정: POR 연도·현재 연도 (대시보드 비교 설정에서 바꿔요, 모든 사용자 공통) |
| `templates/` | 샘플·빈 양식 엑셀 (시뮬레이터 입력 샘플·양식, 조사 양식(일일 기록·정기 업무 설문), 파트별 업무·실적 집계 샘플·양식) |
| `tools/excel/` | 엑셀 생성 스크립트 (`python tools/excel/build_all.py`) |
| `skills-lock.json` | 디자인 도구 스킬 4개 목록 (design-taste-frontend, image-to-code, web-design-guidelines, agent-browser). 스킬 파일(`.claude/skills/`)은 외부 저작물이라 저장소에 올리지 않아요 — `npx skills add`로 다시 설치, 상태 확인: 전역 스킬 `dev-design-tools-setup` |
| `DESIGN.md`, `.streamlit/config.toml` | 디자인 기준(Google design.md 형식)과 그걸 옮긴 Streamlit 테마 |
| `tests/` | 계산 테스트(`test_engine.py`), 화면 스모크 테스트(`test_app_smoke.py`), 브라우저 캡처 시나리오(`browser_pages.mjs`) |

## 테스트

```bash
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest -q tests
```

## 배포 메모

Streamlit은 Python 서버로 동작해요(`streamlit run`). 사내 DevOps에는 컨테이너 등으로 올려요. 지금 샘플은 입력 편집 내용을 **브라우저 세션에만** 들고 있어서, 남기려면 '엑셀로 내보내기'로 저장해요. 여러 사람이 함께 쓰는 저장소(DB)는 사내 빌드업 때 정해요.
