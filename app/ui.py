"""화면 공통: 세션 상태, 계산 캐시, 색, 카드."""
from __future__ import annotations

import streamlit as st

from sim.data import WORK, Dataset, check_table, load_sample, regression_changes, save_config, validate
from sim.engine import Model, Params, State, evaluate
from sim.scenario import compare, trend

# ---- DESIGN.md("Clear Blue") 토큰. 색을 바꿀 때는 DESIGN.md → .streamlit/config.toml → 여기 순서로 맞춰요.
PRIMARY, PRIMARY_STRONG, PRIMARY_SOFT = "#0A24E9", "#152EAE", "#E8ECFE"
SECONDARY, INK, MUTED = "#29315D", "#0B0D17", "#5B6475"
BG, SURFACE, OUTLINE, NEUTRAL = "#F0F2F5", "#FFFFFF", "#CACED6", "#A9B6C0"
NEUTRAL_LIGHT, PRIMARY_MID, SECONDARY_MID = "#D0D5DD", "#8E9AF5", "#3E4784"
ERROR, ERROR_SOFT = "#B42318", "#FCE8E7"
# 3색 체계 (2026-11-21): 바탕·일반 = 그레이, 긍정 = 블루(PRIMARY), 부정 = 레드(ERROR). 녹색·주황 없음
POSITIVE, POSITIVE_SOFT, NEGATIVE, NEGATIVE_SOFT = PRIMARY, PRIMARY_SOFT, ERROR, ERROR_SOFT
SHIFT, OFFICE = PRIMARY, PRIMARY_MID          # 근무형태 구분색 (뜻 없는 범주: 블루 톤)
# 뜻 없는 범주(그룹·대분류·파트) 색: 블루·네이비·그레이 톤온톤
TONES = ["#0A24E9", "#29315D", "#5B6475", "#152EAE", "#8E9AF5", "#A9B6C0", "#3E4784", "#D0D5DD"]
FONT = 'Pretendard, "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif'

CSS = f"""
<style>
html, body, [data-testid="stApp"], .kpi, .pill {{font-family: {FONT};}}
.block-container {{padding-top: 1.2rem; max-width: 1400px;}}
/* 카드: 흰 면 + 1px outline + 16px 모서리 (Elevation: 그림자 대신 테두리) */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{border-radius: 16px;}}
[data-testid="stExpander"] details {{background: {SURFACE}; border-radius: 16px; border-color: {OUTLINE};}}
/* 차트 카드: Streamlit이 차트 칸 높이를 그림 높이로 고정해서 padding·border가 있으면 넘쳐 세로 스크롤이 생겨요.
   → 안쪽 여백은 Plotly margin으로, 테두리는 자리를 차지하지 않는 1px 링(box-shadow)으로 그려요. */
[data-testid="stPlotlyChart"] {{background: {SURFACE}; border-radius: 16px; padding: 0; overflow: hidden;
  box-shadow: 0 0 0 1px {OUTLINE};}}
[data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{overflow: visible;}}
[data-testid="stMetric"] {{background: {SURFACE}; border: 1px solid {OUTLINE}; border-radius: 16px; padding: 14px 16px;
  height: 118px; box-sizing: border-box; overflow: hidden;}}
/* 카드 높이를 맞추려고 라벨·값·보조 줄은 한 줄로, 넘치면 … */
[data-testid="stMetric"] [data-testid="stMetricLabel"] p, [data-testid="stMetricValue"] > div,
[data-testid="stMetricDelta"] > div {{white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.kpi {{border: 1px solid {OUTLINE}; border-radius: 16px; padding: 18px 20px; background: {SURFACE}; height: 100%;}}
.kpi.team {{background: {PRIMARY}; border-color: {PRIMARY};}}
.kpi .t {{font-size: 13px; font-weight: 600; color: {SECONDARY};}}
.kpi.team .t, .kpi.team .v, .kpi.team .s {{color: #FFFFFF;}}
.kpi .v {{font-size: 30px; font-weight: 700; color: {INK}; line-height: 1.15; letter-spacing: -0.02em; font-feature-settings: "tnum" 1;}}
.kpi .s {{font-size: 12px; color: {MUTED};}}
.kpi .bar {{position: relative; height: 8px; border-radius: 6px; background: {BG}; margin: 10px 0 6px;}}
.kpi.team .bar {{background: rgba(255,255,255,0.25);}}
.kpi .bar span {{position: absolute; left: 0; top: 0; height: 8px; border-radius: 6px;}}
.pill {{display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; margin: 0 4px 4px 0;}}
.pill.warn {{background: {ERROR_SOFT}; color: {ERROR};}}
.pill.info {{background: {PRIMARY_SOFT}; color: {PRIMARY};}}
.pill.ok {{background: {PRIMARY_SOFT}; color: {PRIMARY};}}
.pill.bad {{background: {ERROR_SOFT}; color: {ERROR};}}
</style>
"""

