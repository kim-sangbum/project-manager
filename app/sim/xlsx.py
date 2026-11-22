"""시뮬레이터 입력 엑셀 쓰기 (하나의 작성기): 기준정보 [엑셀로 내보내기], [양식 내려받기](templates/시뮬레이터_입력양식.xlsx),
샘플 파일(templates/시뮬레이터_입력_샘플.xlsx), 조사 엑셀의 업무구분 시트가 모두 여기서 만들어져요.

열 이름과 순서는 기준정보 화면 그대로예요 (data.display_table). 화면의 회색 자동 열(업무구분 JOIN, (실측) 자동화율,
직군, 입력 안내, 상태)은 엑셀 수식으로 넣고, 화면에 없는 열은 맨 끝 '입력 검사' 하나뿐이에요(엑셀에서는 앱 검사를 못 돌려서).
인원·파트별 업무·실적은 화면에서는 연도 탭이지만 엑셀에서는 '연도' 열을 둔 시트 하나예요.
"""
from __future__ import annotations

import io

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

from .data import (DICT, EDIT_SHEETS, EQUIP, HEAD, HINT, IN_AX, IN_FREQ, IN_MIN, JOB, LATE, M_AX, M_FREQ, M_MIN, NOTE, REG_FREQ,
                   ORG, ORG_HINTS, ORG_KINDS, ORG_TYPES, RESULT, SHEETS, STATUS, TGT, UNIT, UNITS, WORK, Dataset,
                   display_table, year_cols, years_in_use)

# ---------------------------------------------------------------- 서식 (조사 엑셀 생성기도 같이 써요)
FONT = "맑은 고딕"
_thin = Side(style="thin", color="CBD5E1")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
HDR_FILL = PatternFill("solid", fgColor="1F3B77")
IN_FILL = PatternFill("solid", fgColor="FFF9DB")     # 노란 칸: 입력
CHK_FILL = PatternFill("solid", fgColor="F1F5F9")    # 회색 칸: 자동
EX_FILL = PatternFill("solid", fgColor="E2E8F0")     # 진한 회색: 예시 행

LISTS = {
    "직군": ["공정", "설비", "공통"],
    "TYPE": ["이벤트", "루틴", "이슈", "비가동"],
    "비가동 종류": ["근무 중", "근무 외"],
    "수행 위치": ["오피스", "교대", "DAY", "SWING", "GY"],
    "YN": ["Y", "N"],
    "묶을 때 방식": ["합산", "1회만"],
    "근무대": ["DAY", "SWING", "GY", "오피스"],
    "빈도 단위": UNITS,
}

D = "업무구분!"
P = "인원!"


def f(bold=False, color="000000", size=10, italic=False):
    return Font(name=FONT, bold=bold, color=color, size=size, italic=italic)


def col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def ref(key: str) -> str:
    """목록 시트의 드롭다운 범위"""
    ci = list(LISTS).index(key) + 1
    c = col(ci)
    return f"목록!${c}$2:${c}${len(LISTS[key]) + 1}"


def lists_sheet(wb):
    ws = wb.create_sheet("목록")
    for ci, (k, vals) in enumerate(LISTS.items(), start=1):
        ws.cell(row=1, column=ci, value=k).font = f(True)
        for ri, v in enumerate(vals, start=2):
            ws.cell(row=ri, column=ci, value=v).font = f()
        ws.column_dimensions[col(ci)].width = 14
    return ws


