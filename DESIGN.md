---
version: alpha
name: Fab Staffing Simulator — Clear Blue
description: 반도체 Fab 엔지니어 최소 인원 시뮬레이터의 디자인 시스템. 모노크롬 그레이 바탕 위 흰 카드, 긍정 = 블루 · 부정 = 레드 두 색만 의미색으로 쓰는 분석 대시보드 스타일.
colors:
  primary: "#0A24E9"
  primary-strong: "#152EAE"
  primary-soft: "#E8ECFE"
  secondary: "#29315D"
  on-surface: "#0B0D17"
  on-surface-muted: "#5B6475"
  on-primary: "#FFFFFF"
  background: "#F0F2F5"
  surface: "#FFFFFF"
  outline: "#CACED6"
  neutral: "#A9B6C0"
  neutral-light: "#D0D5DD"
  primary-mid: "#8E9AF5"
  secondary-mid: "#3E4784"
  error: "#B42318"
  error-soft: "#FCE8E7"
  shift: "#0A24E9"
  office: "#8E9AF5"
typography:
  headline-display:
    fontFamily: Pretendard
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Pretendard
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Pretendard
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
  kpi-value:
    fontFamily: Pretendard
    fontSize: 30px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.02em
    fontFeature: '"tnum" 1'
  body-lg:
    fontFamily: Pretendard
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
  body-md:
    fontFamily: Pretendard
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: Pretendard
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.45
  label-md:
    fontFamily: Pretendard
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.3
  label-control:
    fontFamily: Pretendard
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.2
  input-compact:
    fontFamily: Pretendard
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.3
  label-sm:
    fontFamily: Pretendard
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0.02em
rounded:
  none: 0px
  sm: 6px
  md: 10px
  lg: 16px
  xl: 20px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  button-primary-hover:
    backgroundColor: "{colors.primary-strong}"
    textColor: "{colors.on-primary}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: 20px
  kpi-card-team:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.kpi-value}"
    rounded: "{rounded.lg}"
    padding: 20px
  nav-item-active:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
  badge-up:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 2px 8px
  badge-down:
    backgroundColor: "{colors.error-soft}"
    textColor: "{colors.error}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 2px 8px
  badge-warning:
    backgroundColor: "{colors.error-soft}"
    textColor: "{colors.error}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  page:
    backgroundColor: "{colors.background}"
    textColor: "{colors.on-surface}"
  caption:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.body-sm}"
  chart-bar-default:
    backgroundColor: "{colors.neutral}"
    rounded: "{rounded.sm}"
  chart-bar-highlight:
    backgroundColor: "{colors.primary}"
    rounded: "{rounded.sm}"
  chart-series-shift:
    backgroundColor: "{colors.shift}"
  chart-series-office:
    backgroundColor: "{colors.office}"
  chart-series-secondary:
    backgroundColor: "{colors.secondary}"
  chart-series-secondary-mid:
    backgroundColor: "{colors.secondary-mid}"
  chart-bar-light:
    backgroundColor: "{colors.neutral-light}"
  chart-series-primary-mid:
    backgroundColor: "{colors.primary-mid}"
  chart-line:
    backgroundColor: "{colors.primary}"
    width: 2.5px
    size: 6px
  form-control:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.input-compact}"
    rounded: "{rounded.sm}"
    height: 32px
    padding: 2px 10px
  form-label:
    textColor: "{colors.on-surface}"
    typography: "{typography.label-control}"
  table-header:
    backgroundColor: "{colors.background}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-control}"
    height: 28px
    padding: 4px 8px
  table-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.input-compact}"
    height: 26px
    padding: 3px 8px
---

# Fab Staffing Simulator — Clear Blue

## Overview
임원 보고와 실무 입력을 함께 쓰는 **분석 대시보드**예요. 밝은 회색 바탕(`background`) 위에 흰 카드(`surface`)를 띄우고, 일반 수치는 **검정·그레이 모노크롬**, 의미색은 **긍정 = 블루, 부정 = 레드** 두 가지뿐이에요(Tufte의 data-ink 원칙, 2026-11-21 개편: 녹색·주황 삭제). 숫자가 주인공이라 큰 굵은 숫자, 작은 라벨, 넉넉한 여백으로 읽히게 해요. 장식(그라데이션 배경, 큰 그림자, 이모지)은 쓰지 않아요.

스타일 참고: Dribbble "Shopeers — AI-Powered B2B eCommerce Analytics Dashboard"(Dipa Inhouse)의 색상표와 카드·차트 표현 규칙만 참고했어요. 화면 구성·브랜드·로고는 가져오지 않아요.

