# REQUIRE.md — 클로드 구현 명세서

> **작업 지침**: 이 문서는 Antigravity(기획/설계)와 사용자가 확정한 **최신 단일 작업 명세서**입니다. 기존 내용을 대체하며, 클로드는 이 문서를 읽고 명시된 사양과 테스트 기준에 맞춰 구현을 완료해주세요.

---

## 1. 작업 개요

- **작업명**: 중장기 확장 로드맵 문서(`docs/ROADMAP.md`) 작성 및 앱 내 `🗺️ 로드맵` 뷰 신설
- **배경 및 목적 (Why)**:
  1. 현재 구축된 인력 시뮬레이터를 기반으로 향후 구축할 **"반도체 AX 전주기 운영 및 인력 가치 통합 플랫폼"**의 미래 청사진을 파트원 및 유관 부서와 직관적으로 공유하기 위함입니다.
  2. 단순한 개념적 설명에 그치지 않고, **실제 Fab 현장 시나리오(인터락, PM, DataLake 쿼리, MES/EES 시스템 매핑, FTE 환산 등)**를 바탕으로 구체적이면서도 시각적(아이콘, 카드, 다이어그램)으로 한눈에 이해할 수 있는 전용 화면과 문서를 구축합니다.
- **수정 및 생성 대상 파일**:
  - `docs/ROADMAP.md` (신규 생성: 로드맵 마크다운 전문 문서)
  - `app/views/roadmap.py` (신규 생성: 시각적 다이어그램 & 탭 카드형 로드맵 뷰)
  - `app/streamlit_app.py` (상단 내비게이션에 `st.Page(roadmap.render, title="🗺️ 로드맵", url_path="roadmap")` 등록)
  - `tests/test_roadmap.py` (신규 생성: 로드맵 뷰 렌더링 및 문서 존재 검증)

---

## 2. 세부 구현 사양

### 2.1 마크다운 로드맵 문서 작성 (`docs/ROADMAP.md`)

`docs/ROADMAP.md` 파일에 아래 내용을 체계적이고 구체적인 반도체 Fab 용어로 작성합니다:

#### 1) 플랫폼 비전 (Vision)
- **"단순 인력 계산기를 넘어, 반도체 AX 전주기 운영 및 인력 가치 연결 플랫폼으로"**
- 현장 업무(Task) $\rightarrow$ 데이터 파이프라인(DataLake/S3) $\rightarrow$ 과제 PM(기획~배포) $\rightarrow$ 실제 FTE 기여도 검증 $\rightarrow$ 현장 VOC 피드백이 하나의 닫힌 루프(Closed-Loop)로 순환하는 체계.

#### 2) 4대 핵심 축(Pillars) 상세 및 구체적 Fab 예시

1. **축 1. 소분류 업무별 E2E Process Flow & DataLake 자동 실측 파이프라인**:
   - *개념*: 소분류 업무를 구성하는 세부 Task들의 전후 관계와 담당 사내 시스템(MES, EES, FDC, YMS 등) 매핑.
   - *데이터 파이프라인*: DataLake 자동 쿼리 및 S3 배치 적재를 통해 Task 실행 빈도(건/년)와 소요시간(분)을 자동으로 수집하여 기준정보 `(실측)` 데이터로 자동 갱신.
   - *구체적 Fab 예시*: "포토설비 알람 원격 리셋" 소분류
     - Task 1: FDC 실시간 알람 감지 $\rightarrow$ Task 2: MES Lot 레시피 인터락 확인 $\rightarrow$ Task 3: EES 원격 파라미터 리셋 명령 전송.
     - 매일 사내 DataLake에서 리셋 로그를 쿼리하여 S3에 적재 $\rightarrow$ 시뮬레이터 실측 빈도가 1,200건으로 자동 갱신.