def _val(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def write_sheet(wb, name, cols, rows, formulas, nrows, example=False, height=40, freeze="A2"):
    """cols = [(열 이름, 너비, 설명, 종류)], 종류: in(입력) / pct(입력 %) / calc(자동) / calcpct(자동 %) / lock(값이지만 회색: 앱이 채움).
    rows = 입력 열 값 dict 목록. 자동 열은 formulas[열 이름](행 번호)로 채워요. nrows = 수식을 넣을 데이터 행 수."""
    ws = wb.create_sheet(name)
    for ci, (t, w, desc, kind) in enumerate(cols, start=1):
        c = ws.cell(row=1, column=ci, value=t)
        c.font = f(True, "FFFFFF")
        c.fill = HDR_FILL if not kind.startswith("calc") else PatternFill("solid", fgColor="475569")
        c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if desc:
            c.comment = Comment(desc, "양식")
        ws.column_dimensions[col(ci)].width = w
    ws.row_dimensions[1].height = height
    ws.freeze_panes = freeze
    last = 1 + max(nrows, len(rows))
    for r in range(2, last + 1):
        vals = rows[r - 2] if r - 2 < len(rows) else None
        for ci, (t, w, desc, kind) in enumerate(cols, start=1):
            c = ws.cell(row=r, column=ci)
            c.border = BORDER
            if kind.startswith("calc"):
                c.value = formulas[t](r)
                c.fill = CHK_FILL
                c.font = f(color="475569")
            else:
                if vals is not None:
                    c.value = _val(vals.get(t))
                ex = example and vals is not None
                if kind == "lock":
                    c.fill = CHK_FILL
                    c.font = f(color="475569", italic=ex)
                else:
                    c.fill = EX_FILL if ex else IN_FILL
                    c.font = f(color="0000FF", italic=ex)
            if kind in ("pct", "calcpct"):
                c.number_format = "0%"
    ws.auto_filter.ref = f"A1:{col(len(cols))}{last}"
    return ws, last


def dv_list(ws, letter, last, src):
    d = DataValidation(type="list", formula1=src, allow_blank=True, showErrorMessage=True,
                       errorTitle="목록에서 고르세요", error="목록의 값만 넣을 수 있어요.")
    ws.add_data_validation(d)
    d.add(f"{letter}2:{letter}{last}")


def dv_num(ws, letter, last, lo=None, hi=None, whole=False):
    if lo is not None and hi is not None:
        d = DataValidation(type="whole" if whole else "decimal", operator="between", formula1=str(lo), formula2=str(hi),
                           allow_blank=True, showErrorMessage=True, errorTitle="범위", error=f"{lo}~{hi} 사이로 넣어요.")
    else:
        d = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                           showErrorMessage=True, errorTitle="숫자", error="0 이상의 숫자를 넣어요.")
    ws.add_data_validation(d)
    d.add(f"{letter}2:{letter}{last}")


def _rows(df: pd.DataFrame, sort_year=False) -> list[dict]:
    if sort_year and not df.empty:
        df = df.sort_values("연도", kind="stable")
    return df.to_dict("records")


def dlookup(dcol, r, key="C"):
    """업무구분에서 코드(key 열)로 dcol 열 값을 찾아요"""
    return f'=IF({key}{r}="","",IFERROR(INDEX({D}${dcol}$2:${dcol}$1000,MATCH({key}{r},{D}$A$2:$A$1000,0))&"","업무구분에 없음"))'


def plookup(pcol, r, key):
    """인원 시트에서 파트 이름(key 열)으로 pcol 열 값을 찾아요"""
    return f'=IF({key}{r}="","",IFERROR(INDEX({P}${pcol}$2:${pcol}$1001,MATCH({key}{r},{P}$D$2:$D$1001,0))&"","인원에 없음"))'


# ---------------------------------------------------------------- ① 업무구분
DICT_DESC = {"코드": "업데이트 기준 키. 중복 불가", "직군": "공정 / 설비 / 공통", "소분류명": "계산 단위",
             "TYPE": "이벤트 / 루틴 / 이슈 / 비가동", "비가동 종류": "비가동만: 근무 중(식사·휴식) / 근무 외(연차·교육)",
             "수행 위치": "오피스 / 교대 / DAY / SWING / GY. 비가동은 비움", "라인 내 물리 업무": "Y / N. 라인 안에서 몸으로 해야 하는 업무",
             "연기 가능": "루틴만 Y / N. 교대는 다음 근무대, 오피스는 다음 날로 미룰 수 있음", "묶을 때 방식": "합산 / 1회만 (묶으면 묶음에서 1회)"}
DICT_W = {"코드": 12, "직군": 8, "대분류": 16, "중분류": 16, "소분류명": 30, "TYPE": 9, "비가동 종류": 11, "수행 위치": 10,
          "라인 내 물리 업무": 10, "연기 가능": 8, "묶을 때 방식": 10, "설명": 30}


