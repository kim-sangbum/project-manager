"""🏢 그룹보드 (위에서 아래 순서)
1. 공통 스위치(보기 → 직군 → 부하율 기준) + 첫 줄 2열: 그룹(파트)별 인력·FTE 현황 | 파트 부하 진단 버블 (views/diagnosis.py)
2. 그룹별 상세: 그룹 선택 → 그룹마다 지표·파트 표·업무별 AX 효과·파트별 펼침
3. 파트 분석: 진단 파트 선택(또는 버블 클릭) → 3단계 근거
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from sim.data import SLOTS
from views import diagnosis
from views.dashboard import CHART_H, ax_table, settings_panel

PART_COLORS = list(ui.TONES)          # 블루·네이비·그레이 톤온톤


def _gkey(p) -> str:
    return f"{p.site} · {p.group}"


def _group_stats(m, res, job=None):
    """그룹별 총원·필요·FTE 확보·재배치 (재배치 대상은 폐지 파트가 속했던 그룹으로). job = 공정/설비만 셀 때"""
    out = {}
    for r in res.parts:
        if job and r.part.job != job:
            continue
        g = out.setdefault(_gkey(r.part), {"head": 0.0, "need": 0.0, "secured": 0.0, "reloc": 0.0, "shift": 0.0, "office": 0.0,
                                           "h_por": 0.0, "h_now": 0.0, "n": 0})
        g["head"] += r.head; g["need"] += r.need; g["secured"] += r.secured; g["n"] += 1
        g["shift"] += r.secured_shift; g["office"] += r.secured_office
        if r.profile:
            g["h_por"] += sum(v[0] for v in r.profile.hours_loc.values())
            g["h_now"] += sum(v[1] for v in r.profile.hours_loc.values())
    for name, n, _ in res.relocation:
        if name in m.parts and (not job or m.parts[name].job == job):
            out.setdefault(_gkey(m.parts[name]), {"head": 0.0, "need": 0.0, "secured": 0.0, "reloc": 0.0, "shift": 0.0,
                                                  "office": 0.0, "h_por": 0.0, "h_now": 0.0, "n": 0})["reloc"] += n
    return dict(sorted(out.items()))


def _part_stats(m, res, job=None):
    """파트별 총원·필요·FTE 확보·재배치 ('보기 = 파트'일 때 왼쪽 차트). 폐지 파트는 재배치 대상 막대만 있어요. 그룹 → 파트 순"""
    out = {}
    for r in res.parts:
        if job and r.part.job != job:
            continue
        out[r.part.name] = {"head": r.head, "need": r.need, "secured": r.secured, "reloc": 0.0, "group": _gkey(r.part)}
    for name, n, _ in res.relocation:
        if name in m.parts and (not job or m.parts[name].job == job):
            out.setdefault(name, {"head": 0.0, "need": 0.0, "secured": 0.0, "reloc": 0.0, "group": _gkey(m.parts[name])})["reloc"] += n
    return dict(sorted(out.items(), key=lambda kv: (kv[1]["group"], kv[0])))


def _overview(stats, label, job=None, view="그룹"):
    gs = list(stats)
    need = [stats[g]["need"] for g in gs]
    sec = [stats[g]["secured"] for g in gs]
    rel = [stats[g]["reloc"] for g in gs]
    head = [stats[g]["head"] + stats[g]["reloc"] for g in gs]
    fig = go.Figure()
    fig.add_bar(x=gs, y=need, name="필요 인원", marker_color=ui.NEUTRAL)
    fig.add_bar(x=gs, y=sec, name="FTE 확보", marker_color=ui.PRIMARY, text=[f"{v:+.1f}" for v in sec],
                textposition="inside", textfont=dict(color="#FFFFFF", size=10))
    fig.add_bar(x=gs, y=rel, name="재배치 대상", marker_color=ui.NEGATIVE)
    fig.add_scatter(x=gs, y=head, mode="text", text=[f"{h:,.0f}명" for h in head], textposition="top center",
                    textfont=dict(size=11, color=ui.MUTED), showlegend=False, hoverinfo="skip")
    by_part = view == "파트"
    if by_part:      # 파트 이름이 길고 많아서 기울여 써요 (위 숫자는 총원만 짧게)
        fig.update_traces(selector=dict(type="scatter"), text=[f"{h:,.0f}" for h in head], textfont=dict(size=9))
        fig.update_traces(selector=dict(type="bar", name="FTE 확보"), textfont=dict(size=8))
    fig.update_layout(barmode="relative", height=diagnosis.CHART_H2,
                      margin=dict(l=50, r=20, t=40, b=150 if by_part else 90, autoexpand=False),
                      title=dict(text=f"{view}별 인력 · FTE 현황{' · ' + job if job else ''} — COMPARE {label} (위 숫자 = 총원)",
                                 font=dict(size=13)),
                      xaxis=dict(tickangle=-45 if by_part else 0, tickfont=dict(size=9 if by_part else 10)),
                      legend=dict(orientation="h", yanchor="top", y=-0.42 if by_part else -0.12, x=0, font=dict(size=10)),
                      yaxis=dict(range=[min(0, min(sec + [0]) * 1.2), max(head + [1]) * 1.15]))
    st.plotly_chart(fig, theme=None, key="grp_overview")


def _part_rows(m, rs, year):
    rows = []
    for r in rs:
        p = r.part
        ch = m.chambers.get((p.name, year), (None,) * 4)
        rows.append({"파트": p.name, "직군": p.job, "총원": round(r.head, 1), "필요 인원": round(r.need, 1),
                     "FTE 확보": round(r.secured, 1), "교대 FTE 확보": round(r.secured_shift, 1),
                     "오피스 FTE 확보": round(r.secured_office, 1),
                     "인당 챔버 (목표)": round(ch[0] / r.need, 1) if ch[0] and r.need else None,
                     "인당 챔버 (실적)": round(ch[1] / r.head, 1) if ch[1] and r.head else None,
                     "근무대 자리 (현재 → 필요)": "오피스만" if p.office_only else
                     f"{'/'.join(str(int(p.slots[s])) for s in SLOTS)} → {'/'.join(str(r.shift.seats[s]) for s in SLOTS)}"
                     f"{' *' + r.bundle if r.bundle else ''}"})
    return pd.DataFrame(rows)


def _ax_by_part(df, key):
    """대분류별 확보 시간을 파트별 조각으로 쌓은 가로 막대 — 공정·설비는 대분류가 달라서 좌우로 나눠요."""
    if df.empty:
        st.info("업무 데이터가 없어요."); return
    jobs = [j for j in ("공정", "설비") if j in set(df["직군"])]
    n_rows = max(df[df["직군"] == j]["대분류"].nunique() for j in jobs)    # 나란히 놓인 차트 높이를 맞춰요
    parts = sorted(df["파트"].unique())                                      # 파트 색은 그룹 안에서 고정
    cols = st.columns(len(jobs), gap="small")
    for col, job in zip(cols, jobs):
        d = df[df["직군"] == job]
        order = d.groupby("대분류")["확보 (h)"].sum().sort_values().index.tolist()
        fig = go.Figure()
        for part in [p for p in parts if p in set(d["파트"])]:
            s = d[d["파트"] == part].groupby("대분류")["확보 (h)"].sum().reindex(order, fill_value=0)
            fig.add_bar(y=order, x=s.values, name=part, orientation="h",
                        marker_color=PART_COLORS[parts.index(part) % len(PART_COLORS)],
                        hovertemplate=f"{part}<br>%{{y}}: %{{x:,.0f}}h<extra></extra>")
        tot = d.groupby("대분류")[["POR (h)", "확보 (h)"]].sum().reindex(order)
        fig.add_scatter(y=order, x=tot["확보 (h)"], mode="text", showlegend=False, hoverinfo="skip", textposition="middle right",
                        text=[f"  {h:,.0f}h ({h / p:.0%})" if p else "" for h, p in zip(tot["확보 (h)"], tot["POR (h)"])],
                        textfont=dict(size=10, color=ui.MUTED), cliponaxis=False)
        t, por = tot["확보 (h)"].sum(), tot["POR (h)"].sum()
        fig.update_layout(barmode="stack", height=max(240, 100 + 30 * n_rows), margin=dict(l=20, r=20, t=40, b=20),
                          title=dict(text=f"{job} 대분류별 AX 확보 시간 — {t:,.0f}h/년 ({t / por:.0%})" if por else f"{job} 대분류",
                                     font=dict(size=13)),
                          legend=dict(orientation="h", yanchor="top", y=-0.1, x=0, font=dict(size=10), traceorder="normal"),
                          xaxis=dict(range=[0, max(tot["확보 (h)"].max(), 1) * 1.35], tickformat=","))
        with col:
            st.plotly_chart(fig, theme=None, key=f"{key}_{job}")


def _part_detail(m, rc, rr):
    """예전 '파트 정보' 화면 내용: 근무대별 자리와 지배 요인, 대분류별 AX 효과"""
    p = rc.part
    st.caption(f"{p.site} · {p.group} · {p.job} · 파트 ID {p.pid}"
               f"{' · 묶음 ' + rc.bundle if rc.bundle else ''}")
    if p.office_only:
        st.caption("오피스만 있는 파트예요.")
    else:
        rows = [{"근무대": s, "현재 자리": int(p.slots[s]), "업무량 자리 (REF)": round(rr.shift.work[s], 2) if rr else None,
                 "업무량 자리 (COMPARE)": round(rc.shift.work[s], 2), "하한": rc.shift.floor[s],
                 "필요 자리": rc.shift.seats[s], "지배 요인": rc.shift.why[s]} for s in SLOTS]
        st.dataframe(pd.DataFrame(rows), hide_index=True, row_height=ui.TABLE_ROW_H)
    df = ax_table(m, [rc])
    if not df.empty:
        g = df.groupby(["대분류", "중분류"])[["POR (h)", "COMPARE (h)", "확보 (h)"]].sum().reset_index()
        g["자동화율"] = (g["확보 (h)"] / g["POR (h)"]).fillna(0)
        st.dataframe(g.sort_values("확보 (h)", ascending=False), hide_index=True, row_height=ui.TABLE_ROW_H,
                     column_config={k: st.column_config.NumberColumn(format="%.0f") for k in ("POR (h)", "COMPARE (h)", "확보 (h)")}
                     | {"자동화율": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})


def _group_section(m, c, g, stats, ref_stats):
    ss = st.session_state
    s, r0 = stats[g], ref_stats.get(g)
    rs = [r for r in c.cmp.parts if _gkey(r.part) == g]
    with st.container(border=True):
        st.markdown(f"### {g}")
        k = st.columns(6)
        k[0].metric("총원", f"{s['head'] + s['reloc']:,.0f}명", f"재배치 {s['reloc']:.0f}명" if s["reloc"] else "재배치 없음",
                    delta_color="off", delta_arrow="off")
        # 델타 글자는 숫자로 시작해야 화살표 방향이 맞아요
        k[1].metric("필요 인원", f"{s['need']:,.1f}", f"{s['need'] - r0['need']:+.1f} (REF 대비)" if r0 else "REF에 없음",
                    delta_color="inverse" if r0 else "off", delta_arrow="auto" if r0 else "off")
        k[2].metric("FTE 확보", f"{s['secured']:+,.1f}", f"{s['secured'] - r0['secured']:+.1f} (REF 대비)" if r0 else "REF에 없음",
                    delta_color="normal" if r0 else "off", delta_arrow="auto" if r0 else "off")
        k[3].metric("교대 FTE 확보", f"{s['shift']:+,.1f}", f"파트 {s['n']}개", delta_color="off", delta_arrow="off")
        k[4].metric("오피스 FTE 확보", f"{s['office']:+,.1f}", f"파트 {s['n']}개", delta_color="off", delta_arrow="off")
        saved = s["h_por"] - s["h_now"]
        k[5].metric("AX 확보 업무공수 (연)", f"{saved:,.0f}h", f"POR의 {saved / s['h_por']:.0%}" if s["h_por"] else "—",
                    delta_color="off", delta_arrow="off")
        if not rs:
            st.caption("COMPARE 연도에 운영 중인 파트가 없어요."); return
        tbl = _part_rows(m, rs, c.cmp.state.year)
        if tbl["인당 챔버 (실적)"].isna().all():
            tbl = tbl.drop(columns=["인당 챔버 (실적)"])     # COMPARE가 목표 연도면 실적이 없어요
        lo, hi = min(0.0, tbl["FTE 확보"].min()), max(1.0, tbl["FTE 확보"].max())
        st.dataframe(tbl, hide_index=True, row_height=ui.TABLE_ROW_H, column_config={
            "FTE 확보": st.column_config.ProgressColumn(min_value=lo, max_value=hi, format="%.1f",
                                                       help="그룹 안 파트끼리 비교하는 막대"),
            "인당 챔버 (실적)": st.column_config.NumberColumn(help="그해 실적 챔버 수 ÷ 실제 총원 (실적 연도만)")})
        _ax_by_part(ax_table(m, rs), key=f"grp_ax_{g}")
        for r in rs:
            rr = next((x for x in c.ref.parts if x.part.name == r.part.name), None)
            with st.expander(f"🔎 {r.part.name} — 근무대 자리 · 업무별 AX 효과", expanded=r.part.name == ss.get("detail_part")):
                _part_detail(m, r, rr)


def _select_all(groups):
    st.session_state.grp_sel = list(groups)


def _clear():
    st.session_state.grp_sel = []


def render():
    ss = st.session_state
    m = ui.model()
    st.title("그룹보드")
    settings_panel(m)
    with st.spinner("계산 중…"):
        c = ui.get_compare()
    stats, ref_stats = _group_stats(m, c.cmp), _group_stats(m, c.ref)
    # 공통 컨트롤: 직군 스위치 하나가 두 차트(그룹별 인력·FTE, 파트 부하 진단)에 함께 적용돼요
    st.subheader("그룹 현황 · 파트 부하 진단")
    st.caption(f"COMPARE {c.cmp.state.label()} 기준. 부하율 > 110% 부족(OT로 버팀, 레드 띠) · 90~110% 적정 · < 90% 여유(블루 띠). "
               "버블을 누르면 맨 아래 '파트 분석'이 그 파트로 바뀌어요.")
    row = st.container(horizontal=True, gap="small", vertical_alignment="bottom")
    with row:   # 순서: 보기 → 직군 → 부하율 기준
        view = st.segmented_control("보기", ["그룹", "파트"], default="그룹", key="diag_color", width="content",
                                    help="그룹 = 왼쪽 막대는 그룹별, 버블 색·범례는 그룹 / 파트 = 왼쪽 막대는 파트별, 버블 색·범례는 파트") or "그룹"
        job = st.segmented_control("직군", ["전체", "공정", "설비"], default="전체", key="grp_job", width="content") or "전체"
        basis = st.segmented_control("부하율 기준", list(diagnosis.BASES), default="필요 인원", key="diag_basis", width="content",
                                     help="필요 인원 ÷ 총원 = 최소 인원·이슈 대비·묶음 반영(FTE 확보와 같은 기준). "
                                          "업무시간 ÷ 가용시간 = 업무량만 (가용 = 총원 × (2,080h − 1인 비가동))") or "필요 인원"
    job = None if job == "전체" else job
    left, right = st.columns(2, gap="small")
    with left:
        stats_v = _group_stats(m, c.cmp, job) if view == "그룹" else _part_stats(m, c.cmp, job)
        _overview(stats_v, c.cmp.state.label(), job, view)
    diag = diagnosis.chart(m, c, job, basis, view, right)
    st.subheader("그룹별 상세")
    groups = list(stats)
    ss.setdefault("grp_sel", [])
    ss.grp_sel = [g for g in ss.grp_sel if g in groups]
    a, b1, b2 = st.columns([6, 1.1, 0.9], vertical_alignment="bottom")
    sel = a.multiselect("자세히 볼 그룹 (여러 개 선택)", groups, key="grp_sel",
                        placeholder="그룹을 고르면 그룹마다 파트별 현황과 AX 효과가 한 섹션씩 생겨요")
    b1.button("전체 그룹 선택", on_click=_select_all, args=(groups,), width="stretch")
    b2.button("선택 해제", on_click=_clear, width="stretch", disabled=not sel)
    for g in sel:
        _group_section(m, c, g, stats, ref_stats)
    # 맨 아래: 진단 파트를 골라 그 파트를 분석해요
    diagnosis.detail(m, c, diag)