## Colors
- **Primary (#0A24E9):** 주 버튼, 선택된 메뉴, 강조할 차트 요소 하나, 링크. 한 화면에 강조는 적게 써요.
- **Primary strong (#152EAE):** 눌렀을 때·마우스를 올렸을 때.
- **Primary soft (#E8ECFE):** 선택된 메뉴·행의 배경.
- **Secondary (#29315D):** 보조 제목, 아이콘.
- **On-surface (#0B0D17) / muted (#5B6475):** 본문·숫자 / 보조 설명. `neutral(#A9B6C0)`은 글자에 쓰지 않아요(대비 2.1:1). 비활성 막대·눈금선에만 써요.
- **Background (#F0F2F5), Surface (#FFFFFF), Outline (#CACED6):** 바탕, 카드, 얇은 테두리·구분선.
- **3색 체계:** ① 바탕·일반 데이터 = 모노크롬(on-surface, muted, outline, background, surface, 단순 현황 막대 neutral `#A9B6C0` ~ neutral-light `#D0D5DD`) ② **긍정 = 블루**(primary `#0A24E9`, primary-strong, primary-soft `#E8ECFE` 배지 바탕): FTE 확보, 공수 절감, 목표 달성, 여유, 브리지 증가 ③ **부정 = 레드**(error `#B42318`, error-soft `#FCE8E7` 배지 바탕): 인력 부족, 과부하(OT), 목표 미달, 브리지 감소, 재배치 대상, 미반영 계획, 오류. 녹색·주황·보라는 쓰지 않아요.
- **구분색(뜻 없는 범주):** 블루·네이비·그레이 톤온톤만 — primary → secondary(`#29315D`) → muted(`#5B6475`) → primary-strong → primary-mid(`#8E9AF5`) → neutral → secondary-mid(`#3E4784`) → neutral-light. 직군: 공정 = primary, 설비 = secondary(네이비). 근무형태: 교대(shift) = primary, 오피스(office) = primary-mid.
- 브리지 합계 기둥(REF·COMPARE)은 secondary(네이비).

## Typography
- 글꼴은 **Pretendard**. 사내망에서 웹 글꼴을 못 받으면 `"Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif` 순서로 대신해요.
- **Pretendard를 고른 이유:** 영문·숫자(Inter 기반)와 한글의 높이·자간 균형이 자연스럽고, 9단계 굵기와 가변 글꼴을 지원해요. 사내 관리 화면처럼 숫자·한글·영문 약어(FTE, AX, REF)가 섞이는 화면에 범용으로 맞아요.
- 검토한 다른 후보: SUIT(네모꼴, 카드·좁은 버튼 라벨에 깔끔), IBM Plex Sans KR(직선적, 금융·KPI 모니터링에 신뢰감), Wanted Sans(숫자·라틴 약어 가독성). 서체를 바꿀 때는 typography 토큰의 fontFamily와 `.streamlit/config.toml`의 font를 함께 바꿔요.
- 숫자는 표 정렬을 위해 고정폭 숫자(`tnum`)를 써요. KPI 숫자는 `kpi-value`(30px 굵게), 단위(FTE·명)는 `body-sm`.
- 화면 제목 `headline-lg`, 영역 제목 `headline-md`, 본문 `body-md`, 표·보조 설명 `body-sm`, 카드 라벨 `label-md`.

## Layout
- 바탕 위에 카드 격자를 놓아요. 카드 사이 간격 `lg(16px)`, 카드 안쪽 여백 20px.
- 대시보드 순서: 설정(한 줄, 접힘·고정 가능) → KPI 카드 한 줄 → 차트 1행 4열(인력 현황 · 인당 관리 지표 · FTE 추이 · FTE 브리지) → 그룹·파트 비교(선택마다 4열 한 줄) → 표. 차트 높이 300px, 여백 l20 r20 t30 b20(+범례).
- KPI 카드는 데스크톱 5열, 좁은 화면에서는 2열로 접어요.

## Form & Table Density (컴팩트 표준, 2026-11-21)
- **form-controls** — density: compact · control-height **32px**(드롭다운·버튼·세그먼트·토글, `form-control`) · 라벨 12px 600, 아래 여백 2px(`form-label`) · 입력 글자 12px · 모서리 6px(`rounded.sm`) · **vertical-alignment: bottom** · **grid-layout: 4-equal (repeat(4, 1fr))** — 설정·컨트롤 줄은 `st.columns(4, vertical_alignment="bottom")`만 써요. 설명은 위젯 `help=` 툴팁 또는 폼 맨 아래 안내 한 줄로만(칸 안에 `st.caption` 금지). 폼 하단 액션 줄만 [버튼 1.5 : 안내 8.5]를 허용해요.
- **tables** — density: high · header-height **28px**(`table-header`) · row-height **26px**(`table-row`) · font-size 12px · cell-padding 3px 8px. `st.dataframe`은 캔버스라 CSS가 닿지 않아 `row_height=ui.TABLE_ROW_H`(26)를 넘겨요.
- 구현: `app/ui.py`의 `COMPACT_CSS`, `TABLE_ROW_H`. 규칙은 `AGENTS.md` 'UI & Control Layout Rules'에도 있어요.

## Elevation & Depth
그림자 대신 **흰 카드 + 1px outline 테두리**로 층을 나눠요. 떠 있는 요소(확인 창, 펼침 메뉴)에만 아주 옅은 그림자(0 8px 24px, 투명도 8%)를 써요.

## Shapes
- 카드 `lg(16px)`, 버튼·입력·선택 상자 `md(10px)`, 작은 칩 `sm(6px)`, 증감 배지 `full`.
- 막대 차트 막대는 위쪽 모서리를 둥글게(6px) 해요.

## Motion & Micro-interaction
- 상태 변화(마우스 올림, 선택)는 **150ms ease-out**, 펼침·창 등장은 **200ms ease-out**이에요. (규격의 `motion` 키는 지금 쓰는 검사 도구 버전에서 인식되지 않아 값을 본문에만 적어요. 도구가 지원하면 `motion.state-change` / `motion.surface-enter` 토큰으로 옮겨요.)
- 숫자가 바뀔 때 깜빡이거나 튀는 효과는 쓰지 않아요.

## Voice & Content Strategy
- 화면 용어는 "감축"이 아니라 **"FTE 확보"**. 짧고 쉬운 한국어로, 숫자 뒤에 단위를 붙여요(42.1 FTE, 316명).
- 증감은 기호와 색을 함께 써요(▲ 블루, ▼ 레드). 색만으로 뜻을 전하지 않아요.
- 설명 문구는 "왜 그런지"를 한 줄로 알려 줘요(예: "GY 2인 필수에 걸려 있어요").

## Components
- **보조 설명:** `caption` (muted 글자, `body-sm`).
- **KPI 카드:** 라벨(`label-md`) → 큰 숫자(`kpi-value`) = **REF 대비 변화 Δ(COMPARE − REF)**, 증가는 primary(블루)·감소는 error(레드) 색 → COMPARE·REF 막대 두 줄 → "COMPARE x · REF y"(`body-sm`, muted). 팀 전체 카드는 `kpi-card-team`(primary 배경), 나머지는 `card`.
- **증감 배지:** `badge-up`(블루) / `badge-down`(레드), 경고·재배치·미반영 계획 안내는 `badge-warning`(레드). 상태 표시는 🔵 긍정 / ⚪ 보통 / 🔴 부정만 써요.
- **버튼:** 주 동작 하나만 `button-primary`, 나머지는 `button-secondary`.
- **선택된 메뉴·탭:** `nav-item-active`.
- **차트:** 막대 기본 `chart-bar-default`, 강조 `chart-bar-highlight`, 계열 색 `chart-series-shift` / `chart-series-office` / `chart-series-primary-mid` / `chart-series-secondary` / `chart-series-secondary-mid`, 옅은 막대 `chart-bar-light`. 흰 카드 안에 넣고, 눈금선은 outline 색 점선, 축 글자는 muted. 막대 차트는 강조 하나만 primary, 나머지 neutral. 선 차트는 primary 선 + 아래 primary 10% 채움. 선은 점 사이를 곡선으로 잇는다 (`shape: spline`, `smoothing: 1.3`; 굵기·점 크기 = `chart-line`의 width 2.5px · size 6px. design.md 스키마에 shape·smoothing 키가 없어 본문에 적음) — Plotly 템플릿 `clear_blue`의 scatter 기본값과 각 선 트레이스에 함께 지정. 목표선은 실선, 대안 시나리오는 secondary 점선, 실적 막대는 secondary(네이비).
- **표:** 머리 행은 background 색, 행 구분은 outline 1px. 숫자는 오른쪽 정렬.

## Do's and Don'ts
- **Do:** 의미색은 긍정 블루·부정 레드 두 가지만, 나머지는 그레이. 교대 = primary, 오피스 = primary-mid를 모든 화면에서 같게.
- **Do:** 글자와 배경 대비 4.5:1 이상(이 문서의 글자 색 조합은 모두 만족).
- **Don't:** `neutral`·`neutral-light`·`primary-mid`·`office`를 작은 글자색으로 쓰지 않기(대비 부족). 녹색·주황·보라 쓰지 않기.
- **Don't:** 그라데이션 배경, 큰 그림자, 이모지 아이콘, 카드 안에 카드 안에 카드.
- **Don't:** 참고한 디자인의 화면 구성·브랜드·로고를 그대로 옮기지 않기.
