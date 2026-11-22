"""그룹보드 › 파트 부하 진단: 4사분면 버블 차트 + 선택 파트 3단계 드릴다운 (REQUIRE.md, SPEC 결정 이력 2026-11-21).

- Y축 부하율: 기본 = 필요 인원 ÷ 총원 (FTE 확보와 같은 기준, 100% = FTE 확보 0), 스위치로 업무시간 ÷ 가용시간
- X축 인당 챔버 수 (그해 챔버 ÷ 총원). 공정·설비는 대수가 크게 달라서 직군 스위치를 두고 평균선도 직군별로 그려요
- 버블은 모두 동그라미, 색 = 그룹 또는 파트('보기' 스위치 — 왼쪽 인력·FTE 차트도 같이 그룹별/파트별). 상태는 배경 띠: 부족(> 110%, 레드) / 적정 / 여유(< 90%, 블루)
- 직군·부하율 기준·버블 색 스위치는 그룹보드 공통 컨트롤 (직군은 그룹별 인력·FTE 차트와 함께)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from sim.scenario import LOAD_HIGH, LOAD_LOW, load_status, part_loads, type_hours
from views.dashboard import CHART_H, GROUP_COLORS, ax_table

BASES = {"필요 인원": "load_need", "업무시간": "load_hours"}
TYPE_COLOR = {"이벤트": ui.PRIMARY, "루틴": ui.SECONDARY, "이슈": ui.PRIMARY_MID, "비가동": ui.NEUTRAL}


def _ot(row, basis):
    return row["ot_need"] if basis == "필요 인원" else row["ot_hours"]


def _verdict(load, ot):
    s = load_status(load)
    if s == "부족":
        return f"부족: OT {ot:.1f}명분으로 버티는 중"
    return "적정: 정상 근무 범위" if s == "적정" else f"여유: 부하율 {load:.0%}"


def _sizes(heads):
    lo, hi = min(heads), max(heads)
    return [10 + 30 * ((h - lo) / (hi - lo) if hi > lo else 0.5) for h in heads]


CHART_H2 = CHART_H + 120          # 그룹보드 첫 줄 두 차트(그룹별 인력·FTE | 파트 부하 진단)의 같은 높이
# 파트가 많아서 그룹 색(대시보드와 같음) 뒤에 블루·그레이 톤을 이어 써요 (녹색·주황 없음)
PART_COLORS = GROUP_COLORS + ["#6B7FD7", "#1F3B77", "#7A8B99", "#B8C2F8", "#4A5568", "#2D3FCF", "#9AA5B1", "#525A87",
                              "#C3CAD4", "#0F1A8C", "#7380C9", "#3349F0", "#6E7787", "#ADB8F7", "#24304F"]   # 블루·그레이 톤만


def _chart(rows, basis, job, selected_groups, pick, color_by):
    key = BASES[basis]
    fig = go.Figure()
    shown = [r for r in rows if (job is None or r["job"] == job) and r["ch_per"] is not None]
    sizes = dict(zip([r["part"] for r in shown], _sizes([r["head"] for r in shown]) if shown else []))
    # 상태 구역: 110% 위 = 부족(레드 띠), 90% 아래 = 여유(블루 띠). 색은 그룹·파트 구분에 써요
    ys = [r[key] * 100 for r in shown] + [100]
    y0, y1 = min(ys) - 8, max(ys) + 8
    fig.add_hrect(y0=LOAD_HIGH * 100, y1=max(y1, LOAD_HIGH * 100 + 5), fillcolor=ui.ERROR_SOFT, opacity=0.6, line_width=0, layer="below")
    fig.add_hrect(y0=min(y0, LOAD_LOW * 100 - 5), y1=LOAD_LOW * 100, fillcolor=ui.POSITIVE_SOFT, opacity=0.7, line_width=0, layer="below")
    groups = sorted({r["group"] for r in rows})
    parts = [r["part"] for r in sorted(rows, key=lambda r: (r["group"], r["part"]))]   # 왼쪽 파트별 막대와 같은 순서 (그룹 → 파트)
    keyf = (lambda r: r["group"]) if color_by == "그룹" else (lambda r: r["part"])
    names = groups if color_by == "그룹" else parts
    palette = GROUP_COLORS if color_by == "그룹" else PART_COLORS
    for idx, name in enumerate(names):
        pts = [r for r in shown if keyf(r) == name]
        if not pts:
            continue
        dim = [bool(selected_groups) and r["group"] not in selected_groups for r in pts]
        fig.add_scatter(
            x=[r["ch_per"] for r in pts], y=[r[key] * 100 for r in pts], mode="markers", name=name,
            customdata=[[r["part"]] for r in pts],
            marker=dict(size=[sizes[r["part"]] for r in pts], color=palette[idx % len(palette)], symbol="circle",
                        opacity=[0.25 if d else 0.85 for d in dim],
                        line=dict(color=[ui.INK if r["part"] == pick else "#FFFFFF" for r in pts],
                                  width=[3 if r["part"] == pick else 1 for r in pts])),
            text=[(f"<b>{r['part']}</b> · {r['group']} · {r['job']}<br>총원 {r['head']:.0f}명<br>"
                   f"부하율 {r[key]:.1%} — {_verdict(r[key], _ot(r, basis))}<br>인당 챔버 {r['ch_per']:.1f}<br>"
                   f"FTE 교대 {r['shift']:+.1f} / 오피스 {r['office']:+.1f}") for r in pts],
            hovertemplate="%{text}<extra></extra>")
    fig.add_hline(y=100, line=dict(color="#5B6475", dash="dash", width=1.5))
    fig.add_annotation(x=1, xref="paper", y=100, text="100% 정상 근로 (OT 0)", showarrow=False, xanchor="right",
                       yanchor="bottom", font=dict(size=10, color=ui.MUTED))
    for j in ([job] if job else ("공정", "설비")):
        xs = [r["ch_per"] for r in shown if r["job"] == j]
        if xs:
            avg = sum(xs) / len(xs)
            fig.add_vline(x=avg, line=dict(color=ui.NEUTRAL, dash="dot", width=1))
            fig.add_annotation(x=avg, y=1, yref="paper", text=f"{j} 평균 {avg:.1f}", showarrow=False, xanchor="left",
                               yanchor="top", font=dict(size=10, color=ui.MUTED))
    fig.update_layout(
        # 범례는 오른쪽 세로 목록 (그룹 7개·파트 20여 개가 아래 범례로는 잘려서)
        height=CHART_H2, margin=dict(l=50, r=150 if color_by == "파트" else 110, t=40, b=60, autoexpand=False),
        title=dict(text=f"파트 부하 진단{' · ' + job if job else ''} — {basis} 기준 부하율 × 인당 챔버 (버블 = 총원)",
                   font=dict(size=13)),
        xaxis=dict(title=dict(text="인당 관리 챔버 수 (챔버 ÷ 총원)", standoff=4)),
        yaxis=dict(title=dict(text="부하율 (%)", standoff=4), ticksuffix="%", range=[y0, y1]),
        legend=dict(orientation="v", yanchor="top", y=1, x=1.02, xanchor="left", font=dict(size=10 if color_by == "그룹" else 9),
                    title=dict(text=color_by), tracegroupgap=0, itemsizing="constant"))
    missing = sum(1 for r in rows if (job is None or r["job"] == job) and r["ch_per"] is None)
    return fig, missing


def _layer1(m, rc, row, basis):
    key = BASES[basis]
    load = row[key]
    st.markdown("**① 요약 진단**")
    k = st.columns(4)
    k[0].metric(f"총 부하율 ({basis} 기준)", f"{load:.1%}", f"{(load - 1) * 100:+.1f}%p (100% 대비)",
                delta_color="inverse")
    k[1].metric("교대 FTE 여유 / 부족", f"{rc.secured_shift:+.1f} FTE", "여유" if rc.secured_shift >= 0 else "부족",
                delta_color="off", delta_arrow="off")
    k[2].metric("오피스 FTE 여유 / 부족", f"{rc.secured_office:+.1f} FTE", "여유" if rc.secured_office >= 0 else "부족",
                delta_color="off", delta_arrow="off")
    k[3].metric("OT로 버티는 인원 (추정)", f"{max(0.0, rc.need - rc.head):.1f} FTE", "필요 인원 − 총원",
                delta_color="off", delta_arrow="off")
    th = type_hours(m, rc)
    tot = sum(th.values()) or 1
    fig = go.Figure()
    for t, v in th.items():
        fig.add_bar(y=["업무 TYPE"], x=[v / tot * 100], name=f"{t} {v / tot:.0%}", orientation="h",
                    marker_color=TYPE_COLOR[t], text=[f"{t} {v / tot:.0%}"], textposition="inside",
                    insidetextanchor="middle", hovertemplate=f"{t}: {v:,.0f}h/년 ({v / tot:.1%})<extra></extra>")
    fig.update_layout(barmode="stack", height=130, margin=dict(l=20, r=20, t=30, b=10), showlegend=False,
                      title=dict(text=f"업무 TYPE별 시간 비중 — 연 {tot:,.0f}h (비가동 = 1인 기준 × 총원)", font=dict(size=12)),
                      xaxis=dict(range=[0, 100], ticksuffix="%", showgrid=False), yaxis=dict(showticklabels=False))
    st.plotly_chart(fig, theme=None, key="diag_types")


def _layer2(rows, row):
    st.markdown("**② 설비 부하 근거 — 인당 관리 챔버 수**")
    same = [r["ch_per"] for r in rows if r["job"] == row["job"] and r["ch_per"] is not None]
    avg = sum(same) / len(same) if same else None
    k = st.columns(4)
    k[0].metric("인당 챔버 (지금, 챔버 ÷ 총원)", f"{row['ch_per']:.1f}" if row["ch_per"] else "—",
                f"{row['chambers']:,.0f}챔버 · {row['head']:.0f}명" if row["chambers"] else "챔버 데이터 없음",
                delta_color="off", delta_arrow="off")
    k[1].metric("목표 (목표 챔버 ÷ 필요 인원)", f"{row['ch_tgt_per']:.1f}" if row["ch_tgt_per"] else "—",
                "설비 시트 목표", delta_color="off", delta_arrow="off")
    k[2].metric("실적 (실적 챔버 ÷ 총원)", f"{row['ch_act_per']:.1f}" if row["ch_act_per"] else "—",
                "실적 연도만" if not row["ch_act_per"] else "설비 시트 실적", delta_color="off", delta_arrow="off")
    if avg and row["ch_per"]:
        k[3].metric(f"{row['job']} 평균 대비", f"{row['ch_per'] / avg:.0%}", f"{row['job']} 평균 {avg:.1f}",
                    delta_color="off", delta_arrow="off")
    else:
        k[3].metric(f"{row['job']} 평균 대비", "—", "비교할 값 없음", delta_color="off", delta_arrow="off")


def _layer3(m, rc):
    st.markdown("**③ 업무별 근거 — 대분류별 소요시간 (병목 Top 3 강조)**")
    df = ax_table(m, [rc])
    if df.empty:
        st.caption("업무 데이터가 없어요."); return
    g = df.groupby("대분류")[["POR (h)", "COMPARE (h)"]].sum().reset_index()
    g["차이 (h)"] = g["POR (h)"] - g["COMPARE (h)"]
    g["확보율"] = (g["차이 (h)"] / g["POR (h)"]).fillna(0)
    g = g.sort_values("COMPARE (h)", ascending=False).reset_index(drop=True)
    g.insert(0, "순위", [f"Top {i + 1}" if i < 3 else str(i + 1) for i in range(len(g))])
    sty = g.style.apply(lambda r: [f"background-color: {ui.PRIMARY_SOFT}; font-weight: 600" if r.name < 3 else "" for _ in r],
                        axis=1).format({"POR (h)": "{:,.0f}", "COMPARE (h)": "{:,.0f}", "차이 (h)": "{:+,.0f}"})
    st.dataframe(sty, hide_index=True, row_height=ui.TABLE_ROW_H, column_config={
        "확보율": st.column_config.ProgressColumn("확보율 (AX)", min_value=0, max_value=1, format="percent"),
        "COMPARE (h)": st.column_config.Column(help="COMPARE 시점의 연간 업무시간 (AX 적용 후). 이 값이 큰 순서")})
    st.caption("차이 = POR − COMPARE (AX로 줄어든 시간). 비가동은 빼고 업무만 보여 줘요.")


def chart(m, c, job, basis, color_by, chart_box) -> dict | None:
    """그룹보드 첫 줄 오른쪽 칸(chart_box)에 버블 차트를 그려요. 아래 '파트 분석'(detail)에 넘길 값을 돌려줘요.
    직군·부하율 기준·보기(그룹/파트) 스위치는 그룹보드 공통 컨트롤에서 받아요."""
    ss = st.session_state
    rows = part_loads(m, c.cmp)
    if not rows:
        chart_box.info("진단할 파트가 없어요."); return None
    key = BASES[basis]
    names = [r["part"] for r in sorted(rows, key=lambda r: -r[key]) if job is None or r["job"] == job]
    if not names:
        chart_box.caption(f"{job} 파트가 없어요."); return None
    # 버블을 누르면 그 파트로 (새로 누른 경우만 — 셀렉트박스로 고른 값을 덮어쓰지 않게)
    ev = ss.get("diag_chart")
    pts = (ev or {}).get("selection", {}).get("points", []) if isinstance(ev, dict) or hasattr(ev, "get") else []
    clicked = pts[0]["customdata"][0] if pts and pts[0].get("customdata") else None
    if clicked and clicked != ss.get("_diag_seen") and clicked in names:
        ss.diag_part = clicked
    ss._diag_seen = clicked
    if ss.get("diag_part") not in names:
        ss.diag_part = names[0]                      # 기본: 부하율이 가장 높은 파트
    groups = set(ss.get("grp_sel") or [])
    fig, missing = _chart(rows, basis, job, groups, ss.diag_part, color_by)
    with chart_box:
        st.plotly_chart(fig, theme=None, key="diag_chart", on_select="rerun", selection_mode="points")
    notes = []
    if missing:
        notes.append(f"챔버 수가 없는 파트 {missing}개는 버블 차트에서 뺐어요 (아래 선택 목록에는 있어요)")
    if groups:
        notes.append("'자세히 볼 그룹'에서 고른 그룹의 파트는 진하게, 나머지는 옅게 보여요")
    if notes:
        st.caption(" · ".join(notes))
    return {"rows": rows, "names": names, "basis": basis}


def detail(m, c, ctx):
    """선택 파트 분석: [진단 파트 선택] + 3단계 근거 (그룹보드 맨 아래)"""
    if not ctx:
        return
    rows, names, basis = ctx["rows"], ctx["names"], ctx["basis"]
    key = BASES[basis]
    st.subheader("파트 분석")
    st.caption("위 버블을 누르거나 여기서 파트를 고르면 '왜 부족 / 여유인가'를 3단계로 보여 줘요.")
    pick = st.selectbox("진단 파트 선택", names, key="diag_part",
                        format_func=lambda n: f"{n} — {next(r for r in rows if r['part'] == n)[key]:.0%} "
                                              f"{load_status(next(r for r in rows if r['part'] == n)[key])}")
    row = next(r for r in rows if r["part"] == pick)
    rc = next(r for r in c.cmp.parts if r.part.name == pick)
    with st.container(border=True):
        st.markdown(f"#### 🔎 {pick} <span style='font-size:13px;color:{ui.MUTED};font-weight:400'>· {row['group']} · "
                    f"{row['job']} · 총원 {row['head']:.0f}명 · {_verdict(row[key], _ot(row, basis))}</span>",
                    unsafe_allow_html=True)
        _layer1(m, rc, row, basis)
        _layer2(rows, row)
        _layer3(m, rc)