def dict_sheet(wb, df: pd.DataFrame, example=False, nrows=300, check=True):
    """업무구분 시트. 열 = 화면 그대로 (A 코드 … L 설명, M~ 연도 목표) + 입력 검사. 만든 시트와 마지막 열 번호를 돌려줘요."""
    ycols = year_cols(df)
    cols = [(c, DICT_W[c], DICT_DESC.get(c, ""), "in") for c in SHEETS[DICT]]
    cols += [(y, 8, "연도별 공통 AX 자동화율 목표 (1건 처리 시간 기준). 같은 직군의 모든 파트에 적용", "pct") for y in ycols]
    fm = {}
    if check:
        last_y = col(12 + len(ycols))
        rate = f',IF(COUNTIF(M{{r}}:{last_y}{{r}},">1")>0,"목표는 0~100%","OK")' if ycols else ',"OK"'
        cols.append(("입력 검사", 16, "자동", "calc"))
        fm["입력 검사"] = lambda r: (
            f'=IF(E{r}="","",IF(A{r}="","코드 필요",IF(COUNTIF($A$2:$A$1000,A{r})>1,"코드 중복",'
            f'IF(F{r}="","TYPE 필요",IF(AND(F{r}="비가동",G{r}=""),"비가동 종류 필요",'
            f'IF(AND(F{r}<>"비가동",H{r}=""),"수행 위치 필요",'
            f'IF(AND(J{r}<>"",F{r}<>"루틴"),"연기 가능은 루틴만"' + rate.format(r=r) + ')))))))')   # 바깥 IF 7개
    ws, last = write_sheet(wb, DICT, cols, _rows(df), fm, nrows, example, height=36, freeze="F2")
    for key, c in (("직군", "B"), ("TYPE", "F"), ("비가동 종류", "G"), ("수행 위치", "H"), ("YN", "I"), ("YN", "J"),
                   ("묶을 때 방식", "K")):
        dv_list(ws, c, last, ref(key))
    for i in range(len(ycols)):
        dv_num(ws, col(13 + i), last, 0, 1)
    return ws, len(cols)