# 컴팩트 UI & 고밀도 폼/컨트롤 표준 (32px Density) — REQUIRE.md 2026-11-21, DESIGN.md 'Form & Table Density'.
# st.dataframe은 캔버스로 그려져 CSS가 행 높이에 닿지 않아서, 표는 TABLE_ROW_H(26px)를 row_height로 넘겨요.
COMPACT_CSS = """
<style>
/* 1. 위젯 공통 라벨 */
[data-testid="stWidgetLabel"] label, [data-testid="stWidgetLabel"] p {
    font-size: 12px !important; font-weight: 600 !important; color: #0B0D17 !important;
    margin-bottom: 2px !important; line-height: 1.2 !important;
}
/* 2. Selectbox 32px */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    min-height: 32px !important; height: 32px !important; padding-top: 2px !important; padding-bottom: 2px !important;
    font-size: 12px !important; border-radius: 6px !important;
}
/* 3. Segmented control · button group 32px */
div[data-testid="stSegmentedControl"] [data-testid="stButtonGroup"] button,
div[data-testid="stButtonGroup"] button {
    min-height: 32px !important; height: 32px !important; padding: 2px 10px !important;
    font-size: 12px !important; border-radius: 6px !important; line-height: 1.2 !important;
}
/* 4. 일반 버튼 · 폼 제출 버튼 · 내려받기 버튼 32px */
div[data-testid="stButton"] button, div[data-testid="stFormSubmitButton"] button, div[data-testid="stDownloadButton"] button {
    min-height: 32px !important; height: 32px !important; padding: 2px 14px !important;
    font-size: 12px !important; font-weight: 600 !important; border-radius: 6px !important;
}
/* 5. 토글 */
div[data-testid="stToggle"] { margin-top: 0px !important; padding-top: 0px !important; }
div[data-testid="stToggle"] label { font-size: 12px !important; min-height: 32px !important; display: flex !important; align-items: center !important; }
/* 6. 표 (고밀도) */
[data-testid="stDataFrame"] { font-size: 12px !important; }
table.dataframe, [data-testid="stTable"] table { font-size: 12px !important; line-height: 1.3 !important; border-collapse: collapse !important; }
table.dataframe th, [data-testid="stTable"] th {
    padding: 4px 8px !important; height: 28px !important; font-size: 12px !important; font-weight: 600 !important;
    background-color: #F0F2F5 !important;
}
table.dataframe td, [data-testid="stTable"] td { padding: 3px 8px !important; height: 26px !important; font-size: 12px !important; }
</style>
"""
TABLE_ROW_H = 26          # st.dataframe / st.data_editor 행 높이 (고밀도 표)


def _plotly_template():
    """DESIGN.md의 차트 규칙: 흰 면, outline 점선 눈금, muted 축 글자, 계열 색 = 블루·네이비·그레이 톤온톤 (TONES)."""
    import plotly.graph_objects as go
    import plotly.io as pio
    axis = dict(gridcolor=OUTLINE, griddash="dot", linecolor=OUTLINE, zerolinecolor=OUTLINE,
                tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=MUTED, size=12)))
    pio.templates["clear_blue"] = go.layout.Template(layout=dict(
        font=dict(family=FONT, color=INK, size=12), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        colorway=TONES,
        # 카드 안쪽 여백이 없어서 제목은 카드 왼쪽에서 14px 띄워요
        title=dict(font=dict(size=15, color=INK), x=0, xref="container", xanchor="left", pad=dict(l=14)), xaxis=axis, yaxis=axis,
        legend=dict(font=dict(color=MUTED, size=12), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font=dict(family=FONT)), bargap=0.35),
        # 선 차트는 점 사이를 곡선으로 이어요 (DESIGN.md chart-line)
        data=dict(scatter=[dict(line=dict(shape="spline", smoothing=1.3))]))
    pio.templates.default = "plotly_white+clear_blue"


