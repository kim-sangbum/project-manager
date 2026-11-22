"""⚙️ 기준정보: 엑셀 가져오기·내보내기와 시트 5개 (업무구분 · 파트별 업무·실적 · 조직변경 · 인원 · 설비).

표는 기본으로 잠겨 있어요(조회). [✏️ 데이터 수정] → 고치기 → [💾 변경사항 저장]을 누르면 검사(sim.data.check_table)를
통과해야만 저장돼요. 오류가 있으면 행 번호와 사유를 빨간 글씨로 보여 주고 저장하지 않아요. 수정은 한 번에 표 하나만 해요.
자동 열(업무구분 JOIN, (실측) 자동화율, 입력 안내, 상태)은 회색으로 잠겨 있고 저장하지 않아요.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from sim.data import (CHOICES, DICT, EDIT_SHEETS, EQUIP, HEAD, HINT, IN_AX, IN_FREQ, IN_MIN, LATE, M_AX, M_FREQ, M_MIN, ORG,
                      REG_FREQ, SHEETS, SHIFT_LOCS, STATUS, TEMPLATE_PATH, TGT, UNIT, WORK, add_target_year, add_year, derived_cols,
                      locked_cols,
                      display_table, drop_target_year, drop_year, late_plans, load_excel, load_sample, rate_cols,
                      snapshot_years, to_excel_bytes, year_cols)
from sim.engine import _unit_factor
RECENT_TARGETS = 5          # 업무구분 표에 기본으로 보이는 최근 목표 연도 수

HELP = {
    DICT: "팀 공통 업무(대 > 중 > 소분류)와 속성, 오른쪽에 연도별 공통 AX 목표(0.3 = 30%). 공통 목표는 같은 직군의 모든 파트에 적용돼요. "
          "다른 시트에서 쓰는 코드는 지울 수 없어요.",
    WORK: "파트별 업무를 한 줄에: (입력) 빈도·건당 시간(AX 전 기준) → 파트 목표 → (실측) 조사값 → (입력) 보고 실적. "
          "대분류~TYPE은 코드로 자동으로 붙고, (실측) 자동화율 = 1 − 실측 건당 ÷ 입력 건당이에요. "
          "연도별 스냅샷이라 그 연도 행이 없으면 직전 연도 행을 쓰고, 파트 목표는 그 연도에만 적용하고, 보고 실적이 빈 칸이면 직전 연도 보고 실적을 이어받아요. "
          "미래 연도의 (회귀) 빈도는 현재 연도 −2년 ~ 현재 연도 (입력) 빈도의 1차 회귀예요(대시보드 설정 [적용] 때 계산, 고칠 수 없어요). "
          "미래 빈도를 직접 예측해 (입력) 빈도에 넣으면 그 값을 우선 써요.",
    ORG: "파트 신설·폐지·병합·그룹 이동·파트 묶음을 1행 1파트로 적어요 (구분 = 계획 / 실적). 계산은 인원 스냅샷이 기준이라 "
         "이 시트는 스냅샷과 맞는지 검사해요. 병합된 파트 인원은 병합 행 연도부터 존속 파트가 흡수해 재배치 대상이 아니에요. "
         "파트 묶음은 결과 이름이 같은 행끼리 한 묶음(교대·오피스 함께)이고, '실적'은 늘, '계획'은 대시보드 설정 '계획 묶음 반영 = 계획대로'에서 반영해요.",
    HEAD: "연도별 확정 스냅샷이에요(연도 + 파트가 키). 그 연도 총원과 (변동) 신입·전입·전출·퇴직, 근무대별 배치·최소 인원"
          "(2인 근무가 필요하면 최소 2), '교대' 업무의 근무대 배분(합 100%), 비고. 그해 스냅샷에 새로 생긴 파트는 신설, "
          "빠진 파트는 폐지(인원은 재배치 대상)로 봐요. 스냅샷이 없는 연도는 직전 연도 스냅샷을 써요.",
    EQUIP: "파트별 연도별 Process 챔버·설비 수 목표·실적 (대시보드 인당 관리 지표, 공정·설비 따로).",
}

# 파일 올리기 칸을 버튼 높이로 줄여 한 줄 액션 바에 맞춰요 (이 화면에만 적용)
UPLOADER_CSS = """<style>
[data-testid="stFileUploaderDropzone"] {padding: 0 10px 0 0; min-height: 40px; border-radius: 10px; align-items: center;}
[data-testid="stFileUploaderDropzone"] button {border: none; border-right: 1px solid #CACED6; border-radius: 10px 0 0 10px; min-height: 38px;}
[data-testid="stFileUploaderDropzoneInstructions"] > div > span {display: none;}
[data-testid="stFileUploaderDropzoneInstructions"] small {display: none;}
[data-testid="stFileUploaderDropzoneInstructions"]::after {content: "엑셀 가져오기 (.xlsx 끌어 놓기)"; font-size: 14px;}
</style>"""
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
LATE_BG = "#FCE8E7"       # ui.ERROR_SOFT (미반영 계획 = 부정 → 레드 배경)


# ---------------------------------------------------------------- 상단
def _action_bar(ds):
    ss = st.session_state
    st.markdown(UPLOADER_CSS, unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1], vertical_alignment="center")
    up = c1.file_uploader("엑셀에서 가져오기 (시뮬레이터 입력 파일)", type=["xlsx"], label_visibility="collapsed")
    # 서식·수식을 넣은 파일을 만드는 데 1초쯤 걸려서, 누를 때만 만들어요 (화면 열 그대로 + 입력 검사)
    c2.download_button("엑셀로 내보내기", lambda: to_excel_bytes(ss.ds), "시뮬레이터_입력_내보내기.xlsx", XLSX, width="stretch",
                       help="기준정보 화면과 같은 시트·열 (회색 자동 열은 수식, 맨 끝 '입력 검사'만 엑셀에 더 있어요)")
    c3.download_button("양식 내려받기", TEMPLATE_PATH.read_bytes(), TEMPLATE_PATH.name, XLSX, width="stretch")
    if c4.button("샘플 다시 불러오기", width="stretch"):
        ss.pop("_uploaded", None)
        ui.replace_dataset(load_sample())
        ss._flash = (None, "샘플 데이터를 다시 불러왔어요.", [])
        st.rerun()
    if up is not None and ss.get("_uploaded") != (up.name, up.size):
        try:
            new = load_excel(up)
        except Exception as e:  # 형식이 다른 파일
            st.error(f"가져오지 못했어요: {e}")
        else:
            ss._uploaded = (up.name, up.size)
            ui.replace_dataset(new)
            ss._flash = (None, f"{up.name}을(를) 가져왔어요. 기존 입력을 이 파일 내용으로 바꿨어요.", new.notes)
            st.rerun()


def _info(ds, m):
    name = ds.source.split(chr(92))[-1].split("/")[-1]
    ys = snapshot_years(ds)
    span = f"{ys[0]}~{ys[-1]}" if ys else "없음"
    st.markdown(f"**입력 데이터:** {name} · {len(m.parts)}개 파트 "
                f"<span style='color:{ui.MUTED};font-size:13px'>· 인원 스냅샷 {span} · 소분류 {len(ds.t(DICT))}개 · "
                f"POR {m.por} · 현재 {m.cur} (대시보드 비교 설정에서 바꿔요)</span>", unsafe_allow_html=True)
    issues = [(n, v) for n, v in ds.messages.items() if v]
    if issues:
        st.warning("  \n".join(f"**{n}** — {' / '.join(v)}" for n, v in issues))


# ---------------------------------------------------------------- 조회 → 수정 → 검사 → 저장
def _cfg(name, df, editing):
    cfg = {}
    rates = set(rate_cols(name, df)) | ({M_AX} if name == WORK else set())
    auto = set(derived_cols(name))
    for c in df.columns:
        if c == "연도" or c.endswith("연도"):
            cfg[c] = st.column_config.NumberColumn(c, format="%d", step=1)
        elif c in rates:
            cfg[c] = st.column_config.NumberColumn(c, format="%.2f" if editing and c not in auto else "percent",
                                                   min_value=0.0, max_value=1.0, help="자동 계산" if c in auto else "0.3 = 30%")
        elif c in locked_cols(name):
            cfg[c] = st.column_config.NumberColumn(c, format="%.2f", disabled=True,
                                                   help="회귀 예측 (설정 [적용] 때 계산, 고칠 수 없어요). (입력) 빈도에 값을 넣으면 그 값이 우선이에요")
        elif c in auto:
            cfg[c] = st.column_config.TextColumn(c, help="자동 (저장하지 않아요)")
    for (sh, c), opts in CHOICES.items():
        if sh == name and c in df.columns and editing:
            cfg[c] = st.column_config.SelectboxColumn(c, options=opts)
    return cfg


def _show_flash(scope):
    f = st.session_state.get("_flash")
    if f and f[0] == scope:
        st.session_state._flash = None
        st.success(f[1])
        if f[2]:
            st.warning(("확인해 보세요 (저장은 됐어요)  \n" if scope is not None else "") + "  \n".join(f[2][:15]))


def _errors(slot, errs, warns):
    lines = "".join(f"<li>{e}</li>" for e in errs[:40]) + (f"<li>… 외 {len(errs) - 40}건</li>" if len(errs) > 40 else "")
    slot.markdown(f"<div style='color:{ui.ERROR};border:1px solid {ui.ERROR};background:{ui.ERROR_SOFT};border-radius:10px;"
                  f"padding:10px 14px;font-size:14px'><b>저장하지 않았어요 — 오류 {len(errs)}건을 고친 뒤 다시 저장하세요.</b>"
                  f"<ul style='margin:6px 0 0 0'>{lines}</ul></div>", unsafe_allow_html=True)


def _style(name, df):
    """조회 화면 색: 자동 열은 회색 글씨, 조직변경의 미반영 계획 행은 레드(부정) 배경"""
    auto = [c for c in derived_cols(name) + locked_cols(name) if c in df.columns]      # 회색: 자동·회귀 열
    # Styler가 숫자 표시를 정해서(기본 소수 6자리) column_config 형식 대신 여기서 맞춰요: 비율은 %, 나머지는 짧게
    rates = set(rate_cols(name, df)) | ({M_AX} if name == WORK else set())
    # 빈 숫자 칸은 Streamlit이 회색 'None'으로 그려서, 빈칸이 있는 숫자 열은 글자로 바꿔 진짜 빈칸으로 보여요 (조회 화면만)
    df = df.copy()
    nums = []
    for c in df.columns:
        if not pd.api.types.is_float_dtype(df[c]):
            continue
        nums.append(c)
        f = (lambda v: f"{v:.0%}") if c in rates else ((lambda v: f"{v:.0f}") if c.endswith("연도") else (lambda v: f"{v:,.6g}"))
        df[c] = [("" if pd.isna(v) else f(v)) for v in df[c]]
    sty = df.style.set_properties(subset=nums, **{"text-align": "right"}) if nums else df.style
    if auto:
        sty = sty.set_properties(subset=auto, **{"color": ui.MUTED})
    if name == ORG and STATUS in df.columns:
        sty = sty.apply(lambda r: [f"background-color: {LATE_BG}" if r[STATUS] == LATE else "" for _ in r], axis=1)
    return sty


def _sheet_block(name, df, scope, caption="", to_check=None, to_full=None, extra=None, hidden=None):
    """표 하나: 조회(잠김) ↔ 수정 → 검사 → 저장.
    to_check(편집본) = 검사할 표 (행 번호 기준), to_full(편집본) = 저장할 시트 전체. extra(cols) = 버튼 줄 왼쪽에 더 그릴 것.
    hidden = 화면에 안 보이지만 함께 저장되는 같은 시트의 줄(필터 밖) — 키 중복 검사에 써요."""
    ss = st.session_state
    to_check = to_check or (lambda e: e)
    to_full = to_full or (lambda e: e)
    editing = ss.edit == scope
    busy = ss.edit is not None and not editing
    _show_flash(scope)
    bar = st.columns([5, 1.3, 1.1], vertical_alignment="center")
    mode = "**수정 중** — 셀을 고치고 줄을 더하거나 지운 뒤 저장해요 (회색 자동 열은 저장할 때 다시 계산해요)" if editing \
        else f"{len(df):,}줄 · 조회 중 (잠김)"
    bar[0].markdown(f"<span style='font-size:13px;color:{ui.MUTED}'>{caption}{mode}</span>", unsafe_allow_html=True)
    msg = st.empty()
    height = 420 if len(df) > 12 else "auto"
    df = display_table(name, df, ss.ds)
    # 빈 글자 칸은 'None' 대신 빈칸으로 보여요 (저장할 때 다시 빈 값으로 돌려요)
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):      # 글자 열 (pandas 3에서는 object 또는 str)
            df[c] = df[c].astype(object).map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else v)
    if not editing:
        if extra:
            extra(bar)
        if bar[2].button("✏️ 데이터 수정", key=f"edit_{scope}", width="stretch", disabled=busy,
                         help="다른 표를 수정 중이에요. 먼저 저장하거나 취소해요." if busy else None):
            ss.edit = scope
            ss.edit_n = ss.get("edit_n", 0) + 1
            st.rerun()
        cfg = {c: v for c, v in _cfg(name, df, False).items() if not pd.api.types.is_float_dtype(df[c])}   # 실수 열은 _style이 글자로 그려요
        st.dataframe(_style(name, df), hide_index=True, row_height=ui.TABLE_ROW_H, column_config=cfg, height=height)
        return
    save = bar[1].button("💾 변경사항 저장", key=f"save_{scope}", type="primary", width="stretch")
    cancel = bar[2].button("❌ 취소", key=f"cancel_{scope}", width="stretch")
    edited = st.data_editor(df, key=f"ed_{scope}_{ss.get('edit_n', 0)}", num_rows="dynamic", hide_index=True, row_height=ui.TABLE_ROW_H,
                            column_config=_cfg(name, df, True), height=height,
                            disabled=[c for c in derived_cols(name) + locked_cols(name) if c in df.columns])
    if cancel:
        ss.edit = None
        st.rerun()
    if save:
        e = edited.drop(columns=[c for c in derived_cols(name) if c in edited.columns])
        chk = to_check(e.reset_index(drop=True).replace({"": None}))
        errs, warns = ui.check(name, chk, hidden)
        if errs:
            _errors(msg, errs, warns)
            return
        ui.set_table(name, to_full(chk))
        ss.edit = None
        ss._flash = (scope, f"{name} 변경사항을 저장했어요. 대시보드 계산에 바로 반영돼요.", warns)
        st.rerun()


# ---------------------------------------------------------------- 연도별 시트 (인원, 파트별 업무·실적): 연도 서브탭
@st.dialog("연도 스냅샷 삭제")
def _drop_dialog(name, year):
    st.write(f"**{name}** 시트의 **{year}년** 스냅샷을 지울까요? 그 연도 계산에는 직전 연도 스냅샷을 써요.")
    c1, c2 = st.columns(2)
    if c1.button("삭제", type="primary", width="stretch"):
        ui.set_table(name, drop_year(st.session_state.ds, year, name))
        st.session_state._flash = (name, f"{year}년 스냅샷을 지웠어요.", [])
        st.rerun()
    if c2.button("취소", width="stretch"):
        st.rerun()


def _caption(name, view, y, m):
    tags = (" · POR 연도" if y == m.por else "") + (" · 현재 연도" if y == m.cur else "")
    if name == HEAD:
        ins = view[["(변동) 신입", "(변동) 전입"]].fillna(0).to_numpy().sum()
        outs = view[["(변동) 전출", "(변동) 퇴직"]].fillna(0).to_numpy().sum()
        return f"{y}년{tags} · 파트 {len(view)}개 · 총원 {view['총원'].fillna(0).sum():,.0f}명 · 변동 +{ins:g} / −{outs:g} · "
    n_m = int(view[M_MIN].notna().sum())
    n_a = int(view[IN_AX].notna().sum())
    return f"{y}년{tags} · 파트 {view['파트'].nunique()}개 · 보고 실적 {n_a}줄 · 실측 {n_m}줄 · "


def _yearly_tab(name, ds, m):
    ss = st.session_state
    _show_flash(name)
    t = ds.t(name)
    years = snapshot_years(ds, name)
    tabs = st.tabs([f"{y}년" for y in years] + ["➕ 연도 추가"])
    for tab, y in zip(tabs, years):
        with tab:
            year_rows = t[t["연도"] == y]
            pick = None
            if name == WORK:
                parts = sorted(year_rows["파트"].dropna().unique())
                pick = st.selectbox("파트 필터", ["전체"] + parts, key=f"wf_{y}", width=260,
                                    help="한 파트만 보고 고칠 수 있어요 (저장하면 다른 파트 줄은 그대로 둬요)")
                pick = None if pick == "전체" else pick
            shown = year_rows if pick is None else year_rows[year_rows["파트"] == pick]
            hidden = None if pick is None else year_rows[year_rows["파트"] != pick]
            view = shown.drop(columns=["연도"]).reset_index(drop=True)

            def check(e, y=y):
                e = e.copy()
                e.insert(0, "연도", y)
                return e

            def full(chk, y=y, hidden=hidden):
                rest = ss.ds.t(name)
                keep = rest[rest["연도"] != y]
                return pd.concat([keep] + ([hidden] if hidden is not None else []) + [chk], ignore_index=True) \
                    .sort_values("연도", kind="stable")

            def extra(bar, y=y):
                can = y != m.por and len(years) > 1 and ss.edit is None
                if bar[1].button("🗑 이 연도 삭제", key=f"drop_{name}_{y}", width="stretch", disabled=not can,
                                 help="POR 연도는 지울 수 없어요" if y == m.por else None):
                    _drop_dialog(name, y)

            _sheet_block(name, view, (name, y, pick), _caption(name, shown, y, m), check, full, extra, hidden)
    with tabs[-1]:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1.2, 3], vertical_alignment="bottom")
            ny = c1.number_input("추가할 연도", 1900, 2200, (years[-1] + 1) if years else m.por, step=1, key=f"new_year_{name}")
            src = max([y for y in years if y < ny], default=years[0] if years else None)
            go = c2.button("연도 추가", type="primary", width="stretch", disabled=ss.edit is not None or not years,
                           key=f"add_{name}")
            if name == HEAD:
                note = (f"{src}년 스냅샷을 복사해 {int(ny)}년 스냅샷을 만들어요 (변동·비고는 비워요). "
                        f"업무구분에 '{int(ny)} 목표' 열이 없으면 직전 연도 값으로 만들어요.")
            else:
                note = (f"{src}년 줄을 복사해 {int(ny)}년 스냅샷을 만들어요. (입력) 빈도·단위·건당 시간만 복사하고 "
                        "파트 목표·실측·보고 실적·비고는 비워요.")
            c3.caption(note if src else "복사할 스냅샷이 없어요.")
        if go:
            try:
                changed = add_year(ss.ds, int(ny), name)
            except ValueError as e:
                st.error(str(e))
            else:
                for n, tb in changed.items():
                    ui.set_table(n, tb)
                ss._flash = (name, f"{int(ny)}년 스냅샷을 만들었어요 ({src}년 복사). '{int(ny)}년' 탭에서 확인하고 고쳐요.", [])
                st.rerun()


# ---------------------------------------------------------------- 업무구분: AX 공통 목표 일괄 적용 + 원본
@st.dialog("모든 파트에 적용할까요?")
def _apply_dialog(codes, year, value, overrides):
    m = ui.model()
    st.write(f"{len(codes)}개 소분류의 **{year} 목표를 {value:.0f}%**로 바꿔요. 같은 직군의 모든 파트에 적용돼요.")
    if overrides:
        st.write(f"그중 **{len(overrides)}곳**은 이 목표를 파트별로 따로 고쳐 두었어요 (파트별 업무·실적의 파트 목표).")
        st.dataframe(pd.DataFrame([{"파트": p, "소분류": m.leaves[c].name, "고친 목표": f"{v:.0%}"} for p, c, v in overrides]),
                     hide_index=True, row_height=ui.TABLE_ROW_H)
    c1, c2, c3 = st.columns(3)
    keep = c1.button("고친 파트는 유지하고 적용", type="primary")
    over = c2.button("고친 파트도 덮어쓰기", disabled=not overrides)
    if c3.button("취소"):
        st.rerun()
    if keep or over:
        ss = st.session_state
        t = ss.ds.t(DICT).copy()
        col = f"{year} 목표"
        if col not in t.columns:
            t[col] = 0.0
        t.loc[t["코드"].isin(codes), col] = value / 100
        errs, _ = ui.save_table(DICT, t[SHEETS[DICT] + year_cols(t)])
        if not errs and over:
            w = ss.ds.t(WORK).copy()
            w.loc[w["코드"].isin(codes) & (w["연도"] == year), TGT] = float("nan")
            ui.save_table(WORK, w)
        ss._flash = (DICT, f"{len(codes)}개 소분류의 {year} 목표를 {value:.0f}%로 적용했어요." if not errs
                     else "적용하지 못했어요: " + " / ".join(errs[:3]), [])
        st.rerun()


@st.dialog("목표 연도 삭제")
def _drop_target_dialog(year):
    st.write(f"업무구분에서 **{year} 목표** 열을 지울까요? 그 연도 목표 계산은 공통 목표 0%가 돼요.")
    c1, c2 = st.columns(2)
    if c1.button("삭제", type="primary", width="stretch"):
        t, why = drop_target_year(st.session_state.ds, year)
        if t is None:
            st.error(why)
        else:
            ui.set_table(DICT, t)
            st.session_state._flash = (DICT, f"{year} 목표 열을 지웠어요.", [])
            st.rerun()
    if c2.button("취소", width="stretch"):
        st.rerun()


def _target_years_tool(tc, ycols):
    """목표 연도 열 추가·삭제 (표 편집기는 열을 더할 수 없어서 따로 둬요)"""
    ss = st.session_state
    busy = ss.edit is not None
    with st.container(border=True):
        c = st.columns([0.9, 1.3, 1.1, 0.3, 0.9, 1.0], vertical_alignment="bottom")
        ny = c[0].number_input("추가할 목표 연도", 1900, 2200, (max(ycols) + 1) if ycols else 2026, step=1, key="tg_new")
        copy = c[1].segmented_control("처음 값", ["직전 연도 복사", "빈칸"], default="직전 연도 복사", key="tg_copy",
                                      width="content") != "빈칸"
        if c[2].button("➕ 목표 연도 추가", type="primary", width="stretch", disabled=busy):
            try:
                t = add_target_year(ss.ds, int(ny), copy)
            except ValueError as e:
                st.error(str(e))
            else:
                ui.set_table(DICT, t)
                ss._flash = (DICT, f"{int(ny)} 목표 열을 만들었어요" + (" (직전 연도 값 복사)." if copy else " (빈칸)."), [])
                st.rerun()
        # 열이 바뀌면 다시 가장 최근 연도를 고른 상태로 (예전 선택이 남아 다른 연도를 지우지 않게)
        dy = c[4].selectbox("지울 목표 연도", sorted(ycols, reverse=True), key=f"tg_drop_{'_'.join(map(str, ycols))}",
                            disabled=not ycols)
        if c[5].button("🗑 목표 연도 삭제", width="stretch", disabled=busy or not ycols):
            _drop_target_dialog(dy)


def _dict_tab(ds, m):
    ss = st.session_state
    _show_flash(DICT)              # 목표 연도 추가·삭제·일괄 적용 결과 (표가 '최근 연도' 보기여도 보이게 여기서)
    tc = ds.t(DICT)
    ycols = [int(c[:4]) for c in year_cols(tc)]
    with st.container(border=True):
        c = st.columns([1.0, 2.4, 0.9, 0.8, 1.6], vertical_alignment="bottom")
        job = c[0].radio("직군", ["설비", "공정"], horizontal=True, key="ax_job")
        leaves = [(k, lf) for k, lf in m.leaves.items() if lf.type != "비가동" and lf.job == job]
        bigs = c[1].multiselect("대분류 (비우면 전체)", sorted({lf.big for _, lf in leaves}), key="ax_bigs", placeholder="전체")
        opts = ycols or m.years
        year = c[2].selectbox("연도", opts, index=min(1, len(opts) - 1), key="ax_bulk_year")
        val = c[3].number_input("공통 목표 (%)", 0, 100, 20, key="ax_bulk_val")
        codes = [k for k, lf in leaves if not bigs or lf.big in bigs]
        if c[4].button(f"소분류 {len(codes)}개에 일괄 적용", type="primary", width="stretch",
                       disabled=not codes or ss.edit is not None):
            overrides = [(p, x, v) for (p, x, y), v in m.tgt_part.items() if x in codes and y == year]
            _apply_dialog(codes, year, float(val), overrides)
    _target_years_tool(tc, ycols)
    # 연도가 많아지면 최근 5개 연도만 보여요 (데이터·엑셀에는 늘 모든 연도). 가린 연도는 저장할 때 코드로 다시 붙여요.
    many = len(ycols) > RECENT_TARGETS
    show_all = st.toggle(f"모든 목표 연도 보기 ({len(ycols)}개)", key="tg_all", disabled=not many,
                         help=f"끄면 최근 {RECENT_TARGETS}개 연도 목표만 보여요" if many else "연도가 5개 이하라 모두 보여요")
    hide = [f"{y} 목표" for y in sorted(ycols)[:-RECENT_TARGETS]] if many and not show_all else []
    if not hide:
        _sheet_block(DICT, tc, DICT)
        return
    hidden_vals = tc[["코드"] + hide].drop_duplicates("코드")

    def merge(e):
        out = e.merge(hidden_vals, on="코드", how="left")
        return out[SHEETS[DICT] + year_cols(out)]

    _sheet_block(DICT, tc.drop(columns=hide), (DICT, "recent"), f"최근 {RECENT_TARGETS}개 연도만 보는 중 ({hide[-1][:4]}년 이전 숨김) · ",
                 to_check=merge)


# ---------------------------------------------------------------- 파트별 업무·실적: 실적 보정 (같은 시트의 입력 vs 실측)
FREQ, BASE, MEAS = "빈도 단위", "(입력)건당 소요시간(분)", "(실측)건당 소요시간(분)"
INP, CONV = "(입력)자동화율(%)", "(실측)자동화율(%)"
CALC, SURV, DIFF = "(입력)총 소요시간(시간)", "(실측)총 소요시간(시간)", "공수 차이(시간)"


def _factor(m, part, year, unit, loc):
    """엔진과 같은 연 환산: 수행 위치가 비면 오피스, 오피스만 있는 파트는 교대 업무도 오피스(260일)"""
    loc = loc or "오피스"
    p = m.part_at(part, year)
    if p is not None and p.office_only and loc in SHIFT_LOCS:
        loc = "오피스"
    return _unit_factor(unit, loc)


def _reconcile(ds, m):
    ss = st.session_state
    w = ds.t(WORK)
    sv = w[w[M_MIN].notna()]
    if sv.empty:
        st.info("'업무·실적' 탭의 (실측) 빈도·(실측) 건당 소요시간에 실적 조사 결과를 넣으면 여기서 (입력) 값과 비교할 수 있어요.")
        return
    _show_flash("보정")
    years = sorted(sv["연도"].dropna().astype(int).unique())
    with st.container(border=True):
        c = st.columns([1, 1.4, 1.4, 1.2], vertical_alignment="bottom")
        year = c[0].selectbox("실적 연도", years, index=len(years) - 1, key="rc_year")
        thr_pp = c[1].number_input("강조: 자동화율 차이 (%p 이상)", 0, 100, 5)
        thr_h = c[2].number_input("그리고 공수 차이 (시간/년 이상)", 0, 10000, 50)
        only = c[3].toggle("강조된 줄만 보기", True)
    rows = []
    for idx, r in sv[sv["연도"] == year].iterrows():
        if r["코드"] not in m.leaves or not r[IN_MIN]:
            continue
        lf = m.leaves[r["코드"]]
        b, meas = float(r[IN_MIN]), float(r[M_MIN])
        inp = float(r[IN_AX]) if pd.notna(r[IN_AX]) else 0.0
        fq = r[M_FREQ] if pd.notna(r[M_FREQ]) else r[IN_FREQ]
        n = float(fq or 0) * _factor(m, r["파트"], year, r[UNIT], lf.loc)
        calc, surv = n * b / 60 * (1 - inp), n * meas / 60
        conv = 1 - meas / b
        diff = surv - calc
        up = conv < -1e-9
        flag = (abs(conv - inp) * 100 >= thr_pp and abs(diff) >= thr_h) or (up and abs(diff) >= thr_h)
        rows.append({"조정": flag and not up, "파트": r["파트"], "코드": r["코드"], "소분류": lf.name,
                     FREQ: f"{fq:g}/{r[UNIT]}", BASE: round(b, 1), MEAS: round(meas, 1),
                     INP: round(inp * 100), CONV: round(conv * 100), CALC: round(calc),
                     SURV: round(surv), DIFF: round(diff),
                     "상태": "건당 시간 증가" if up and flag else ("조정 검토" if flag else ""), "_up": up, "_conv": conv, "_i": idx})
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("비교할 줄이 없어요."); return
    df = df.reindex(df[DIFF].abs().sort_values(ascending=False).index)
    n_adj, n_up = int((df["상태"] == "조정 검토").sum()), int((df["상태"] == "건당 시간 증가").sum())
    gain = -df.loc[df["상태"] == "조정 검토", DIFF].sum()
    k1, k2, k3, k4 = st.columns(4)
    # 네 카드 모두 보조 줄을 두고 CSS(ui.py)로 높이를 고정해 높이를 맞춰요
    k1.metric("비교한 줄", f"{len(df)}줄", f"{year} 실측", delta_color="off", delta_arrow="off")
    k2.metric("조정 검토", f"{n_adj}줄", "자동화율 차이 큼", delta_color="off", delta_arrow="off")
    k3.metric("건당 시간 증가", f"{n_up}줄", "입력 건당 시간 검토", delta_color="off", delta_arrow="off")
    k4.metric("검토 줄을 조정하면", f"{gain / 2080:+.1f} FTE", f"연 {gain:,.0f}시간 ÷ 2,080h")

    ups = df[df["상태"] == "건당 시간 증가"]
    busy = ss.edit is not None
    a1, a2, a3 = st.columns([1.3, 2.2, 1], vertical_alignment="center")
    adj_slot = a1.empty()   # 선택한 줄 수는 표를 그린 뒤에 알 수 있어서 자리만 먼저 잡아요
    fix = a2.button(f"'건당 시간 증가' {len(ups)}줄의 (입력) 건당 시간을 실측값으로 수정", disabled=ups.empty or busy,
                    width="stretch")
    with a3.popover(f"수정 이력 ({len(ss.history)})", width="stretch", disabled=not ss.history):
        st.markdown("\n".join(f"- {h}" for h in ss.history[-50:]))
    st.caption(f"{CALC} = 실측 빈도 × 입력 건당 시간 × (1 − 입력 자동화율). {SURV} = 실측 빈도 × 실측 건당 시간. "
               f"{CONV} = 1 − 실측 건당 ÷ 입력 건당. 조정하면 같은 줄의 (입력) 자동화율을 실측값으로 바꾸고 비고에 '조사 보정'을 남겨요. "
               "건당 시간이 늘면 자동화율을 0% 아래로 내리지 않고 따로 표시해요.")
    msg = st.empty()
    view = df[df["상태"] != ""] if only else df
    key = f"rc_{year}_{only}_{ss.version}"
    ed = st.data_editor(view.drop(columns=["_up", "_conv", "_i"]), key=key, hide_index=True, row_height=ui.TABLE_ROW_H, height=420,
                        disabled=[x for x in view.columns if x != "조정"])
    sel = ed[ed["조정"]]
    if adj_slot.button(f"선택한 {len(sel)}줄 실측값으로 조정", type="primary", disabled=sel.empty or busy, width="stretch"):
        t = ss.ds.t(WORK).copy()
        hist = []
        for _, r in sel.iterrows():
            src = df[(df["파트"] == r["파트"]) & (df["코드"] == r["코드"])].iloc[0]
            conv = max(0.0, src["_conv"])
            t.loc[src["_i"], IN_AX] = round(conv, 3)
            note = t.loc[src["_i"], "비고"]
            t.loc[src["_i"], "비고"] = "조사 보정" if not isinstance(note, str) or not note else (
                note if "조사 보정" in note else f"{note} · 조사 보정")
            hist.append(f"{year} 실적 보정: {r['파트']} · {r['소분류']} {r[INP]}% → {conv:.0%}")
        errs, _ = ui.save_table(WORK, t)
        if errs:
            _errors(msg, errs, [])
        else:
            ss.history += hist
            ss._flash = ("보정", f"{len(sel)}줄의 (입력) 자동화율을 실측값으로 조정했어요.", [])
            st.rerun()
    if fix:
        # 조사 연도 + 이후 연도 줄을 함께 고쳐요. 이후 연도는 조사 연도의 수정 전 값과 같은 줄만 (따로 넣은 값은 그대로),
        # 지난 연도는 그대로 (SPEC 결정 2026-11-22 ⑥)
        t = ss.ds.t(WORK).copy()
        yrs = pd.to_numeric(t["연도"], errors="coerce")
        hist, n_rows = [], 0
        for _, r in ups.iterrows():
            inp = r[INP] / 100
            new = round(r[MEAS] / (1 - inp) if inp < 1 else r[MEAS], 1)
            old = float(t.loc[r["_i"], IN_MIN])
            later = t[(t["파트"] == r["파트"]) & (t["코드"] == r["코드"]) & (yrs > year)
                      & (pd.to_numeric(t[IN_MIN], errors="coerce").sub(old).abs() < 1e-6)].index
            idx = [r["_i"], *later]
            t.loc[idx, IN_MIN] = new
            n_rows += len(idx)
            span = f"{year}~{int(yrs[later].max())}" if len(later) else f"{year}"
            hist.append(f"{span} 입력 건당 시간 수정: {r['파트']} · {r['소분류']} {old:g}분 → {new:g}분 ({len(idx)}줄)")
        errs, _ = ui.save_table(WORK, t)
        if errs:
            _errors(msg, errs, [])
        else:
            ss.history += hist
            ss._flash = ("보정", f"{len(ups)}개 업무의 (입력) 건당 시간을 {year}년과 이후 연도 {n_rows}줄에서 고쳤어요.", [])
            st.rerun()


def _work_tab(ds, m):
    stale = ui.regression_stale()
    if stale:
        st.markdown(f'<span class="pill warn">⚠️ 회귀 예측 갱신 필요</span> <span style="font-size:13px;color:{ui.MUTED}">'
                    f'(입력) 빈도가 바뀌어 미래 연도 {stale}줄의 (회귀) 빈도가 예전 예측이에요. '
                    '대시보드 설정의 [설정 적용]을 누르면 다시 계산해요.</span>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["업무·실적", "실적 보정"])
    with t1:
        _yearly_tab(WORK, ds, m)
    with t2:
        _reconcile(ds, m)


# ---------------------------------------------------------------- 조직변경: 미반영 계획 배지 + 일괄 전환
def _org_tab(ds, m):
    ss = st.session_state
    late = late_plans(ds)
    if late.any():
        a, b = st.columns([4, 1.6], vertical_alignment="center")
        a.markdown(f'<span class="pill warn">{LATE} {int(late.sum())}줄</span> '
                   f'<span style="font-size:13px;color:{ui.MUTED}">현재 연도({m.cur}) 이하인데 아직 구분이 \'계획\'이에요. '
                   '실제로 반영됐으면 실적으로 바꿔요.</span>', unsafe_allow_html=True)
        if b.button("도래한 계획을 실적으로 일괄 전환", type="primary", width="stretch", disabled=ss.edit is not None):
            t = ds.t(ORG).copy()
            t.loc[late, "구분"] = "실적"
            errs, warns = ui.save_table(ORG, t)
            ss._flash = (ORG, f"{int(late.sum())}줄을 실적으로 바꿨어요." if not errs else "바꾸지 못했어요: " + " / ".join(errs[:3]),
                         warns)
            st.rerun()
    bundles = {}
    for name, part, y, kind in m.bundle_rows:
        bundles.setdefault(name, []).append(part)
    cap = (f"묶음 {len(bundles)}개 ({', '.join(f'{n} {len(p)}파트' for n, p in bundles.items())}) · " if bundles else "")
    _sheet_block(ORG, ds.t(ORG), ORG, cap)


# ---------------------------------------------------------------- 화면
def render():
    ss = st.session_state
    ss.setdefault("edit", None)
    st.title("기준정보")
    ds = ss.ds
    m = ui.model()
    _action_bar(ds)
    _info(ds, m)
    _show_flash(None)
    tabs = st.tabs(EDIT_SHEETS)
    for tab, name in zip(tabs, EDIT_SHEETS):
        with tab:
            st.caption(HELP[name])
            if name == DICT:
                _dict_tab(ds, m)
            elif name == WORK:
                _work_tab(ds, m)
            elif name == ORG:
                _org_tab(ds, m)
            elif name == HEAD:
                _yearly_tab(HEAD, ds, m)
            else:
                _sheet_block(name, ds.t(name), name)