2. **축 2. 공정·설비 지표 대시보드 & E2E 연계**:
   - *개념*: 엔지니어가 매일 모니터링하는 현장 품질/설비 지표 대시보드 구축 및 E2E 프로세스와의 직결.
   - *주요 레포트*:
     - **인터락(Interlock) 분석 레포트**: 설비/챔버/레시피별 인터락 발생 빈도, 평균 해소 시간, 투입 공수.
     - **PM(예방정비) 모니터링 레포트**: 정기 PM 준수율, 기준 시간 대비 초과 시간 분석, 자동화 후보 Task 발굴.
   - *연계 방식*: E2E 플로우에서 특정 Task 클릭 시 해당 Task의 인터락/PM 통계 대시보드가 연동되어 병목 지점 즉시 확인.

3. **축 3. AX 과제 프로젝트 매니지먼트 (기획 $\rightarrow$ 배포 $\rightarrow$ FTE 실기여도)**:
   - *개념*: 과제 기획부터 개발, 평가, 배포까지의 라이프사이클 관리 및 파트원 주간 업무(스프린트) 할당.
   - *가치 연결 사슬 (Value Chain)*:
     - 과제 등록: "포토 챔버 인터락 자동 해소 에이전트 개발"
     - 주간 할당: 담당 파트원 배정 및 WBS 진척도 관리
     - 배포 및 실적 연계: 배포 즉시 해당 소분류 업무의 자동화율 목표 80% 달성
     - 최종 FTE 영향: 연간 업무 시간 1,500시간 절감 $\rightarrow$ **FTE +0.7명 확보 기여도 실시간 증명**.

4. **축 4. 현장 VOC 창구 & Closed-Loop 피드백**:
   - *1단계 (Self-Service)*: 단순 기능 질문이나 가이드 문의는 사전 정의된 가이드/FAQ 검색 엔진이 즉시 자동 답변.
   - *2단계 (Closed-Loop)*: 로직 수정, 에러 제보, 기능 개선 요구는 티켓(Issue)으로 등록되어 담당 개발 파트원의 주간 업무로 자동 배정 $\rightarrow$ 배포 완료 시 요청자에게 피드백 알림 전달.

#### 3) 단계별 추진 로드맵 (Phases)
- **Phase 1 (기반 확립)**: FTE 시뮬레이터 완성, 기준정보 5개 시트 정규화, 가이드 문서화
- **Phase 2 (과제 & E2E)**: 소분류 E2E Process Flow 정의, AX 과제 기획-배포 PM 보드 구축
- **Phase 3 (데이터 파이프라인)**: DataLake 쿼리 & S3 연계 파이프라인, 인터락/PM 모니터링 대시보드
- **Phase 4 (선순환 완성)**: 실측치 기반 FTE 실기여도 자동 검증, Closed-Loop VOC 운영 체계 확립

---

### 2.2 앱 내 로드맵 뷰 구현 (`app/views/roadmap.py`)

- **헤더 영역**:
  - `st.title("🗺️ 중장기 로드맵")`
  - 배너 캡션: "반도체 Fab AX 전주기 운영 및 인력 가치 플랫폼 (AX Lifecycle & Operational Intelligence Platform)"
  - 우측 상단: `[📥 로드맵 문서 다운로드 (.md)]` 버튼 (`docs/ROADMAP.md` 다운로드)