# ---------------------------------------------------------------- ② 파트별 업무·실적
def work_sheet(wb, df, example=False, nrows=1000):
    """열 = 화면 그대로: 연도 · 파트 · 코드 · (자동) 대분류~TYPE · (입력) 빈도 · (회귀) 빈도 · 빈도 단위 · (입력) 건당 · 파트 목표 ·
    (실측) 빈도 · (실측) 건당 · (입력) 자동화율 · (자동) (실측) 자동화율 · 비고 · 입력 검사. 수식은 열 이름으로 글자를 찾아요."""
    cols = [("연도", 7, "스냅샷 연도. 연도 + 파트 + 코드가 한 줄의 키예요. 그 연도 행이 없으면 직전 연도 행을 써요", "in"),
            ("파트", 16, "인원 시트의 파트", "in"), ("코드", 11, "업무구분의 코드", "in"),
            ("대분류", 14, "자동 (업무구분)", "calc"), ("중분류", 14, "자동", "calc"), ("소분류명", 26, "자동", "calc"),
            ("TYPE", 7, "자동", "calc"),
            (IN_FREQ, 8, "파트 전체 기준 빈도. 비가동은 1인 기준. 미래 연도는 비우면 (회귀) 빈도를 써요 (직접 예측해 넣으면 이 값이 우선)", "in"),
            (REG_FREQ, 8, "앱이 채워요: 현재 연도 −2년 ~ 현재 연도 (입력) 빈도의 1차 회귀 예측 (웹앱 설정 [적용] 때 계산). 고치지 마세요", "lock"),
            (UNIT, 7, "하루 / 주 / 월 / 년", "in"),
            (IN_MIN, 10, "AX 적용 전 기준 건당 시간(분)", "in"),
            (TGT, 8, "이 파트만 공통 목표와 다르게 할 때 (이 연도에만 적용). 비우면 업무구분의 공통 목표", "pct"),
            (M_FREQ, 8, "실적 조사로 확인한 빈도 (입력값 검수·조정용, 실적 보정 화면에서 비교)", "in"),
            (M_MIN, 10, "실적 조사로 잰 1건 처리 시간 (AX 적용 후 실제)", "in"),
            (IN_AX, 8, "파트가 보고한 실적 자동화율 (이 연도에만 적용). 실적 연도 계산에 써요", "pct"),
            (M_AX, 8, "자동: 1 − 실측 건당 ÷ 입력 건당", "calcpct"),
            ("비고", 16, "예: 조사 보정", "in"), ("입력 검사", 18, "자동", "calc")]
    L = {t: col(i) for i, (t, *_r) in enumerate(cols, start=1)}
    A, B, C, F = L["연도"], L["파트"], L["코드"], L["TYPE"]
    fq, rg, un, mn, tg, mm, ia = L[IN_FREQ], L[REG_FREQ], L[UNIT], L[IN_MIN], L[TGT], L[M_MIN], L[IN_AX]
    rng = lambda c: f"${c}$2:${c}$9001"
    fm = {"대분류": lambda r: dlookup("C", r), "중분류": lambda r: dlookup("D", r), "소분류명": lambda r: dlookup("E", r),
          "TYPE": lambda r: dlookup("F", r),
          M_AX: lambda r: f'=IF(OR({mm}{r}="",{mn}{r}="",N({mn}{r})=0),"",1-{mm}{r}/{mn}{r})',
          "입력 검사": lambda r: (
              f'=IF({B}{r}="","",IF({F}{r}="업무구분에 없음","업무구분에 없는 코드",IF(COUNTIF({P}$D$2:$D$1001,{B}{r})=0,"인원 시트에 없는 파트",'
              f'IF(COUNTIFS({rng(A)},{A}{r},{rng(B)},{B}{r},{rng(C)},{C}{r})>1,"같은 연도·파트·코드 중복",'
              f'IF(OR({A}{r}="",{un}{r}="",{mn}{r}=""),"연도·단위·건당 시간 필요",'
              f'IF(AND({fq}{r}="",{rg}{r}=""),"(입력) 빈도 필요 (미래 연도는 웹앱 [적용]으로 회귀 예측)",'
              f'IF(OR(N({tg}{r})>1,N({ia}{r})>1),"자동화율은 0~100%",'
              f'IF(AND({mm}{r}<>"",N({mn}{r})=0),"실측 건당은 입력 건당이 있어야 함","OK"))))))))')}
    ws, last = write_sheet(wb, WORK, cols, _rows(df, True), fm, nrows, example, freeze="D2")
    dv_num(ws, A, last, 2000, 2100, whole=True)
    dv_list(ws, B, last, f"{P}$D$2:$D$1001")
    dv_list(ws, un, last, ref("빈도 단위"))
    for c in (fq, mn, L[M_FREQ], mm):
        dv_num(ws, c, last)
    for c in (tg, ia):
        dv_num(ws, c, last, 0, 1)
    return ws