_plotly_template()


def init():
    ss = st.session_state
    if "ds" not in ss:
        ss.version = 0
        ss.params = Params()
        ss.history = []               # 실적 보정·기준 건당 시간 수정 이력
        replace_dataset(load_sample())
    st.markdown(CSS + COMPACT_CSS, unsafe_allow_html=True)


def default_states(m: Model):
    """현재 연도 기준 기본값: REF = 현재 연도 실적(없으면 POR), COMPARE = 다음 연도 목표."""
    ref = ("actual", m.cur) if m.cur in m.actual_years else ("none", m.por)
    nxt = m.cur + 1 if m.cur + 1 in m.years else m.years[-1]
    return ref, ("target", nxt)


def replace_dataset(ds: Dataset):
    """엑셀 가져오기·샘플 다시 불러오기: 데이터와 함께 화면 선택값(REF/COMPARE·조직개편·차트 범위)을 새로 정해요."""
    ss = st.session_state
    ss.ds = ds
    ss.reorg = "none"
    ss.detail_part = None
    ss.chart_range = None
    ss.edit = None                # 기준정보에서 수정 중인 표 (한 번에 하나)
    bump()
    ss.ref, ss.cmp = default_states(model())


def bump():
    """입력 데이터가 바뀌면 호출: 검사 다시 하고 계산 캐시를 새로 만들어요."""
    ss = st.session_state
    ss.ds.messages = validate(ss.ds)
    ss.version += 1


def set_table(name, df):
    st.session_state.ds.tables[name] = df.reset_index(drop=True)
    bump()


def set_years(por: int, cur: int):
    """POR·현재 연도: 앱 설정 파일(config/settings.json)에 저장하고 REF·COMPARE·차트 연도를 새 기본값으로 맞춰요."""
    ss = st.session_state
    save_config({"POR 연도": por, "현재 연도": cur})
    ss.ds.settings.update({"POR 연도": por, "현재 연도": cur})
    bump()
    ss.ref, ss.cmp = default_states(model())
    ss.chart_range = None


def apply_regression() -> int:
    """설정 [적용] 때: 미래 연도 (회귀) 빈도를 다시 계산해 저장해요. 바뀐 줄 수를 돌려줘요 (안 바뀌면 저장하지 않아요)."""
    new, changed = regression_changes(st.session_state.ds)
    if changed:
        set_table(WORK, new)
    return changed


def regression_stale() -> int:
    """저장된 (회귀) 빈도가 지금 데이터의 회귀와 다른 줄 수 (0 = 최신). [설정 적용]을 누르면 0이 돼요."""
    return _cached(("reg_stale",), lambda: regression_changes(st.session_state.ds)[1])


def check(name, df, hidden=None) -> tuple[list[str], list[str]]:
    """저장 전 검사만: (오류, 경고)"""
    return check_table(name, df, st.session_state.ds, hidden)


def save_table(name, df) -> tuple[list[str], list[str]]:
    """검사를 통과해야 저장해요: (오류, 경고). 오류가 있으면 저장하지 않아요."""
    errs, warns = check(name, df)
    if not errs:
        set_table(name, df)
    return errs, warns


def chart_years(m: Model) -> list[int]:
    """대시보드 차트 범위. 기본 = REF 연도 ~ REF + 4년 (데이터 연도 밖은 잘라요). 직접 고르면 그 값을 유지해요."""
    ref_y = st.session_state.ref[1] if st.session_state.get("ref") else m.por
    a, b = st.session_state.get("chart_range") or (ref_y, ref_y + 4)
    a, b = max(a, m.years[0]), min(b, m.years[-1])
    return [y for y in m.years if a <= y <= b] or list(m.years)


def editor_changed(key) -> bool:
    """st.data_editor에서 실제로 고친 칸·추가·삭제가 있는지"""
    s = st.session_state.get(key)
    return bool(s) and bool(s.get("edited_rows") or s.get("added_rows") or s.get("deleted_rows"))