- **1. 전체 순환 구조 다이어그램 (Native Graphviz SVG)**:
  - `st.graphviz_chart`를 활용하여 4대 축의 유기적 데이터/업무 순환 다이어그램 렌더링:
    ```dot
    digraph G {
      rankdir=LR;
      node [fontname="Pretendard, Malgun Gothic", shape=box, style="filled,rounded", fillcolor="#F0F2F5", color="#CACED6", fontsize=11];
      edge [fontname="Pretendard, Malgun Gothic", color="#0A24E9", fontsize=10];
      
      E2E [label="1. E2E Process & DataLake\n(MES·EES Task / S3 실측 자동 갱신)", fillcolor="#E8ECFE", color="#0A24E9", penwidth=1.5];
      DASH [label="2. 도메인 지표 대시보드\n(인터락 분석 · PM 레포트 모니터링)"];
      PM [label="3. AX 과제 Project Managing\n(기획 → 개발 → 배포 → 주간 할당)", fillcolor="#E8ECFE", color="#0A24E9", penwidth=1.5];
      FTE [label="4. 가치 연결 (FTE Engine)\n(Task 실적 반영 → FTE 기여도 산출)", fillcolor="#29315D", fontcolor="#FFFFFF"];
      VOC [label="5. Closed-Loop VOC\n(단순 질의 가이드 자동 안내 / 수정 과제 할당)"];
      
      E2E -> DASH [label="지표 연계"];
      E2E -> FTE [label="실측 빈도 갱신"];
      PM -> E2E [label="자동화 Task 배포"];
      PM -> FTE [label="FTE 절감 증명"];
      VOC -> PM [label="개선 티켓 할당"];
      DASH -> PM [label="병목 개선 과제 발굴"];
    }
    ```
- **2. 4대 핵심 축 탭 인터페이스 (`st.tabs`)**:
  - `tab1: 🔄 E2E & DataLake`
  - `tab2: 📈 지표 대시보드 (인터락/PM)`
  - `tab3: 📋 AX 프로젝트 매니징`
  - `tab4: 💬 Closed-Loop VOC`
  - `tab5: 🚀 단계별 추진 계획`
- 각 탭 내부:
  - 핵심 목적 및 아키텍처 설명
  - **"현장 적용 시나리오 (Fab Use Case)"** 콜아웃 박스 (배경 `#E8ECFE`, 테두리 `#0A24E9`)로 구체적 예시 제시
  - 상세 기능 목록 및 기대 효과
- **스타일 준수**:
  - `ui.py`의 3색 체계(블루 `#0A24E9`, 네이비 `#29315D`, 그레이)와 컴팩트 디자인 토큰 준수.

---

### 2.3 상단 내비게이션 바 연결 (`app/streamlit_app.py`)

`app/streamlit_app.py`의 `pages` 리스트에 `roadmap` 등록:

```python
from views import dashboard, group_detail, guide, master, roadmap  # noqa: E402

...
pages = [
    st.Page(dashboard.render, title="📊 대시보드", url_path="dashboard", default=True),
    st.Page(group_detail.render, title="🏢 그룹보드", url_path="group"),
    st.Page(master.render, title="⚙️ 기준정보", url_path="master"),
    st.Page(roadmap.render, title="🗺️ 로드맵", url_path="roadmap"),
    st.Page(guide.render, title="📖 가이드", url_path="guide"),
]
st.session_state.pages = {p.url_path: p for p in pages}
st.navigation(pages, position="top").run()
```

---

### 2.4 테스트 코드 추가 (`tests/test_roadmap.py`)

- `tests/test_roadmap.py` 신규 작성:
  - `docs/ROADMAP.md` 파일이 존재하고 비어있지 않은지 검증.
  - `roadmap.render()` 호출 시 오류 없이 정상 렌더링되는지 검증.

---

## 3. 검증 및 테스트 요건

1. **테스트 통과**:
   - `python -m pytest -q tests` 실행 시 100% 통과 확인.
2. **시각적 검증**:
   - 상단 내비게이션에 `[🗺️ 로드맵]` 메뉴가 표시되고 클릭 시 이동 확인.
   - Graphviz 순환 다이어그램이 브라우저에서 깔끔한 벡터 그래픽으로 깨짐 없이 렌더링되는지 확인.
   - 5개 탭을 넘나들며 구체적인 반도체 Fab 시나리오와 설명이 읽기 쉽게 표시되는지 확인.
   - 마크다운 다운로드 버튼 클릭 시 `ROADMAP.md`가 정상 다운로드되는지 확인.