# ---------------------------------------------------------------- ③ 조직변경
def org_sheet(wb, df, cur, example=False, nrows=300):
    # A 상태 · B 연도 · C 구분 · D 변경 유형 · E 대상 파트 · F 직군 · G 결과 (적용처) · H 입력 안내 · I 비고 / 상세내용 · J 입력 검사
    cur_expr = "YEAR(TODAY())" if cur is None else str(int(cur))
    cols = [(STATUS, 14, f"자동: 현재 연도({'올해' if cur is None else cur}) 이하인데 '계획'이면 {LATE}", "calc"),
            ("연도", 7, "변경(또는 묶음 적용) 연도", "in"),
            ("구분", 7, "계획 / 실적", "in"),
            ("변경 유형", 10, " / ".join(ORG_TYPES), "in"),
            ("대상 파트", 16, "한 줄에 파트 하나 (쉼표로 여러 파트를 쓰지 않아요)", "in"),
            (JOB, 7, "자동 (인원 시트). 같은 묶음은 같은 직군이어야 해요", "calc"),
            (RESULT, 18, "신설·이동 = 그룹, 병합 = 존속 파트, 묶음 = 묶음 이름, 폐지 = 비움", "in"),
            (HINT, 26, "자동: 결과 칸에 넣을 값", "calc"), (NOTE, 28, "", "in"), ("입력 검사", 22, "자동", "calc")]
    hint = "".join(f'IF(D{{r}}="{k}","{v}",' for k, v in ORG_HINTS.items()) + '""' + ")" * len(ORG_HINTS)
    fm = {STATUS: lambda r: f'=IF(AND(C{r}="계획",B{r}<>"",N(B{r})<={cur_expr}),"{LATE}","")',
          JOB: lambda r: plookup("E", r, "E"),
          HINT: lambda r: f'=IF(OR(D{r}="",G{r}<>""),"",{hint.format(r=r)})',
          "입력 검사": lambda r: (
              f'=IF(E{r}="","",IF(OR(B{r}="",C{r}="",D{r}=""),"연도·구분·변경 유형 필요",'
              f'IF(F{r}="인원에 없음","인원 시트에 없는 파트",'
              f'IF(AND(D{r}="파트 폐지",G{r}<>""),"폐지는 결과를 비워요",'
              f'IF(AND(D{r}<>"파트 폐지",G{r}=""),"결과 필요",'
              f'IF(AND(D{r}="파트 병합",G{r}=E{r}),"병합 대상과 존속 파트가 같음",'
              f'IF(AND(OR(D{r}="파트 신설",D{r}="그룹 이동"),COUNTIF({P}$C$2:$C$1001,G{r})=0),"인원 시트에 없는 그룹",'
              f'IF(AND(D{r}="파트 병합",COUNTIF({P}$D$2:$D$1001,G{r})=0),"인원 시트에 없는 존속 파트",'
              f'IF(AND(D{r}="파트 묶음",COUNTIFS($D$2:$D$1001,"파트 묶음",$G$2:$G$1001,G{r},$F$2:$F$1001,"<>"&F{r})>0),"묶음 안에 직군이 섞임",'
              f'"OK")))))))))')}
    ws, last = write_sheet(wb, ORG, cols, _rows(df, True), fm, nrows, example)
    dv_num(ws, "B", last, 2000, 2100, whole=True)
    dv_list(ws, "C", last, '"' + ",".join(ORG_KINDS) + '"')
    dv_list(ws, "D", last, '"' + ",".join(ORG_TYPES) + '"')
    dv_list(ws, "E", last, f"{P}$D$2:$D$1001")
    for r in range(2, last + 1):
        ws[f"H{r}"].font = f(color="94A3B8", italic=True)
        ws[f"A{r}"].font = f(color="B4500F", bold=True)
    return ws


# ---------------------------------------------------------------- ④ 인원
HEAD_DESC = {"연도": "스냅샷 연도. 연도 + 파트가 한 줄의 키예요", "SITE": "", "그룹": "조직 그룹. 파트는 그룹 하나에 속해요",
             "파트": "파트 이름 (같은 연도 안에서 고유)", "직군": "공정 / 설비", "총원": "그 연도의 확정 총원 (직접 입력)",
             "(변동) 신입": "그 연도에 들어온 신입 (명, 기록용)", "(변동) 전입": "전입 (명)", "(변동) 전출": "전출 (명, 양수로)",
             "(변동) 퇴직": "퇴직 (명, 양수로)", "배치 DAY": "근무대별 하루 배치 인원",
             "최소 DAY": "근무대 최소 인원 (0, 1, 2 …). 2인 근무가 필요하면 2", "교대 배분 DAY": "'교대'로 등록한 업무를 나누는 비율. 합 100%",
             "파트 ID": "바뀌지 않는 고유 ID", "전신 파트 ID": "병합으로 생긴 파트의 이전 파트 ID (기록용)",
             "참고 파트": "신설 파트: 파트별 업무·실적 행이 없으면 이 파트를 복사해 챔버 수 비율로 맞춰요", "비고": "특이사항"}


