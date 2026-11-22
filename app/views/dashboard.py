"""📊 대시보드 — 단일 고정 화면 (REQUIRE.md 2026-11-21, SPEC 결정 이력).

맨 위 통합 설정 패널(영역 A 공통 조건: POR·현재 연도, 대상 범위 직군·그룹·파트, 시뮬레이션 조건 /
영역 B 차트 설정: 연도 범위, 인당 관리 지표, 추이 단위, 업무량 차트 모양)을 바꾸면 아래 4개 섹션이 그 범위로 함께 다시 계산돼요.
  1. KPI 카드 5개 (Δ = COMPARE − REF, 업무공수 병기)
  2. 인적자원: 인력·FTE | FTE 확보 추이 | FTE 브리지 | 근무형태별 확보 → 파트별 결과 표 → 묶음 상세
  3. 업무량: 인당 관리 챔버(설비) | 이벤트 | 루틴 | 이슈 빈도
  4. AX 효과: 대분류별 절감 공수 | 목표 vs 실적 자동화율 → 소분류 요약 표 (COMPARE가 목표면 예측, 실적이면 실제 효과)
그룹보드도 settings_panel을 쓰지만 공통 조건 중 연도·시뮬레이션 조건만 보여요(full=False).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from sim.data import SLOTS, reg_trend, snapshot_years
from sim.engine import Params
from sim.scenario import (REORGS, WORK_TYPES, Scope, ax_detail, bridge_for, freq_series, inscope, per_person, seg_total,
                          year_series)

CHART_H = 320
MARGIN = dict(l=20, r=20, t=30, b=20)
ISSUE = ["연평균", "최대 이슈 1건", "동시 2건"]
ISSUE_SHORT = ["이슈 연평균", "이슈 대비 1건", "이슈 대비 동시 2건"]
OPTS = ["인원 변동", "교차 숙련"]   # 2인 근무는 인원 시트의 최소 인원(2)으로 넣어요
JOB_COLOR = {"공정": ui.PRIMARY, "설비": ui.SECONDARY}          # 공정 = 블루, 설비 = 네이비
# AX 효과 차트의 직군 · 근무형태 구분색 (뜻 없는 범주: 공정 = 블루 계열, 설비 = 네이비·그레이 계열, 교대 = 진하게)
SEGS_AX = ["공정 오피스", "공정 교대", "설비 오피스", "설비 교대"]          # KPI 카드와 같은 순서
# AX 효과 막대 색 = 달성 상태 (DESIGN.md: 긍정 블루 · 부정 레드 · 나머지 그레이). (이름, 색, 빗금)
# 범례는 색 상자로 보여 줘서 이름에 🔵⚪🔴 이모지를 붙이지 않아요 (겹쳐 보여요)
AX_STATUS = {"달성": ("실적 ≥ 목표", ui.PRIMARY, ""), "정상": ("목표의 80% 이상", ui.NEUTRAL, ""),
             "미달": ("그 밖 (미달·지연)", ui.ERROR, ""), "목표 없음": ("목표 없음", ui.NEUTRAL_LIGHT, ""),
             "미보고": ("미보고 (목표가 있는데 그해 실적 칸이 빔)", ui.NEUTRAL_LIGHT, "/"),
             "예측": ("예측 (COMPARE = 목표)", ui.PRIMARY_MID, "")}
WL_MODES = ["누적 막대", "누적 비율", "라인"]
ALL_GROUPS, ALL_PARTS = "전체 그룹", "전체 파트"
# 그룹·대분류 색: 블루·네이비·그레이 톤온톤 (뜻 없는 범주, 순서대로 고정) — DESIGN.md 3색 체계
GROUP_COLORS = list(ui.TONES)


def _gkey(p) -> str:
    return f"{p.site} · {p.group}"


def _all_parts(m):
    """모든 연도 스냅샷의 파트 (그룹을 옮긴 파트는 소속마다 한 번씩)"""
    return [p for y in m.snap_years for p in m.snap[y].values()]


# ---------------------------------------------------------------- 설정 패널
GROWTH = ["증감 예측 반영", "현재 빈도 유지"]


def _grid():
    """설정 패널 한 줄 = 균등 4열, 밑변 정렬 (AGENTS.md UI 규칙)"""
    return st.columns(4, vertical_alignment="bottom")


def _scope_parts(m):
    """고른 직군·그룹에 한 해라도 속했던 파트 (소속은 그해 스냅샷 기준)"""
    ss = st.session_state
    job, group = ss.get("ctl_job") or "전체", ss.get("scope_group") or ALL_GROUPS
    names = {p.name for p in _all_parts(m) if (group == ALL_GROUPS or _gkey(p) == group) and (job == "전체" or p.job == job)}
    return sorted(names, key=lambda n: (_gkey(m.parts[n]), n))


# ---- 칸 하나씩 그리는 위젯 (설명은 모두 help 툴팁) ----
def _w_por(c, m):
    snaps = snapshot_years(st.session_state.ds) or [m.por]
    return c.selectbox("POR 연도", snaps, index=snaps.index(m.por) if m.por in snaps else 0,
                       help="기준 스냅샷 연도. '인원 변동'을 끄면 이 연도 총원으로 고정, REF의 'POR (AX 없음)'. "
                            "앱 설정에 저장돼요(모든 사용자 공통). 바꾸면 REF·COMPARE가 새 기본값으로 맞춰져요")


def _w_cur(c, m):
    return c.selectbox("현재 연도", m.years, index=m.years.index(m.cur) if m.cur in m.years else 0,
                       help="실적 구간의 마지막 연도. 이후는 예측 구간이고, 회귀 예측은 현재 연도 −2년 ~ 현재 연도 (입력) 빈도로 해요. "
                            "앱 설정에 저장돼요(모든 사용자 공통)")


def _w_job(c):
    with c:
        st.segmented_control("직군", ["전체", "공정", "설비"], default="전체", key="ctl_job",
                             help="대시보드 전체(KPI·인적자원·업무량·AX 효과)를 이 직군으로 다시 계산해요")


def _w_group(c, m):
    ss = st.session_state
    groups = sorted({_gkey(p) for p in _all_parts(m)})
    if ss.get("scope_group") not in [ALL_GROUPS] + groups:
        ss.scope_group = ALL_GROUPS
    c.selectbox("그룹 선택", [ALL_GROUPS] + groups, key="scope_group", help="고른 그룹으로 대시보드 전체를 다시 계산해요")


def _w_part(c, m):
    ss = st.session_state
    parts = _scope_parts(m)
    if ss.get("scope_part") not in [ALL_PARTS] + parts:
        ss.scope_part = ALL_PARTS                    # 직군·그룹과 안 맞는 파트는 '전체 파트'로 (위젯을 그리기 전에 고쳐요)
    c.selectbox("파트 선택", [ALL_PARTS] + parts, key="scope_part",
                help="적용된 직군·그룹의 파트만 보여요 (그룹을 바꾸면 [설정 적용] 뒤에 목록이 바뀌어요). 폐지된 파트도 골라 볼 수 있어요")


def _w_ref(c, m):
    ss = st.session_state
    opts = ui.ax_options(m)
    return c.selectbox("REF (기준)", opts, index=opts.index(ss.ref) if ss.ref in opts else 0,
                       format_func=lambda o: ui.state_label(*o), help="KPI 변화량(Δ)과 FTE 브리지의 시작점")


def _w_cmp(c, m):
    ss = st.session_state
    opts = [o for o in ui.ax_options(m) if o[0] != "none"]
    return c.selectbox("COMPARE (비교)", opts, index=opts.index(ss.cmp) if ss.cmp in opts else 0,
                       format_func=lambda o: ui.state_label(*o),
                       help="KPI 목표치와 FTE 브리지의 종착점, AX 효과·파트별 결과 표의 기준 시점. 목표 = 예측, 실적 = 실제 효과 분석")


def _w_reorg(c):
    ss = st.session_state
    reorgs = list(REORGS)
    return c.selectbox("계획 묶음 반영 (COMPARE)", reorgs, index=reorgs.index(ss.reorg) if ss.reorg in reorgs else 0,
                       format_func=ui.reorg_label,
                       help="조직변경 시트의 '계획' 파트 묶음을 COMPARE에 반영할지 ('실적' 묶음은 늘 반영). "
                            "파트 신설·폐지·그룹 이동은 이 선택과 상관없이 그해 인원 시트 명단대로 계산해요")


def _w_issue(c):
    return c.selectbox("이슈 대비", [0, 1, 2], index=st.session_state.params.issue_level, format_func=lambda i: ISSUE[i],
                       help="돌발 설비·품질 사고에 대비하는 예비 인원. 모든 차트의 필요 인원에 반영돼요")


def _w_opts(c):
    ss = st.session_state
    p = ss.params
    cur = [o for o, on in zip(OPTS, (p.headcount_change, p.cross_skill)) if on]
    with c:
        sel = st.segmented_control("계산 옵션", OPTS, default=cur, selection_mode="multi", key=f"opt_{ss.version}",
                                   help="인원 변동 = 연도별 인원 스냅샷 총원 적용(끄면 POR 총원 고정). "
                                        "교차 숙련 = 묶음에서 근무대마다 파트별 최소 1명이 필요하다는 조건")
    return sel if sel is not None else cur


def _w_growth(c):
    return c.selectbox("미래 빈도", GROWTH, index=0 if st.session_state.params.freq_growth else 1,
                       help="증감 예측 반영 = 현재 연도 이후는 그해 빈도((입력) 값, 없으면 (회귀) 예측)로 FTE 계산. "
                            "현재 빈도 유지 = 현재 연도 빈도를 이어서 계산. 업무량 차트도 이 선택을 따라요")


def _chart_row(m):
    """영역 B: 차트 기간 | 인당 관리 지표 | 추이 단위 | 업무량 차트"""
    ss = st.session_state
    yrs = ui.chart_years(m)
    c = _grid()
    a, b = c[0].columns(2, vertical_alignment="bottom")
    y0 = a.selectbox("차트 시작", m.years, index=m.years.index(yrs[0]), key=f"cr0_{ss.version}_{yrs[0]}",
                     help="기본은 REF ~ REF+4년이에요. REF를 바꾸면 다시 REF를 따라가요")
    y1 = b.selectbox("차트 끝", m.years, index=m.years.index(yrs[-1]), key=f"cr1_{ss.version}_{yrs[-1]}")
    with c[1]:
        st.segmented_control("인당 관리 지표", ["챔버", "설비"], default="챔버", key="ctl_met", help="업무량 첫 차트의 인당 관리 대수")
    with c[2]:
        st.segmented_control("추이 단위", ["FTE", "공수"], default="FTE", key="ctl_unit", help="공수 = 연간 업무시간(시간/년)")
    with c[3]:
        st.segmented_control("업무량 차트", WL_MODES, default=WL_MODES[0], key="ctl_wl",
                             help="실적 구간은 선명하게, 예측 구간은 흐리게·점선으로 그려요")
    return y0, y1


def _scope(m) -> dict:
    """적용된 설정 값 → 범위(names, job)와 차트 설정"""
    ss = st.session_state
    job = ss.get("ctl_job") or "전체"
    group, part = ss.get("scope_group") or ALL_GROUPS, ss.get("scope_part") or ALL_PARTS
    job = None if job == "전체" else job
    names = None                       # 범위: 그해 소속 기준 (sim.scenario.Scope)
    if group != ALL_GROUPS or part != ALL_PARTS:
        names = Scope(None if group == ALL_GROUPS else group, None if part == ALL_PARTS else part)
    label = part if part != ALL_PARTS else (group if group != ALL_GROUPS else "팀 전체")
    return {"names": names, "job": job, "label": label + (f" · {job}" if job else ""),
            "met": ss.get("ctl_met") or "챔버", "unit": ss.get("ctl_unit") or "FTE", "wl": ss.get("ctl_wl") or WL_MODES[0]}


def _apply(m, years, sim, chart):
    """[설정 적용]: 연도 → 시뮬레이션 조건 → 차트 연도 → 회귀 예측((회귀) 빈도) 순으로 반영하고 한 번에 다시 계산해요.
    연도를 바꿔도 함께 바꾼 시뮬레이션 조건(이슈 대비·계산 옵션·미래 빈도·계획 묶음)은 그대로 반영해요.
    REF·COMPARE는 직접 바꿨고 새 연도에서도 고를 수 있으면 그 값, 아니면 새 기본값이에요."""
    ss = st.session_state
    notes = []
    ref, cmp, reorg, newp = sim
    ref_changed, cmp_changed = ref != ss.ref, cmp != ss.cmp
    ss.reorg, ss.params = reorg, newp
    if years != (m.por, m.cur):
        ui.set_years(*years)               # REF·COMPARE·차트 연도를 새 기본값으로 맞춘 뒤, 직접 고른 값은 되살려요
        opts = ui.ax_options(ui.model())
        kept, reset = [], []
        for name, want, changed, ok in (("REF", ref, ref_changed, opts),
                                         ("COMPARE", cmp, cmp_changed, [o for o in opts if o[0] != "none"])):
            if not changed:
                continue
            if want in ok:
                setattr(ss, "ref" if name == "REF" else "cmp", want)
                kept.append(f"{name} {ui.state_label(*want)}")
            else:
                reset.append(f"{name} {ui.state_label(*want)}")
        how = ("REF·COMPARE 새 기본값" if not kept else " · ".join(kept) + " 유지")
        notes.append(f"POR {years[0]} · 현재 {years[1]} ({how})")
        if reset:
            notes.append(f"{', '.join(reset)}은(는) 새 연도에서 고를 수 없어 기본값으로 바꿨어요")
    else:
        ss.ref, ss.cmp = ref, cmp
        if ref_changed:
            ss.chart_range = None          # 차트 연도는 다시 REF ~ REF+4로
        elif chart is not None:
            yrs = ui.chart_years(ui.model())
            y0, y1 = min(chart), max(chart)
            if (y0, y1) != (yrs[0], yrs[-1]):
                ss.chart_range = (y0, y1)
    n = ui.apply_regression()
    notes.append(f"회귀 예측 {n}줄 갱신" if n else "회귀 예측 변화 없음")
    ss._flash_settings = "설정을 적용했어요 — " + " · ".join(notes)
    st.rerun()


def settings_panel(m, full=False):
    """맨 위 설정 패널 (균등 4열 · 밑변 정렬 · 설명은 help 툴팁). 값을 바꿔도 [설정 적용]을 눌러야 반영돼요(회귀 예측도 그때 다시 계산).
    full=True(대시보드) = 영역 A(연도·범위·시뮬레이션 3줄) + 영역 B(차트 설정), False(그룹보드) = 연도·시뮬레이션 2줄."""
    ss = st.session_state
    p = ss.params
    summary = (f"POR {m.por} · 현재 {m.cur} · REF **{ui.state_label(*ss.ref)}** → COMPARE **{ui.state_label(*ss.cmp)}** · "
               f"계획 묶음 {ui.reorg_label(ss.reorg)} · "
               f"{ISSUE_SHORT[p.issue_level]}{' · 인원 변동' if p.headcount_change else ' · 인원 POR 고정'}"
               f" · {'교차 숙련 조건' if p.cross_skill else '교차 숙련 전제'}"
               f" · 미래 빈도 {GROWTH[0] if p.freq_growth else GROWTH[1]}")
    if full:
        sc = _scope(m)
        yrs = ui.chart_years(m)
        summary = (f"범위 **{sc['label']}** · " + summary +
                   f" · 차트 {yrs[0]}~{yrs[-1]} · 인당 {sc['met']} · 추이 {sc['unit']} · 업무량 {sc['wl']}")
    stale = ui.regression_stale()
    if stale:
        summary += (f' <span class="pill warn">⚠️ 회귀 예측 갱신 필요 — 빈도가 바뀌어 미래 {stale}줄이 예전 예측이에요. '
                    f'[설정 적용]을 누르세요</span>')
    h1, h2 = st.columns([10, 2], vertical_alignment="center")
    h1.markdown(summary, unsafe_allow_html=True)
    pinned = h2.toggle("설정 고정", key="pin_settings", help="켜면 설정 패널이 항상 펼쳐져 있어요")
    msg = ss.pop("_flash_settings", None)
    if msg:
        st.success(msg)
    # 제목을 고정해 두어야 값을 바꿀 때 패널이 저절로 닫히지 않아요
    box = st.container(border=True) if pinned else st.expander("설정", expanded=False)
    with box:
        with st.form("settings_form", border=False):
            chart = None
            if full:
                st.markdown("**A. 공통 조건** <span style='font-size:12px;color:#5B6475'>— 대시보드 전체에 적용</span>",
                            unsafe_allow_html=True)
                r1, r2, r3 = _grid(), _grid(), _grid()
                por, cur_y = _w_por(r1[0], m), _w_cur(r1[1], m)
                _w_job(r1[2]); _w_group(r1[3], m)
                _w_part(r2[0], m)
                ref, cmp, reorg = _w_ref(r2[1], m), _w_cmp(r2[2], m), _w_reorg(r2[3])
                lvl, sel, growth = _w_issue(r3[0]), _w_opts(r3[1]), _w_growth(r3[2])
                st.divider()
                st.markdown("**B. 차트 설정** <span style='font-size:12px;color:#5B6475'>— 표현 방식</span>",
                            unsafe_allow_html=True)
                chart = _chart_row(m)
            else:
                r1, r2 = _grid(), _grid()
                por, cur_y = _w_por(r1[0], m), _w_cur(r1[1], m)
                ref, cmp = _w_ref(r1[2], m), _w_cmp(r1[3], m)
                reorg, lvl, sel, growth = _w_reorg(r2[0]), _w_issue(r2[1]), _w_opts(r2[2]), _w_growth(r2[3])
            btn_c, cap_c = st.columns([1.5, 8.5], vertical_alignment="center")
            submitted = btn_c.form_submit_button("✅ 설정 적용", type="primary", width="stretch")
            cap_c.caption("설정을 바꾼 뒤 [설정 적용]을 누르면 대시보드 전체 계산과 미래 회귀 예측이 한 번에 갱신돼요.")
        if submitted:
            newp = Params(issue_level=lvl, headcount_change="인원 변동" in sel, cross_skill="교차 숙련" in sel,
                          freq_growth=growth == GROWTH[0])
            _apply(m, (por, cur_y), (ref, cmp, reorg, newp), chart)
    return _scope(m) if full else None


# ---------------------------------------------------------------- 공통 차트 모양
def _layout(fig, title, legend=True, height=CHART_H, align=False, left=40):
    """align=True (4열 차트): 아래 여백을 범례 두 줄 자리로 고정하고 자동으로 늘리지 않아요.
    범례 줄 수·범례 유무와 상관없이 네 차트의 X축 높이가 같아져요."""
    b = MARGIN["b"] + (70 if align else (40 if legend else 0))
    fig.update_layout(title=dict(text=title, font=dict(size=13)), height=height,
                      # 자동 여백을 끄면 축 글자 자리도 안 늘어나서, 왼쪽 여백(left)을 차트마다 정해 줘요
                      margin=dict(MARGIN, b=b, l=left if align else MARGIN["l"], autoexpand=not align),
                      showlegend=legend, legend=dict(orientation="h", yanchor="top", y=-0.13 if align else -0.2, x=0,
                                                     font=dict(size=10), traceorder="normal"),
                      xaxis=dict(tickfont=dict(size=10)), yaxis=dict(tickfont=dict(size=10)))
    return fig


def _cur_line(fig, years):
    """현재 연도까지 = 실적 구간, 이후 = 목표 구간 (경계에 점선)"""
    cur = ui.model().cur
    if years[0] <= cur < years[-1]:
        fig.add_vline(x=cur + 0.5, line=dict(color=ui.NEUTRAL, width=1, dash="dot"))
        fig.add_annotation(x=cur + 0.5, y=1, yref="paper", text="현재", showarrow=False, xanchor="left",
                           yanchor="bottom", font=dict(size=9, color=ui.MUTED))


def _move_marks(fig, moves):
    """그룹 이동이 있는 해에 표시 (그룹 범위에서는 옮긴 해부터 숫자가 계단처럼 바뀌어요)"""
    by = {}
    for y, part, a, b in moves:
        by.setdefault(y, []).append(f"{part}: {a} → {b}")
    for y, txt in by.items():
        fig.add_annotation(x=y, y=1, yref="paper", text="↔ 그룹 이동", showarrow=False, yanchor="bottom",
                           font=dict(size=9, color=ui.SECONDARY), hovertext="<br>".join(txt))


def _section(no, title, caption):
    st.markdown(f"### {no}. {title}")
    st.caption(caption)


# ---------------------------------------------------------------- 1. KPI
SEGS = [(None, None), ("공정", "오피스"), ("공정", "교대"), ("설비", "오피스"), ("설비", "교대")]


def _cards(m, c, sc):
    names, job = sc["names"], sc["job"]
    in_scope = [p for p in _all_parts(m) if inscope(names, p) and (job is None or p.job == job)]
    cols = st.columns(5)
    for col, (sjob, kind) in zip(cols, SEGS):
        if sjob is None:
            title = sc["label"]
            v, hv = seg_total(c.cmp, names, job)
            rv, hr = seg_total(c.ref, names, job)
            col.markdown(ui.kpi_delta(title, v, rv, team=True, hours=(hv, hr)), unsafe_allow_html=True)
            continue
        title = f"{sjob} {kind}"
        ok = (job is None or job == sjob) and any(p.job == sjob and (kind == "오피스" or not p.office_only) for p in in_scope)
        if not ok:
            col.markdown(ui.kpi_na(title), unsafe_allow_html=True)
            continue
        v, hv = seg_total(c.cmp, names, sjob, kind)
        rv, hr = seg_total(c.ref, names, sjob, kind)
        col.markdown(ui.kpi_delta(title, v, rv, hours=(hv, hr)), unsafe_allow_html=True)
    note = ("큰 숫자 = REF 대비 FTE 확보 변화(Δ = COMPARE − REF). FTE 확보 = (총원 − 재배치 대상) − 필요 인원. "
            "업무공수 = 빈도 × 건당 시간 × (1 − 자동화율) 원값(비가동 제외).")
    reloc = [(n, h, y) for n, h, y in c.cmp.relocation
             if n in m.parts and inscope(names, m.parts[n]) and (job is None or m.parts[n].job == job)]
    if reloc:
        txt = ", ".join(f"{n} {h:.0f}명 ({y})" for n, h, y in reloc)
        st.markdown(f'<span class="pill warn">재배치 대상 {sum(h for _, h, _ in reloc):.0f}명 — {txt} · FTE 확보와 별도</span> '
                    f'<span style="font-size:12px;color:{ui.MUTED}">{note}</span>', unsafe_allow_html=True)
    else:
        st.caption(note)


# ---------------------------------------------------------------- 2. 인적자원
def _chart_people(ys, key, sub, moves=()):
    years = ys["year"]
    fig = go.Figure()
    fig.add_bar(x=years, y=ys["need"], name="필요 인원", marker_color=ui.NEUTRAL)
    fig.add_bar(x=years, y=ys["secured"], name="FTE 확보", marker_color=ui.PRIMARY)
    fig.add_bar(x=years, y=ys["reloc"], name="재배치 대상", marker_color=ui.NEGATIVE)
    fig.add_scatter(x=years, y=ys["head"], name="총원", mode="text", text=[f"{h:,.0f}" for h in ys["head"]],
                    textposition="top center", textfont=dict(size=10, color=ui.MUTED), showlegend=False)
    top = max([h for h in ys["head"] if h] + [1])
    fig.update_layout(barmode="relative", xaxis=dict(dtick=1), yaxis=dict(range=[min(0, min(ys["secured"]) * 1.2), top * 1.15]))
    _cur_line(fig, years)
    _move_marks(fig, moves)
    st.plotly_chart(_layout(fig, f"인력 · FTE 종합 현황{sub} (목표)", align=True), theme=None, key=f"ppl_{key}")


def _chart_trend(ys, key, unit, sub, has_plan, moves=()):
    years = ys["year"]
    fig = go.Figure()
    if unit == "공수":
        act, tgt, title = ys["h_act"], ys["h_tgt"], f"POR 대비 확보 업무공수 (시간/년){sub}"
    else:
        act, tgt, title = ys["actual"], ys["no_reorg"], f"연도별 FTE 확보 추이{sub}"
    a = [(y, v) for y, v in zip(years, act) if v is not None]
    if a:
        fig.add_bar(x=[p for p, _ in a], y=[q for _, q in a], name="실적", marker_color=ui.SECONDARY, width=0.5)
    fig.add_scatter(x=years, y=tgt, name="목표", mode="lines+markers", line=dict(color=ui.PRIMARY, width=2.5, shape="spline", smoothing=1.3))
    if unit == "FTE" and has_plan:
        fig.add_scatter(x=years, y=ys["plan"], name="목표 + 계획 묶음", mode="lines+markers",
                        line=dict(color=ui.PRIMARY, width=2, dash="dash", shape="spline", smoothing=1.3), marker=dict(symbol="circle-open"))
    fig.update_layout(xaxis=dict(dtick=1))
    _cur_line(fig, years)
    _move_marks(fig, moves)
    st.plotly_chart(_layout(fig, title, align=True), theme=None, key=f"tr_{key}")


SHORT = {"REF FTE 확보": "REF", "인원 변동": "인원 변동", "AX 효과": "AX", "묶음 효과": "묶음",
         "조직 변경": "조직 변경", "재배치 대상 제외": "재배치", "COMPARE FTE 확보": "COMPARE"}


def _chart_bridge(b, key, sub):
    names = [SHORT[x[0]] for x in b]
    vals = [x[2] for x in b]
    fig = go.Figure(go.Waterfall(
        orientation="h", y=names, x=vals, measure=["absolute"] + ["relative"] * 5 + ["total"],
        text=[f"{v:+,.1f}" if 0 < i < 6 else f"{v:,.1f}" for i, v in enumerate(vals)], textposition="outside",
        textfont=dict(size=10), hovertext=[f"{x[0]}: {x[1]}" for x in b], hoverinfo="text",
        increasing=dict(marker=dict(color=ui.POSITIVE)), decreasing=dict(marker=dict(color=ui.NEGATIVE)),
        totals=dict(marker=dict(color=ui.SECONDARY)), connector=dict(line=dict(color=ui.OUTLINE, dash="dot"))))
    cum, lo, hi = 0.0, 0.0, 0.0
    for i, v in enumerate(vals):
        cum = v if i in (0, 6) else cum + v
        lo, hi = min(lo, cum), max(hi, cum)
    span = (hi - lo) or 1
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(range=[lo - span * 0.22, hi + span * 0.28]))
    st.plotly_chart(_layout(fig, f"FTE 브리지 (REF → COMPARE){sub}", legend=False, align=True, left=80), theme=None, key=f"br_{key}")


def _chart_share(ys, key, sub):
    """근무형태별 FTE 확보: 교대·오피스 수량 누적 (마이너스 = 부족은 0 아래로), 위 숫자 = 합계, 툴팁 = 비중"""
    years = ys["year"]
    fig = go.Figure()
    tot = [a + b for a, b in zip(ys["shift"], ys["office"])]
    for name, vals, color in (("교대 FTE 확보", ys["shift"], ui.SHIFT), ("오피스 FTE 확보", ys["office"], ui.OFFICE)):
        share = [(v / t if t else 0) for v, t in zip(vals, tot)]
        fig.add_bar(x=years, y=vals, name=name, marker_color=color, customdata=share,
                    hovertemplate=f"{name}<br>%{{x}}: %{{y:+.1f}} FTE (합계의 %{{customdata:.0%}})<extra></extra>")
    fig.add_scatter(x=years, y=[max(0, a) + max(0, b) for a, b in zip(ys["shift"], ys["office"])], mode="text",
                    text=[f"{t:+.1f}" for t in tot], textposition="top center", textfont=dict(size=10, color=ui.MUTED),
                    showlegend=False, hoverinfo="skip")
    fig.add_hline(y=0, line=dict(color=ui.OUTLINE, width=1))
    hi = max([max(0, a) + max(0, b) for a, b in zip(ys["shift"], ys["office"])] + [1])
    lo = min([min(0, a) + min(0, b) for a, b in zip(ys["shift"], ys["office"])] + [0])
    fig.update_layout(barmode="relative", xaxis=dict(dtick=1), yaxis=dict(range=[lo * 1.2, hi * 1.2]))
    _cur_line(fig, years)
    st.plotly_chart(_layout(fig, f"근무형태별 FTE 확보{sub} (목표, 위 = 합계)", align=True), theme=None, key=f"sh_{key}")


def part_table(k, names=None, job=None) -> pd.DataFrame:
    rows = []
    for r in k.parts:
        p = r.part
        if not inscope(names, p) or (job and p.job != job):
            continue
        s = r.secured
        state = f"🔵 여유 (+{s:.1f}명)" if s > 0.1 else (f"🔴 부족 ({-s:.1f}명)" if s < -0.1 else "⚪ 적정")
        rows.append({
            "SITE": p.site, "그룹": p.group, "파트": p.name, "직군": p.job, "총원": round(r.head, 1),
            "필요 인원": round(r.need, 1), "교대 확보": round(r.secured_shift, 1), "오피스 확보": round(r.secured_office, 1),
            "FTE 확보": round(s, 1),
            "근무대 자리 (현재 → 필요)": "—" if p.office_only else
            f"{'/'.join(str(int(p.slots[x])) for x in SLOTS)} → {'/'.join(str(r.shift.seats[x]) for x in SLOTS)}{'*' if r.bundle else ''}",
            "상태": state,
        })
    return pd.DataFrame(rows)


def _parts(m, c, sc):
    df = part_table(c.cmp, sc["names"], sc["job"])
    a, b = st.columns([4, 1], vertical_alignment="bottom")
    a.markdown(f"**파트별 결과** <span style='font-size:12px;color:{ui.MUTED}'>· COMPARE {c.cmp.state.label()} · "
               f"{len(df)}개 파트 · 🔵 여유 / ⚪ 적정 (±0.1) / 🔴 부족</span>", unsafe_allow_html=True)
    b.download_button("결과 내보내기 (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "FTE확보_파트별.csv", "text/csv",
                      width="stretch", disabled=df.empty)
    if df.empty:
        st.caption("선택한 범위에 COMPARE 연도에 운영 중인 파트가 없어요."); return
    st.dataframe(df, hide_index=True, row_height=ui.TABLE_ROW_H)
    d1, d2 = st.columns([3, 1])
    pick = d1.selectbox("파트 정보 보기", df["파트"].tolist(), key="dash_pick", label_visibility="collapsed")
    if d2.button("그룹보드에서 보기", width="stretch"):
        p = m.parts[pick]
        st.session_state.detail_part = pick
        st.session_state.diag_part = pick
        st.session_state.grp_sel = [_gkey(p)]      # 그 파트의 그룹을 골라 둔 채로 열어요
        st.switch_page(st.session_state.pages["group"])
    st.caption("* 묶음 안에서 자리를 함께 써요. 묶음 파트의 필요 인원은 묶음 결과를 업무량 비율로 나눈 참고값이에요.")


def _reorg_and_diagnose(c, sc):
    """파트별 결과 펼침 안의 '묶음 상세' 구역 (펼침 안에는 펼침을 또 넣을 수 없어서 소제목으로)"""
    names, job = sc["names"], sc["job"]
    st.markdown("**조직개편(묶음) 상세 · 왜 더 확보되지 않나요**")
    rows = c.cmp.bundle_rows
    if rows:
        df = pd.DataFrame(rows)
        for col in ("단독 필요", "묶음 필요", "묶음 효과"):
            df[col] = df[col].round(1)
        df["자리"] = df["자리"].map(lambda s: " / ".join(str(s[x]) for x in SLOTS) if s else "")
        st.dataframe(df.sort_values(["시작", "묶음"])[["시작", "묶음", "구분", "파트", "단독 필요", "묶음 필요", "묶음 효과", "자리"]],
                     hide_index=True, row_height=ui.TABLE_ROW_H, column_config={"시작": st.column_config.NumberColumn("적용 시작", format="%d"),
                                                     "구분": "계획 / 실적", "자리": "묶음 자리 D / S / G"})
        st.caption("묶음은 교대·오피스를 함께 합쳐요. 단독 필요 = 묶기 전 파트별 필요 인원의 합. (묶음 표는 범위와 상관없이 전체)")
    else:
        st.caption("COMPARE 연도에 적용되는 묶음이 없어요. '계획' 묶음은 설정의 '계획 묶음 반영'에서 '계획대로'를 고르면 반영돼요.")
    by = {}
    for r in c.cmp.parts:
        if not inscope(names, r.part) or (job and r.part.job != job):
            continue
        for s in SLOTS:
            w = r.shift.why.get(s)
            if w in ("물리 업무", "최소 인원", "교차 숙련") and r.shift.work.get(s, 0) < r.shift.floor.get(s, 0) - 0.3:
                by.setdefault(w, []).append(f"{r.part.name} {s}")
    msgs = [f"**{w}**에 걸린 근무대 {len(v)}곳: {', '.join(v[:6])}{' …' if len(v) > 6 else ''}" for w, v in by.items()]
    if msgs:
        st.markdown("\n".join(f"- {x}" for x in msgs))


def _people(m, c, tr, sc):
    _section(2, "인적자원", "연도별 필요 인원·FTE 확보(목표), 추이(실적 막대·목표 선), REF → COMPARE 브리지, 교대·오피스별 확보.")
    names, job = sc["names"], sc["job"]
    sub = f" · {sc['label']}" if (names is not None or job) else ""
    ys = year_series(m, tr, names, plan=st.session_state.reorg == "plan", job=job)
    # 그룹 범위면 그 그룹으로 들고 난 파트가 있는 해를 표시 (팀 전체·파트 하나는 합계가 바뀌지 않아요)
    grp = names.group if isinstance(names, Scope) and names.part is None else None
    moves = [mv for mv in m.group_moves() if grp in (mv[2], mv[3]) and mv[0] in ys["year"]
             and (job is None or m.parts[mv[1]].job == job)] if grp else []
    cols = st.columns(4, gap="small")
    with cols[0]:
        _chart_people(ys, "team", sub, moves)
    with cols[1]:
        _chart_trend(ys, "team", sc["unit"], sub, m.has_plan, moves)
    with cols[2]:
        _chart_bridge(bridge_for(c, names, job, m), "team", sub)
    with cols[3]:
        _chart_share(ys, "team", sub)
    # 대시보드는 차트 위주: 파트별 결과 표 · 그룹보드에서 보기 · 묶음 상세는 펼쳐서 봐요
    with st.expander(f"파트별 결과 · 그룹보드에서 보기 · 묶음 상세 — COMPARE {c.cmp.state.label()}", expanded=False):
        _parts(m, c, sc)
        st.divider()
        _reorg_and_diagnose(c, sc)


# ---------------------------------------------------------------- 3. 업무량
def _chart_per_person(m, tr, names, key, jobs, met, sub):
    """인당 관리 챔버(설비) 수: 실적 = 막대, 목표 = 선. 공정·설비를 나눠 그려요."""
    years = tr["year"]
    fig = go.Figure()
    for job in jobs:
        pp = per_person(m, tr, names, job, met)
        col = JOB_COLOR[job]
        act = [(y, v) for y, v in zip(years, pp["actual"]) if v is not None]
        if act:
            fig.add_bar(x=[a for a, _ in act], y=[b for _, b in act], name=f"{job} 실적", marker_color=col, opacity=0.45)
        fig.add_scatter(x=years, y=pp["target"], name=f"{job} 목표", mode="lines+markers", line=dict(color=col, width=2.5, shape="spline", smoothing=1.3))
    fig.update_layout(xaxis=dict(dtick=1), barmode="group")
    _cur_line(fig, years)
    st.plotly_chart(_layout(fig, f"인당 관리 {met} 수{sub}", align=True), theme=None, key=f"pp_{key}")


def _chart_freq(fs, typ, mode, key, sub, cur, trend):
    """업무 빈도 (대분류별). 현재 연도까지 = 실적(선명), 이후 = 예측(흐리게 / 점선).
    trend = 연도 → 총합 1차 회귀 추세 (누적 막대에서 점선으로 겹쳐요, '현재 빈도 유지'면 None)"""
    years = fs["year"]
    data = fs[typ]
    bigs = sorted(data, key=lambda b: -sum(data[b]))
    past = [y <= cur for y in years]
    tag = ["실적" if p else "예측" for p in past]
    fig = go.Figure()
    for i, b in enumerate(bigs):
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        if mode == "라인":
            # 실적 = 실선 + 채운 원, 예측 = 점선 + 빈 원. 마지막 실적 점에서 예측이 이어져요 (범례는 대분류 하나)
            xa = [y for y, p in zip(years, past) if p]
            xf = [y for y, p in zip(years, past) if not p]
            if xa:
                fig.add_scatter(x=xa, y=[v for v, p in zip(data[b], past) if p], name=b, legendgroup=b, mode="lines+markers",
                                line=dict(color=color, width=2, dash="solid", shape="spline", smoothing=1.3), marker=dict(size=6),
                                hovertemplate=f"{b}<br>%{{x}} 실적: %{{y:,.0f}}건<extra></extra>")
            if xf:
                xs = ([xa[-1]] if xa else []) + xf
                ys = ([data[b][len(xa) - 1]] if xa else []) + [v for v, p in zip(data[b], past) if not p]
                fig.add_scatter(x=xs, y=ys, name=b, legendgroup=b, showlegend=not xa, mode="lines+markers",
                                line=dict(color=color, width=2, dash="dash", shape="spline", smoothing=1.3), marker=dict(symbol="circle-open", size=7),
                                hovertemplate=f"{b}<br>%{{x}} 예측: %{{y:,.0f}}건<extra></extra>")
        else:
            fig.add_bar(x=years, y=data[b], name=b, marker=dict(color=color, opacity=[1.0 if p else 0.35 for p in past]),
                        customdata=tag, hovertemplate=f"{b}<br>%{{x}} %{{customdata}}: %{{y:,.0f}}건<extra></extra>")
    if mode == "누적 막대":
        # 현재 연도까지 빈도 합계 = 실선 (실적), 그 뒤 = 점선 예측 추세선
        xa = [y for y, p in zip(years, past) if p]
        if xa:
            fig.add_scatter(x=xa, y=[sum(data[b][years.index(y)] for b in bigs) for y in xa], name="실적 합계",
                            mode="lines+markers", line=dict(color=ui.INK, dash="solid", width=2.5, shape="spline", smoothing=1.3), marker=dict(size=6),
                            hovertemplate="실적 합계<br>%{x}: %{y:,.0f}건<extra></extra>")
    if mode == "누적 막대" and trend:
        xs = [y for y in years if y >= cur]
        if len(xs) > 1:
            fig.add_scatter(x=xs, y=[trend[y] for y in xs], name="예측 추세선", mode="lines+markers",
                            line=dict(color=ui.INK, dash="dash", width=2.5, shape="spline", smoothing=1.3), marker=dict(size=5),
                            hovertemplate="선형회귀 예측 (합계)<br>%{x}: %{y:,.0f}건<extra></extra>")
    if mode == "누적 비율":
        fig.update_layout(barmode="stack", barnorm="percent", yaxis=dict(ticksuffix="%"))
    elif mode == "누적 막대":
        fig.update_layout(barmode="stack", yaxis=dict(tickformat=","))
    else:
        fig.update_layout(yaxis=dict(tickformat=","))
    fig.update_layout(xaxis=dict(dtick=1))
    _cur_line(fig, years)
    unit = "비중" if mode == "누적 비율" else "건/년"
    _layout(fig, f"{typ} 업무 빈도 ({unit}){sub}", align=True, left=50)
    fig.update_layout(legend=dict(font=dict(size=9)))
    st.plotly_chart(fig, theme=None, key=f"fq_{typ}_{key}")


def _workload(m, tr, sc):
    growth = st.session_state.params.freq_growth
    _section(3, "업무량", "설비 규모(인당 관리 대수)와 업무 발생 빈도(건/년)의 연도별 변화. 빈도 = 그해 파트별 업무·실적의 빈도((입력), 없으면 (회귀)) "
                         "× 연 환산(하루 = 교대 365 · 오피스 260일), 대분류별. 현재 연도까지 = 실적(선명), 이후 = 예측(흐리게·점선). "
                         + ("예측 추세선 = 현재 연도 −2년 ~ 현재 연도 합계의 1차 회귀." if growth else
                            "설정 '미래 빈도 = 현재 빈도 유지'라 예측 연도는 현재 연도 빈도를 그대로 이어요."))
    names, job = sc["names"], sc["job"]
    sub = f" · {sc['label']}" if (names is not None or job) else ""
    have = sorted({p.job for p in _all_parts(m) if inscope(names, p)})
    jobs = [job] if job else have
    years = tr["year"]
    full = freq_series(m, sorted(set(m.years) | set(years)), names, job, growth)    # 회귀선은 차트 범위 밖 실적 연도도 써요
    idx = [full["year"].index(y) for y in years]
    fs = {"year": years, **{t: {b: [v[i] for i in idx] for b, v in full[t].items()} for t in WORK_TYPES}}
    cols = st.columns(4, gap="small")
    with cols[0]:
        _chart_per_person(m, tr, names, "team", [j for j in jobs if j in have], sc["met"], sub)
    for col, typ in zip(cols[1:], WORK_TYPES):
        tot = {y: sum(v[i] for v in full[typ].values()) for i, y in enumerate(full["year"]) if y <= m.cur}
        trend = reg_trend(tot, m.cur, years) if growth else None
        with col:
            _chart_freq(fs, typ, sc["wl"], "team", sub, m.cur, trend)


# ---------------------------------------------------------------- 4. AX 효과
def ax_table(m, results, job=None) -> pd.DataFrame:
    """결과의 파트들에서 소분류별 POR·COMPARE 업무공수를 모아요 (대분류·중분류·파트 단위로 다시 묶어 써요). 그룹보드도 써요."""
    rows = []
    for r in results:
        if job and r.part.job != job or not r.profile:
            continue
        for code, (por, now) in r.profile.hours_by_code.items():
            lf = m.leaves[code]
            rows.append({"직군": r.part.job, "그룹": f"{r.part.site} · {r.part.group}", "대분류": lf.big, "중분류": lf.mid,
                         "소분류": lf.name, "파트": r.part.name, "POR (h)": por, "COMPARE (h)": now, "확보 (h)": por - now})
    return pd.DataFrame(rows, columns=["직군", "그룹", "대분류", "중분류", "소분류", "파트", "POR (h)", "COMPARE (h)", "확보 (h)"])


def _status(act, tgt, n_tgt=0, n_unrep=0):
    """달성 상태 (SPEC 결정 2026-11-22 ⑧). n_tgt = 목표 > 0인 파트 줄 수, n_unrep = 그중 그해 실적을 보고하지 않은 줄 수"""
    if act is None or pd.isna(act):
        return "예측"
    if tgt <= 1e-9:
        return "— 목표 없음"
    if n_tgt and n_unrep >= n_tgt:
        return "미보고"
    base = "🔵 달성" if act >= tgt - 1e-9 else ("⚪ 정상 진행" if act / tgt >= 0.8 else "🔴 미달/지연")
    return base + (f" · 미보고 {n_unrep}파트" if n_unrep else "")


def _ax(m, c, sc):
    names, job = sc["names"], sc["job"]
    actual_mode = c.cmp.state.ax_kind == "actual"
    y = c.cmp.state.year
    mode_txt = f"실제 효과 — COMPARE {y} 실적" if actual_mode else f"예측 — COMPARE {y} 목표"
    _section(4, "AX 효과", f"{mode_txt}. POR(AX 없음) 대비 줄어든 연간 업무시간을 직군 · 근무형태별로, 대분류 순위로 보여요. "
                         f"막대 = COMPARE 절감 공수, | = 목표 절감 공수. COMPARE를 실적으로 고르면 실제 효과, 목표로 고르면 예측이에요.")
    rs = [r for r in c.cmp.parts if inscope(names, r.part) and (job is None or r.part.job == job)]
    det = pd.DataFrame(ax_detail(m, c.cmp, names, job))
    if det.empty or not rs:
        st.caption("선택한 범위에 업무 데이터가 없어요."); return
    det["tgt_h"] = det["por_h"] * (1 - det["tgt"])
    det["act_h"] = [p * (1 - a) if a is not None and not pd.isna(a) else None for p, a in zip(det["por_h"], det["act"])]
    det["now_h"] = det["act_h"] if actual_mode else det["tgt_h"]            # COMPARE 시점 잔여 = KPI와 같은 기준
    _ax_charts(det, job, actual_mode)
    # 소분류 요약 표 — 잔여·절감은 KPI와 같은 기준: (입력) × (1 − 자동화율). 실측 시간은 참고 열 (SPEC 결정 2026-11-22 ⑦)
    det["rem_h"] = [p * (1 - a) if actual_mode and a is not None and not pd.isna(a) else p * (1 - t)
                    for p, t, a in zip(det["por_h"], det["tgt"], det["act"])]
    det["has_tgt"] = det["tgt"] > 1e-9
    det["unrep"] = (det["has_tgt"] & ~det["reported"].astype(bool)) if actual_mode else False
    s = det.groupby(["직군", "근무형태", "대분류", "소분류", "TYPE"]).agg(
        base=("por_h", "sum"), rem=("rem_h", "sum"), tgt_h=("tgt_h", "sum"),
        meas=("meas_h", lambda v: v.sum() if v.notna().any() else float("nan")),
        n_tgt=("has_tgt", "sum"), n_unrep=("unrep", "sum")).reset_index()
    s["절감"] = s["base"] - s["rem"]
    s["목표"] = 1 - s["tgt_h"] / s["base"].where(s["base"] > 0)
    s["실적"] = (s["절감"] / s["base"].where(s["base"] > 0)) if actual_mode else float("nan")   # 예측이면 빈칸
    s["달성 상태"] = [_status(a if actual_mode else None, t, int(n), int(u))
                    for a, t, n, u in zip(s["실적"] if actual_mode else [None] * len(s), s["목표"].fillna(0), s["n_tgt"], s["n_unrep"])]
    rem_col = "(실적) 잔여 공수(h)" if actual_mode else "(예측) 잔여 공수(h)"
    cols = {"직군": s["직군"], "근무형태": s["근무형태"], "대분류": s["대분류"], "소분류(업무명)": s["소분류"], "TYPE": s["TYPE"],
            "(입력) 기준 공수(h)": s["base"].round(0), rem_col: s["rem"].round(0), "절감 공수(h)": s["절감"].round(0)}
    if actual_mode:
        # 빈 숫자 칸은 Streamlit이 'None'으로 그려서 글자로 넣어요 (조사 안 한 업무는 빈칸)
        cols["(실측) 잔여 공수(h)"] = [f"{v:,.0f}" if pd.notna(v) else "" for v in s["meas"]]
    cols.update({"목표(%)": [f"{v:.0%}" if pd.notna(v) else "" for v in s["목표"]],
                 "실적(%)": [f"{v:.0%}" if pd.notna(v) else "" for v in s["실적"]] if actual_mode else [""] * len(s),
                 "달성 상태": s["달성 상태"]})
    out = pd.DataFrame(cols)
    out = out[out["(입력) 기준 공수(h)"] > 0].sort_values(["직군", "근무형태", "대분류", "절감 공수(h)"],
                                                     ascending=[True, True, True, False])
    basis = ("잔여 = (입력) × (1 − 보고 실적, 미보고면 직전 보고 실적) · (실측) 잔여 = 조사값 참고(반영은 기준정보 › 실적 보정)"
             if actual_mode else "잔여 = (입력) × (1 − 목표)")
    hcols = [c for c in out.columns if c.endswith("(h)") and c != "(실측) 잔여 공수(h)"]
    right = ["목표(%)", "실적(%)"] + (["(실측) 잔여 공수(h)"] if actual_mode else [])
    sty = (out.style.format({c: "{:,.0f}" for c in hcols})
           .set_properties(subset=right, **{"text-align": "right"}))
    with st.expander(f"소분류별 AX 요약 — {mode_txt} · {len(out)}개 업무", expanded=False):
        st.markdown(f"<span style='font-size:12px;color:{ui.MUTED}'>{basis}"
                    f" · 달성 상태: 🔵 실적 ≥ 목표 · ⚪ 목표의 80% 이상 · 🔴 그 밖 · — 목표 없음 · 미보고 = 목표가 있는데 그해 실적 칸이 빔</span>",
                    unsafe_allow_html=True)
        st.dataframe(sty, hide_index=True, row_height=ui.TABLE_ROW_H, height=420)
        if actual_mode:
            _report_rate(det)
    st.caption("AX 과제(프로젝트) 매핑·과제 관리는 이번 범위에서 빼고 백로그(KEEP)로 둬요.")


def _ax_state(save, tsave, n_tgt, n_unrep, actual) -> str:
    """대분류 막대 하나의 달성 상태 키 (소분류 표의 _status와 같은 규칙: 실적율 ÷ 목표율 = 절감 ÷ 목표 절감)"""
    if not actual:
        return "예측"
    if tsave <= 1e-9:
        return "목표 없음"
    if n_tgt and n_unrep >= n_tgt:
        return "미보고"
    return "달성" if save >= tsave - 1e-9 else ("정상" if save / tsave >= 0.8 else "미달")


def _ax_legend(actual):
    """네 차트 공통 범례 (차트마다 그리지 않고 차트 위에 한 번)"""
    keys = ["달성", "정상", "미달", "목표 없음", "미보고"] if actual else ["예측"]
    sw = lambda color, hatch: (f'<span style="display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:-1px;'
                               f'margin-right:5px;background:{color};'
                               + (f'background-image:repeating-linear-gradient(45deg,{ui.MUTED} 0 1px,transparent 1px 4px);' if hatch else "")
                               + '"></span>')
    items = [f'{sw(c, h)}{n}' for k in keys for n, c, h in [AX_STATUS[k]]]
    items.append(f'<span style="display:inline-block;width:3px;height:14px;background:{ui.INK};vertical-align:-2px;margin-right:5px"></span>'
                 '목표 절감 공수')
    st.markdown(f'<div style="font-size:12px;color:{ui.MUTED};margin:-4px 0 6px">막대 색 = 달성 상태 · '
                + " &nbsp;&nbsp; ".join(items) + "</div>", unsafe_allow_html=True)


def _ax_charts(det, job, actual):
    """대분류별 절감 공수: 직군 × 근무형태마다 차트 하나 (전체 = 1행 4열, 직군을 고르면 그 직군의 오피스·교대 2열).
    막대 = COMPARE 절감 공수(색 = 달성 상태), | = 목표 절감 공수(POR × 목표 자동화율). 범례는 차트 위에 한 번.
    네 차트의 높이와 X축 눈금을 맞춰요."""
    segs = [x for x in SEGS_AX if job is None or x.startswith(job)]
    has_tgt = det["tgt"] > 1e-9
    det = det.assign(seg=det["직군"] + " " + det["근무형태"], save_h=det["por_h"] - det["now_h"], tsave_h=det["por_h"] - det["tgt_h"],
                     n_tgt=has_tgt.astype(int),
                     n_unrep=(has_tgt & ~det["reported"].astype(bool)).astype(int) if actual else 0)
    rows = max([det[det["seg"] == sg]["대분류"].nunique() for sg in segs] + [1])
    height = max(280, 100 + 26 * rows)
    hi = max(det.groupby(["seg", "대분류"])[["save_h", "tsave_h"]].sum().max().max(), 1)     # 네 차트 X축을 같은 눈금으로
    _ax_legend(actual)
    cols = st.columns(len(segs), gap="small")
    for col, sg in zip(cols, segs):
        d = (det[det["seg"] == sg].groupby("대분류")[["por_h", "save_h", "tsave_h", "n_tgt", "n_unrep"]].sum()
             .sort_values("save_h"))
        with col:
            if d.empty:
                st.markdown(ui.kpi_na(f"{sg} 절감 공수", "선택한 범위에 이 직군·근무형태 업무가 없어요"), unsafe_allow_html=True)
                continue
            state = [_ax_state(a, b, n, u, actual) for a, b, n, u in zip(d["save_h"], d["tsave_h"], d["n_tgt"], d["n_unrep"])]
            fig = go.Figure()
            fig.add_bar(y=d.index, x=d["save_h"], orientation="h", name="절감",
                        marker=dict(color=[AX_STATUS[k][1] for k in state],
                                    pattern=dict(shape=[AX_STATUS[k][2] for k in state], fgcolor=ui.MUTED, size=5)),
                        customdata=list(zip(d["por_h"], [AX_STATUS[k][0] for k in state])),
                        hovertemplate="%{y}: %{x:,.0f}h (POR %{customdata[0]:,.0f}h)<br>%{customdata[1]}<extra></extra>")
            fig.add_scatter(y=d.index, x=d["tsave_h"], mode="markers", name="목표",
                            marker=dict(symbol="line-ns-open", size=18, line=dict(width=3, color=ui.INK)),
                            hovertemplate="%{y} 목표: %{x:,.0f}h<extra></extra>")
            fig.add_scatter(y=d.index, x=d[["save_h", "tsave_h"]].max(axis=1).clip(lower=0), mode="text", showlegend=False,
                            hoverinfo="skip", textposition="middle right", cliponaxis=False,
                            textfont=dict(size=9, color=ui.MUTED),
                            text=[f"  {h:,.0f}h ({h / p:.0%})" if p else "" for h, p in zip(d["save_h"], d["por_h"])])
            t, por = d["save_h"].sum(), d["por_h"].sum()
            _layout(fig, f"{sg} 절감 공수 +{t:,.0f}h/년 ({t / por:.0%})" if por else f"{sg} 절감 공수",
                    legend=False, height=height)
            fig.update_layout(xaxis=dict(range=[0, hi * 1.6], tickformat=","), margin=dict(l=20, r=10, t=40, b=30))
            st.plotly_chart(fig, theme=None, key=f"ax_{sg.replace(' ', '_')}")


def _report_rate(det):
    """목표가 있는 업무 중 그해 실적을 보고한 비율 (파트별). 목표 0% 업무는 세지 않아요."""
    d = det[det["has_tgt"]]
    if d.empty:
        return
    g = d.groupby("파트").agg(직군=("직군", "first"), 대상=("reported", "size"), 보고=("reported", "sum")).reset_index()
    g["보고율"] = g["보고"] / g["대상"]
    total = g["보고"].sum() / g["대상"].sum()
    st.markdown(f"**실적 보고율 {total:.0%}** <span style='font-size:12px;color:{ui.MUTED}'>— 목표가 있는 업무 "
                f"{int(g['대상'].sum())}개 중 {int(g['보고'].sum())}개 보고</span>", unsafe_allow_html=True)
    g = g.sort_values(["보고율", "파트"])
    g["보고율"] = [f"{v:.0%}" for v in g["보고율"]]
    st.dataframe(g.rename(columns={"대상": "목표 있는 업무", "보고": "보고한 업무"}), hide_index=True, row_height=ui.TABLE_ROW_H)
    st.caption("미보고 업무는 직전 연도 보고 실적을 이어받고, 직전 실적도 없으면 0%로 계산해요.")


# ---------------------------------------------------------------- 화면
def render():
    m = ui.model()
    st.title("대시보드")
    sc = settings_panel(m, full=True)
    with st.spinner("계산 중…"):
        c = ui.get_compare()
        tr = ui.get_trend()
    fb = m.target_fallbacks(sorted(set(tr["year"]) | {c.ref.state.year, c.cmp.state.year}))
    _section(1, "KPI 요약", ("AX 목표 열이 없는 연도는 앞 연도 목표를 이어서 써요: "
                            + ", ".join(f"{y} → {t} 목표 사용" for y, t in sorted(fb.items()))) if fb else "")
    _cards(m, c, sc)
    _people(m, c, tr, sc)
    _workload(m, tr, sc)
    _ax(m, c, sc)