def model() -> Model:
    ss = st.session_state
    c = ss.get("_model")
    if not c or c[0] != ss.version:
        ss._model = (ss.version, Model(ss.ds))
    return ss._model[1]


def _cached(key, fn):
    ss = st.session_state
    store = ss.setdefault("_calc", {})
    if store.get("_v") != ss.version:
        store.clear(); store["_v"] = ss.version
    if key not in store:
        store[key] = fn()
    return store[key]


def state_label(kind, year):
    return State(year, kind).label()


def ax_options(m: Model):
    """REF/COMPARE 고를 수 있는 시점: POR(AX 없음), 현재 연도까지의 실적, 모든 연도의 목표"""
    return ([("none", m.por)] + [("actual", y) for y in m.actual_years if y <= m.cur]
            + [("target", y) for y in m.years])


def get_compare():
    ss = st.session_state
    p = ss.params
    key = ("cmp", ss.ref, ss.cmp, ss.reorg, p.key())
    return _cached(key, lambda: compare(model(), State(ss.ref[1], ss.ref[0]), ss.cmp[1], ss.cmp[0], ss.reorg, p))


def get_trend():
    p = st.session_state.params
    ys = tuple(chart_years(model()))
    return _cached(("trend", p.key(), ys), lambda: trend(model(), p, ys))


def get_eval(kind, year, plan=False):
    p = st.session_state.params
    return _cached(("eval", kind, year, plan, p.key()), lambda: evaluate(model(), State(year, kind, plan), p))


def reorg_label(r):
    return {"none": "없음", "plan": "계획대로"}.get(r, r)


def kpi_delta(title, value, ref, team=False, hours=None):
    """KPI 카드: 큰 숫자 = Δ(COMPARE − REF), 아래에 COMPARE·REF 값과 막대.
    hours = (COMPARE 업무공수, REF 업무공수) 원값(시간/년)이면 맨 아래 줄에 함께 보여 줘요."""
    delta = value - ref
    scale = max(abs(value), abs(ref), 1.0) * 1.15
    def w(v): return f"{max(0.0, min(100.0, v / scale * 100)):.0f}%"
    sign = "+" if delta >= 0 else "−"
    if team:
        color, track, cmp_bar, ref_bar = "#FFFFFF", "", "#FFFFFF", "rgba(255,255,255,0.55)"
        tag = ""
    else:
        color = POSITIVE if delta > 0.05 else (NEGATIVE if delta < -0.05 else INK)
        cmp_bar, ref_bar = PRIMARY, NEUTRAL
        cls = "ok" if delta > 0.05 else ("bad" if delta < -0.05 else "info")
        tag = f'<span class="pill {cls}" style="float:right;margin:0">{"▲" if delta >= 0 else "▼"} REF 대비</span>'
    return f"""<div class="kpi {'team' if team else ''}">
<div class="t">{title}{tag}</div>
<div class="v" style="color:{color}">{sign}{abs(delta):,.1f} <span style="font-size:13px;font-weight:400">FTE</span></div>
<div class="bar" title="COMPARE"><span style="width:{w(value)};background:{cmp_bar}"></span></div>
<div class="bar" title="REF" style="margin-top:4px"><span style="width:{w(ref)};background:{ref_bar}"></span></div>
<div class="s">COMPARE <b>{value:,.1f}</b> · REF {ref:,.1f}</div>
{_hours_line(hours)}</div>"""


def kpi_na(title, why="선택한 범위에 이 직군·근무형태 파트가 없어요"):
    """대상 파트가 없는 KPI 카드 (카드 수를 그대로 둬서 배치가 흔들리지 않게)"""
    return f"""<div class="kpi" style="background:{BG};border-style:dashed">
<div class="t" style="color:{MUTED}">{title}</div>
<div class="v" style="color:{NEUTRAL}">해당 없음</div>
<div class="s">{why}</div></div>"""


def _hours_line(hours):
    if not hours:
        return ""
    now, ref = hours
    d = now - ref
    return (f'<div class="s" title="업무공수 원값 = 빈도 × 건당 시간 × (1 − 자동화율), 비가동 제외">'
            f'업무공수 {now:,.0f}h/년 ({"+" if d >= 0 else "−"}{abs(d):,.0f}h)</div>')