def head_sheet(wb, df, example=False, nrows=500):
    # A 연도 · B SITE · C 그룹 · D 파트 · E 직군 · F 총원 · G~J (변동) · K~M 배치 · N~P 최소 · Q~S 교대 배분 · T 파트 ID · U 전신 · V 참고 · W 비고
    w = {"파트": 16, "전신 파트 ID": 12, "참고 파트": 16, "비고": 24}
    cols = [(c, w.get(c, 8 if c.startswith("교대") else 7), HEAD_DESC.get(c, ""), "pct" if c.startswith("교대 배분") else "in")
            for c in SHEETS[HEAD]] + [("입력 검사", 18, "자동", "calc")]
    R = lambda c: f"${c}$2:${c}$1001"
    fm = {"입력 검사": lambda r: (
        f'=IF(D{r}="","",IF(OR(A{r}="",B{r}="",C{r}="",E{r}=""),"연도·SITE·그룹·직군 필요",'
        f'IF(COUNTIFS({R("A")},A{r},{R("D")},D{r})>1,"같은 연도·파트 중복",'
        f'IF(AND(T{r}<>"",COUNTIFS({R("A")},A{r},{R("T")},T{r})>1),"같은 연도 파트 ID 중복",'
        f'IF(OR(F{r}="",F{r}<0),"총원 필요 (0 이상)",'
        f'IF(AND(V{r}<>"",COUNTIF({R("D")},V{r})=0),"참고 파트가 없음",'
        f'IF(OR(K{r}<N{r},L{r}<O{r},M{r}<P{r}),"배치가 최소 인원보다 적음",'
        f'IF(AND(K{r}+L{r}+M{r}>0,ABS(Q{r}+R{r}+S{r}-1)>0.005),"교대 배분 합 100% 아님","OK"))))))))')}
    ws, last = write_sheet(wb, HEAD, cols, _rows(df, True), fm, nrows, example)
    dv_num(ws, "A", last, 2000, 2100, whole=True)
    dv_list(ws, "E", last, '"공정,설비"')
    for c in "FGHIJKLMNOP":
        dv_num(ws, c, last)
    for c in "QRS":
        dv_num(ws, c, last, 0, 1)
    dv_list(ws, "V", last, "$D$2:$D$1001")
    return ws


# ---------------------------------------------------------------- ⑤ 설비
def equip_sheet(wb, df, example=False, nrows=500):
    desc = {"목표 챔버 수": "그해 관리할 Process 챔버 수 (계획)", "실적 챔버 수": "그해 실제 관리한 Process 챔버 수",
            "목표 설비 수": "그해 관리할 설비(메인프레임) 수 (계획)", "실적 설비 수": "그해 실제 관리한 설비 수"}
    cols = [(c, 16 if c == "파트" else (7 if c == "연도" else 9), desc.get(c, ""), "in") for c in SHEETS[EQUIP]] + \
           [("입력 검사", 16, "자동", "calc")]
    fm = {"입력 검사": lambda r: (f'=IF(A{r}="","",IF(COUNTIF({P}$D$2:$D$1001,A{r})=0,"인원 시트에 없는 파트",'
                                f'IF(COUNTIFS($A$2:$A$3001,A{r},$B$2:$B$3001,B{r})>1,"같은 파트·연도 중복",'
                                f'IF(AND(C{r}="",D{r}="",E{r}="",F{r}=""),"목표나 실적 필요","OK"))))')}
    ws, last = write_sheet(wb, EQUIP, cols, _rows(df, True), fm, nrows, example)
    dv_list(ws, "A", last, f"{P}$D$2:$D$1001")
    dv_num(ws, "B", last, 2000, 2100, whole=True)
    for c in "CDEF":
        dv_num(ws, c, last)
    return ws


# ---------------------------------------------------------------- 안내
def guide_sheet(wb, status: str):
    ws = wb.active
    ws.title = "안내"
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 110
    ws.cell(row=1, column=1, value="시뮬레이터 입력 파일").font = f(True, "1F3B77", 13)
    lines = [
        ("상태", status),
        ("용도", "웹앱이 한 번에 가져오는 입력 묶음이에요. 가져오면 웹앱의 기존 입력을 이 파일 내용으로 바꿔요. 예전 11시트 양식도 가져오면 이 구조로 바꿔요."),
        ("열 구성", "시트와 열 이름·순서는 웹앱 기준정보 화면과 같아요. 회색 열은 자동 계산(가져올 때 읽지 않음), 마지막 '입력 검사' 열만 엑셀에만 있어요. "
                  "인원과 파트별 업무·실적은 화면에서는 연도 탭이고, 엑셀에서는 '연도' 열로 한 시트에 모아요."),
        ("연도 설정", "POR 연도(기준 스냅샷)와 현재 연도(이 연도까지 실적 구간)는 엑셀이 아니라 웹앱의 '비교 설정'에서 정해요."),
        (DICT, "팀 공통 업무(대 > 중 > 소분류)와 속성, 오른쪽에 연도별 공통 AX 목표('2026 목표' …). 공통 목표는 같은 직군의 모든 파트에 적용돼요."),
        (WORK, "파트별 업무를 한 줄에: (입력) 빈도·단위·건당 시간(AX 전 기준) → 파트 목표 → (실측) 조사 빈도·건당 시간 → (입력) 보고 실적 자동화율. "
               "(실측) 자동화율 = 1 − 실측 건당 ÷ 입력 건당 (자동). 그 연도 행이 없으면 직전 연도 행을 쓰고, 파트 목표는 그 행의 연도에만, 보고 실적이 빈 칸이면 직전 연도 보고 실적을 이어받아요."),
        (ORG, "파트 신설·폐지·병합·그룹 이동·파트 묶음을 1행 1파트로 적어요. 구분 = 계획 / 실적. 계산은 인원 스냅샷이 기준이고 이 시트 행은 스냅샷과 맞는지 검사해요. "
              "병합된 파트 인원은 존속 파트가 흡수해 재배치 대상이 아니에요. 파트 묶음은 결과 이름이 같은 행끼리 한 묶음(교대·오피스 함께)이고, "
              "'실적' 묶음은 늘, '계획' 묶음은 대시보드 '계획 묶음 반영 = 계획대로'에서 반영해요. 신설·폐지는 인원 시트 명단이 기준이에요."),
        (HEAD, "연도별 확정 스냅샷(연도 + 파트가 키). 그해 스냅샷에 새로 생긴 파트는 신설, 빠진 파트는 폐지(인원은 재배치 대상). 스냅샷이 없는 연도는 직전 연도를 써요."),
        (EQUIP, "파트별 연도별 Process 챔버·설비 수 목표·실적. 대시보드의 '인당 관리 챔버(설비) 수'에 써요."),
        ("자동화율의 뜻", "1건을 처리하는 시간이 얼마나 자동화됐는지예요. 업무시간 = 빈도 × 기준 건당 시간 × (1 − 자동화율)."),
        ("입력 검사", "각 시트 마지막 열이 'OK'가 아니면 고쳐요. 웹앱에 가져오면 더 자세히(인원 스냅샷과의 일치 등) 검사해요."),
    ]
    r = 3
    for a, b in lines:
        ws.cell(row=r, column=1, value=a).font = f(True)
        c = ws.cell(row=r, column=2, value=b)
        c.font = f()
        c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    r += 1
    for label, fill, text in (("노란 칸", IN_FILL, "직접 입력하는 칸"), ("회색 칸", CHK_FILL, "자동 계산 칸 (가져올 때 읽지 않아요)"),
                              ("진한 회색 행", EX_FILL, "예시 행 (빈 양식). 지우고 입력하세요")):
        ws.cell(row=r, column=1, value=label).fill = fill
        ws.cell(row=r, column=2, value=text).font = f()
        r += 1


# ---------------------------------------------------------------- 파일
def build(ds: Dataset, example=False, status: str | None = None) -> Workbook:
    """example=True = 빈 양식(예시 행, 상태 열은 올해 기준). 아니면 데이터 그대로(상태 열은 앱 설정의 현재 연도 기준)."""
    wb = Workbook()
    if status is None:
        status = ("빈 양식이에요. 시트마다 회색 예시 행을 지우고 입력하세요." if example
                  else f"웹앱에서 내보낸 데이터예요 (현재 연도 {years_in_use(ds)[1]} 기준 상태 표시).")
    guide_sheet(wb, status)
    big = 3 if example else 1
    dict_sheet(wb, ds.t(DICT), example, nrows=300)
    work_sheet(wb, ds.t(WORK), example, nrows=1000 * big)
    org_sheet(wb, ds.t(ORG), None if example else years_in_use(ds)[1], example, nrows=300)
    head_sheet(wb, ds.t(HEAD), example, nrows=500 * (2 if example else 1))
    equip_sheet(wb, ds.t(EQUIP), example, nrows=500 * (2 if example else 1))
    lists_sheet(wb)
    wb._sheets = [wb[n] for n in ["안내"] + EDIT_SHEETS + ["목록"]]
    return wb


def to_bytes(ds: Dataset, example=False, status: str | None = None) -> bytes:
    buf = io.BytesIO()
    build(ds, example, status).save(buf)
    return buf.getvalue()


def screen_columns(ds: Dataset) -> dict[str, list[str]]:
    """기준정보 화면의 열 (시트별) — 엑셀 열과 같은지 시험에서 비교해요."""
    return {n: list(display_table(n, ds.t(n), ds).columns) for n in EDIT_SHEETS}
