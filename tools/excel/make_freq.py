"""파트별 업무·실적 집계 양식 (샘플 / 빈 양식) 생성 — 일일 기록 + 정기 설문 → 시뮬레이터 '파트별 업무·실적' 시트.

시트: 안내(조사 연도·조사 목적 설정) · 파트설정(= 인원 시트 열 + 조사 보조 열) · 기록취합 · 설문취합 · 기준값(실적 조사 때만)
      · 집계 작업(파트 × 업무 계산) · 파트별 업무·실적(결과: 기준정보 화면과 같은 열) · 파트요약 · 업무구분 · 목록
조사 목적: 기준 조사 → 결과의 (입력) 빈도·건당 시간 / 실적 조사 → (실측) 빈도·건당 시간 (입력 값은 '기준값'에서 가져와요).
"""
import sys, os, importlib.util, datetime
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("mi", os.path.join(HERE, "make_input.py"))
mi = importlib.util.module_from_spec(spec); spec.loader.exec_module(mi)
md, xlsx = mi.md, mi.xlsx
f, BORDER, HDR_FILL, IN_FILL, CHK_FILL, EX_FILL = xlsx.f, xlsx.BORDER, xlsx.HDR_FILL, xlsx.IN_FILL, xlsx.CHK_FILL, xlsx.EX_FILL
from sim.data import HEAD, IN_AX, IN_FREQ, IN_MIN, JOIN_COLS, M_AX, M_FREQ, M_MIN, REG_FREQ, SHEETS, TGT, UNIT, WORK  # noqa: E402
from sim.xlsx import col  # noqa: E402

NP = 100      # 파트 최대 행
NLOG = 3000   # 기록취합 최대 행
NSUR = 1000   # 설문취합 최대 행
NFREQ = 3000  # 집계 작업·결과 최대 행
SHIFT_LOCS = ("교대", "DAY", "SWING", "GY")
LABELS = mi.LABELS
lookup = mi.lookup
PURPOSES = ["기준 조사", "실적 조사"]
YEAR_CELL, PURPOSE_CELL = "안내!$B$3", "안내!$B$4"
WK = "'집계 작업'!"
BASE = "기준값!"


def header(ws, cols, height=40, freeze="B2"):
    for ci, (t, w, desc, kind) in enumerate(cols, start=1):
        c = ws.cell(row=1, column=ci, value=t)
        c.font = f(True, "FFFFFF"); c.fill = HDR_FILL; c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if desc: c.comment = Comment(desc, "양식")
        ws.column_dimensions[col(ci)].width = w
    ws.row_dimensions[1].height = height
    ws.freeze_panes = freeze

def body(ws, cols, nrows, formulas, data=None, example=False):
    data = data or []
    for r in range(2, nrows + 2):
        vals = data[r - 2] if r - 2 < len(data) else None
        for ci, (t, w, desc, kind) in enumerate(cols, start=1):
            c = ws.cell(row=r, column=ci); c.border = BORDER
            if kind.startswith("calc"):
                c.value = formulas[t](r); c.fill = CHK_FILL; c.font = f(color="475569")
            else:
                if vals is not None and t in vals and vals[t] is not None:
                    c.value = vals[t]
                ex = example and vals is not None
                c.fill = EX_FILL if ex else IN_FILL; c.font = f(color="0000FF", italic=ex)
            if kind == "date": c.number_format = "yyyy-mm-dd"
            if kind in ("pct", "calcpct"): c.number_format = "0%"
            if kind == "calc2": c.number_format = "0.00"

def add_list(ws, col_letter, nrows, src):
    d = DataValidation(type="list", formula1=src, allow_blank=True)
    ws.add_data_validation(d); d.add(f"{col_letter}2:{col_letter}{nrows+1}")

def letters(cols):
    return {t: col(i) for i, (t, *_rest) in enumerate(cols, start=1)}

# ---------------- 샘플 데이터 ----------------
CODES = md.codes()

def label(code):
    row = md.ROWS[CODES.index(code)]
    return f"{row[1]} > {row[2]} > {row[3]} [{code}]"

def sample_logs():
    """H1-포토설비1: DAY만, 조사자 1명이 5번 근무 기록. H1-포토공정: 오피스 5일 기록."""
    out = []
    d0 = datetime.date(2026, 11, 23)
    for i in range(5):
        d = d0 + datetime.timedelta(days=i)
        for code, n, mins in [("E-EV-001", 4, 40), ("E-EV-003", 1, 60), ("E-RT-001", 1, 30), ("E-RT-003", 1, 45)]:
            out.append({"날짜": d, "파트": "H1-포토설비1", "조사자 ID": "01", "근무대": "DAY",
                        "업무 (대 > 중 > 소)": label(code), "건수": n, "소요 시간 (분, 합계)": n * mins,
                        "오늘 이슈 있었음": "N", "미룰 수 있었음": "N" if code.startswith("E-RT") else None})
        for code, n, mins in [("P-RT-003", 1, 60), ("P-RT-007", 1, 30), ("P-EV-007", 2, 20)]:
            out.append({"날짜": d, "파트": "H1-포토공정", "조사자 ID": "02", "근무대": "오피스",
                        "업무 (대 > 중 > 소)": label(code), "건수": n, "소요 시간 (분, 합계)": n * mins,
                        "오늘 이슈 있었음": "N", "미룰 수 있었음": "N" if code.startswith("P-RT") else None})
    return out

def sample_survey():
    return [
        {"파트": "H1-포토설비1", "업무 (대 > 중 > 소)": label("E-RT-008"), "빈도": 1, "빈도 단위": "월", "건당 시간 (분)": 120},
        {"파트": "H1-포토설비1", "업무 (대 > 중 > 소)": label("C-AL-001"), "빈도": 15, "빈도 단위": "년", "건당 시간 (분)": 480},
        {"파트": "H1-포토설비1", "업무 (대 > 중 > 소)": label("C-AL-004"), "빈도": 1, "빈도 단위": "하루", "건당 시간 (분)": 60},
        {"파트": "H1-포토공정", "업무 (대 > 중 > 소)": label("P-RT-004"), "빈도": 2, "빈도 단위": "월", "건당 시간 (분)": 90},
        {"파트": "H1-포토공정", "업무 (대 > 중 > 소)": label("C-AL-001"), "빈도": 15, "빈도 단위": "년", "건당 시간 (분)": 480},
    ]

# ---------------- 파트설정 = 인원 시트 열(A~W) + 조사 보조 열 ----------------
PART_EXTRA = [
    ("오피스 인원 (자동)", 9, "총원 − 교대 배치 환산 인원 (배치 합 × 8h × 365 ÷ 1,912h)", "calc"),
    ("오피스 인원 보정", 9, "자동 값이 틀릴 때만 입력", "in"),
    ("기록 근무 DAY (자동)", 9, "일일 기록에 나온 DAY 근무 횟수 (날짜 × 조사자)", "calc"),
    ("기록 근무 SWING (자동)", 9, "", "calc"), ("기록 근무 GY (자동)", 9, "", "calc"),
    ("오피스 조사일수 (자동)", 9, "일일 기록에 오피스 기록이 있는 날 수", "calc"),
    ("기록 근무 DAY 보정", 9, "자동 값이 틀릴 때만 입력 (예: 업무가 없어 기록이 빠진 근무)", "in"),
    ("기록 근무 SWING 보정", 9, "", "in"), ("기록 근무 GY 보정", 9, "", "in"), ("오피스 조사일수 보정", 9, "", "in"),
    ("사용 DAY", 8, "계산에 쓰는 값: 보정 값이 있으면 보정 값", "calc"), ("사용 SWING", 8, "", "calc"),
    ("사용 GY", 8, "", "calc"), ("사용 오피스일수", 8, "", "calc"), ("사용 오피스 인원", 8, "", "calc"),
]
PART_COLS = [(c, 16 if c in ("파트", "참고 파트", "비고") else 8, "인원 시트와 같은 열 (기준정보 › 인원의 그해 줄을 그대로 붙여 넣어요)" if c == "연도" else "", "in")
             for c in SHEETS[HEAD]] + PART_EXTRA
PL = letters(PART_COLS)

def sheet_parts(wb, sample):
    ws = wb.create_sheet("파트설정")
    LOG = "기록취합!"
    def ps(slot):
        return lambda r: (f'=IF(D{r}="","",SUMIFS({LOG}$O$2:$O${NLOG+1},{LOG}$B$2:$B${NLOG+1},D{r},'
                          f'{LOG}$D$2:$D${NLOG+1},"{slot}"))')
    use = lambda auto, fix: (lambda r: f'=IF(D{r}="","",IF({PL[fix]}{r}<>"",{PL[fix]}{r},{PL[auto]}{r}))')
    fm = {
        "오피스 인원 (자동)": lambda r: f'=IF(D{r}="","",MAX(0,F{r}-(K{r}+L{r}+M{r})*8*365/1912))',
        "기록 근무 DAY (자동)": ps("DAY"), "기록 근무 SWING (자동)": ps("SWING"), "기록 근무 GY (자동)": ps("GY"),
        "오피스 조사일수 (자동)": lambda r: f'=IF(D{r}="","",SUMIFS({LOG}$P$2:$P${NLOG+1},{LOG}$B$2:$B${NLOG+1},D{r}))',
        "사용 DAY": use("기록 근무 DAY (자동)", "기록 근무 DAY 보정"),
        "사용 SWING": use("기록 근무 SWING (자동)", "기록 근무 SWING 보정"),
        "사용 GY": use("기록 근무 GY (자동)", "기록 근무 GY 보정"),
        "사용 오피스일수": use("오피스 조사일수 (자동)", "오피스 조사일수 보정"),
        "사용 오피스 인원": use("오피스 인원 (자동)", "오피스 인원 보정"),
    }
    snaps = [r for r in mi.part_snapshots() if r["연도"] == mi.POR]
    data = snaps if sample else [r for r in snaps if r["파트"] == "H1-포토설비1"]
    header(ws, PART_COLS, freeze="E2"); body(ws, PART_COLS, NP, fm, data, example=not sample)
    for r in range(2, NP + 2):
        ws[f"{PL['오피스 인원 (자동)']}{r}"].number_format = "0.0"
        ws[f"{PL['사용 오피스 인원']}{r}"].number_format = "0.0"
    add_list(ws, "E", NP, '"공정,설비"')
    return ws

def pcol(name):
    """파트설정 열 범위 (집계 작업에서 INDEX로 꺼내 써요)"""
    c = PL[name]
    return f"파트설정!${c}$2:${c}${NP+1}"

# ---------------- 기록취합 · 설문취합 ----------------
def sheet_log(wb, sample):
    ws = wb.create_sheet("기록취합")
    cols = [
        ("날짜", 11, "", "date"), ("파트", 14, "", "in"), ("조사자 ID", 8, "", "in"), ("근무대", 8, "", "in"),
        ("업무 (대 > 중 > 소)", 48, "", "in"), ("건수", 6, "", "in"), ("소요 시간 (분, 합계)", 9, "", "in"),
        ("오늘 이슈 있었음", 8, "", "in"), ("미룰 수 있었음", 8, "", "in"), ("비고", 16, "", "in"),
        ("코드", 10, "", "calc"), ("TYPE", 8, "", "calc"), ("수행 위치", 8, "업무구분의 수행 위치", "calc"),
        ("건당 시간 (분)", 8, "", "calc"),
        ("근무 첫 행", 7, "같은 파트·날짜·조사자·근무대의 첫 줄이면 1 (근무 횟수 계산용)", "calc"),
        ("오피스 날짜 첫 행", 7, "같은 파트·날짜의 오피스 첫 줄이면 1 (오피스 조사일수 계산용)", "calc"),
    ]
    fm = {
        "코드": lambda r: lookup("A", r, "E"), "TYPE": lambda r: lookup("F", r, "E"),
        "수행 위치": lambda r: lookup("H", r, "E"),
        "건당 시간 (분)": lambda r: f'=IF(OR(F{r}="",G{r}="",F{r}=0),"",G{r}/F{r})',
        "근무 첫 행": lambda r: (f'=IF(B{r}="",0,IF(COUNTIFS($B$2:B{r},B{r},$A$2:A{r},A{r},'
                                f'$C$2:C{r},C{r},$D$2:D{r},D{r})=1,1,0))'),
        "오피스 날짜 첫 행": lambda r: (f'=IF(OR(B{r}="",D{r}<>"오피스"),0,IF(COUNTIFS($B$2:B{r},B{r},'
                                     f'$A$2:A{r},A{r},$D$2:D{r},"오피스")=1,1,0))'),
    }
    header(ws, cols); body(ws, cols, NLOG, fm, sample_logs() if sample else [])
    return ws

def sheet_survey(wb, sample):
    ws = wb.create_sheet("설문취합")
    cols = [
        ("파트", 14, "", "in"), ("업무 (대 > 중 > 소)", 48, "", "in"), ("빈도", 6, "", "in"),
        ("빈도 단위", 8, "", "in"), ("건당 시간 (분)", 8, "", "in"), ("비고", 16, "", "in"),
        ("코드", 10, "", "calc"), ("찾기 키", 22, "파트|코드 (집계 작업 연결용)", "calc"),
    ]
    fm = {"코드": lambda r: lookup("A", r, "B"),
          "찾기 키": lambda r: f'=IF(OR(A{r}="",G{r}=""),"",A{r}&"|"&G{r})'}
    header(ws, cols); body(ws, cols, NSUR, fm, sample_survey() if sample else [])
    return ws

# ---------------- 기준값 (실적 조사 때: 기준정보에서 그 연도 파트별 업무·실적을 붙여 넣기) ----------------
WORK_SCREEN = ["연도", "파트", "코드", *JOIN_COLS, *SHEETS[WORK][3:11], M_AX, "비고"]   # 기준정보 화면과 같은 열
SL = {c: col(i) for i, c in enumerate(WORK_SCREEN, start=1)}                               # 열 이름 → 글자 (기준값·결과 공통)
KEY = col(len(WORK_SCREEN) + 1)                                                            # 기준값의 찾기 키 / 결과의 보조 열 시작

def sheet_base(wb):
    ws = wb.create_sheet("기준값")
    cols = [(c, 16 if c in ("파트", "소분류명") else 9, "", "in") for c in WORK_SCREEN] + \
           [("(보조) 찾기 키", 24, "파트|코드", "calc")]
    fm = {"(보조) 찾기 키": lambda r: f'=IF({SL["파트"]}{r}="","",{SL["파트"]}{r}&"|"&{SL["코드"]}{r})'}
    header(ws, cols, freeze="D2"); body(ws, cols, NFREQ, fm)
    return ws

# ---------------- 집계 작업 (파트 × 업무 계산; 예전 '빈도표') ----------------
def sheet_work(wb):
    ws = wb.create_sheet("집계 작업")
    cols = [
        ("파트", 14, "파트설정 × 업무구분 조합으로 자동 생성", "calc"), ("코드", 10, "", "calc"),
        ("소분류명", 26, "", "calc"), ("TYPE", 7, "", "calc"), ("수행 위치", 8, "", "calc"),
        ("조사 건수", 7, "일일 기록 건수 합계", "calc"),
        ("조사 건당 시간 (분)", 9, "일일 기록 평균", "calc2"),
        ("조사 추정 빈도 (파트 하루)", 10,
         "교대: 근무대별 (건수 ÷ 기록 근무 횟수) × 배치 인원을 더함. 기록이 없는 근무대는 기록된 근무대 평균을 씀. "
         "DAY·SWING·GY 전용 업무는 그 근무대만 계산. 오피스: 건수 ÷ 오피스 조사일수", "calc2"),
        ("설문 빈도", 7, "", "calc"), ("설문 단위", 7, "", "calc"), ("설문 건당 시간 (분)", 9, "", "calc"),
        ("확정 빈도", 8, "미세 조정할 때만 입력. 비우면 설문 → 조사 순서로 씀", "in"),
        ("확정 단위", 7, "", "in"), ("확정 건당 시간 (분)", 9, "", "in"),
        ("사용 빈도", 8, "결과 시트로 가는 값", "calc2"), ("사용 단위", 7, "", "calc"),
        ("사용 건당 시간 (분)", 9, "", "calc2"), ("연간 시간 (h)", 9, "빈도 × 연 환산 × 건당 시간 ÷ 60", "calc2"),
        ("출처", 7, "확정 / 설문 / 조사", "calc"),
        ("(보조) DAY 건수", 7, "", "calc"), ("(보조) SWING 건수", 7, "", "calc"), ("(보조) GY 건수", 7, "", "calc"),
        ("(보조) 오피스 건수", 7, "", "calc"), ("(보조) 파트 행", 6, "", "calc"),
        ("(보조) 직군 일치", 6, "업무 직군이 파트 직군과 같거나 '공통'이면 1. 0이면 이 행은 계산하지 않아요", "calc"),
        ("(보조) 결과 순번", 6, "결과 시트로 보내는 줄의 순번 (사용 빈도·건당 시간이 있는 줄만)", "calc"),
    ]
    nparts = f'COUNTA({pcol("파트")})'
    ncodes = 'COUNTA(업무구분!$A$2:$A$1000)'
    def pidx(r): return f'(INT(({r}-2)/{ncodes})+1)'
    def cidx(r): return f'(MOD({r}-2,{ncodes})+1)'
    def dict_at(dcol, r): return f'=IF(A{r}="","",INDEX(업무구분!${dcol}$2:${dcol}$1000,{cidx(r)})&"")'
    def pv(name, r): return f'INDEX({pcol(name)},X{r})'
    LOG = "기록취합!"
    def cnt(slot):
        return lambda r: (f'=IF(B{r}="",0,SUMIFS({LOG}$F$2:$F${NLOG+1},{LOG}$B$2:$B${NLOG+1},A{r},'
                          f'{LOG}$K$2:$K${NLOG+1},B{r},{LOG}$D$2:$D${NLOG+1},"{slot}"))')
    def est(r):
        dS, sS, gS = pv("사용 DAY", r), pv("사용 SWING", r), pv("사용 GY", r)
        bD, bS, bG = pv("배치 DAY", r), pv("배치 SWING", r), pv("배치 GY", r)
        tot = f'(T{r}+U{r}+V{r})'
        pool = f'IF(({dS}+{sS}+{gS})=0,0,{tot}/({dS}+{sS}+{gS}))'
        rate = lambda c, ps: f'IF({ps}>0,{c}{r}/{ps},{pool})'
        rD, rS, rG = f'{rate("T", dS)}*{bD}', f'{rate("U", sS)}*{bS}', f'{rate("V", gS)}*{bG}'
        shift = f'IF(E{r}="DAY",{rD},IF(E{r}="SWING",{rS},IF(E{r}="GY",{rG},{rD}+{rS}+{rG})))'
        offd = pv("사용 오피스일수", r)
        return (f'=IF(OR(B{r}="",D{r}="비가동",Y{r}=0),"",IF(OR(E{r}="교대",E{r}="DAY",E{r}="SWING",E{r}="GY"),'
                f'IF(({dS}+{sS}+{gS})=0,"",{shift}),IF({offd}>0,(T{r}+U{r}+V{r}+W{r})/{offd},"")))')
    def sv(c, r):
        return (f'=IF(B{r}="","",IFERROR(INDEX(설문취합!${c}$2:${c}${NSUR+1},'
                f'MATCH(A{r}&"|"&B{r},설문취합!$H$2:$H${NSUR+1},0))&"",""))')
    fm = {
        "파트": lambda r: f'=IF({r}-1>{nparts}*{ncodes},"",INDEX({pcol("파트")},{pidx(r)}))',
        "코드": lambda r: dict_at("A", r), "소분류명": lambda r: dict_at("E", r),
        "TYPE": lambda r: dict_at("F", r), "수행 위치": lambda r: dict_at("H", r),
        "조사 건수": lambda r: f'=IF(B{r}="","",T{r}+U{r}+V{r}+W{r})',
        "조사 건당 시간 (분)": lambda r: (f'=IF(OR(B{r}="",F{r}=0),"",SUMIFS({LOG}$G$2:$G${NLOG+1},'
                                       f'{LOG}$B$2:$B${NLOG+1},A{r},{LOG}$K$2:$K${NLOG+1},B{r})/F{r})'),
        "조사 추정 빈도 (파트 하루)": est,
        "설문 빈도": lambda r: sv("C", r), "설문 단위": lambda r: sv("D", r), "설문 건당 시간 (분)": lambda r: sv("E", r),
        "사용 빈도": lambda r: (f'=IF(OR(B{r}="",Y{r}=0),"",IF(L{r}<>"",L{r},IF(I{r}<>"",VALUE(I{r}),IF(H{r}<>"",H{r},""))))'),
        "사용 단위": lambda r: (f'=IF(OR(B{r}="",Y{r}=0),"",IF(L{r}<>"",M{r},IF(I{r}<>"",J{r},IF(H{r}<>"","하루",""))))'),
        "사용 건당 시간 (분)": lambda r: (f'=IF(OR(B{r}="",Y{r}=0),"",IF(N{r}<>"",N{r},IF(K{r}<>"",VALUE(K{r}),'
                                       f'IF(G{r}<>"",G{r},""))))'),
        "연간 시간 (h)": lambda r: (f'=IF(OR(B{r}="",O{r}="",Q{r}=""),"",O{r}*IF(P{r}="하루",'
                                   f'IF(OR(E{r}="교대",E{r}="DAY",E{r}="SWING",E{r}="GY"),365,260),'
                                   f'IF(P{r}="주",52,IF(P{r}="월",12,1)))*Q{r}/60)'),
        "출처": lambda r: f'=IF(OR(B{r}="",Y{r}=0),"",IF(L{r}<>"","확정",IF(I{r}<>"","설문",IF(H{r}<>"","조사",""))))',
        "(보조) DAY 건수": cnt("DAY"), "(보조) SWING 건수": cnt("SWING"), "(보조) GY 건수": cnt("GY"),
        "(보조) 오피스 건수": cnt("오피스"),
        "(보조) 파트 행": lambda r: f'=IF(A{r}="","",MATCH(A{r},{pcol("파트")},0))',
        "(보조) 직군 일치": lambda r: (f'=IF(B{r}="","",IF(OR(INDEX(업무구분!$B$2:$B$1000,{cidx(r)})="공통",'
                                   f'INDEX(업무구분!$B$2:$B$1000,{cidx(r)})={pv("직군", r)}),1,0))'),
        "(보조) 결과 순번": lambda r: (f'=IF(AND(N(Y{r})=1,O{r}<>"",Q{r}<>""),MAX($Z$1:Z{r - 1})+1,"")'
                                    if r > 2 else f'=IF(AND(N(Y{r})=1,O{r}<>"",Q{r}<>""),1,"")'),
    }
    header(ws, cols, 52); body(ws, cols, NFREQ, fm)
    add_list(ws, "M", NFREQ, xlsx.ref("빈도 단위"))
    ws.auto_filter.ref = f"A1:S{NFREQ+1}"
    return ws

# ---------------- 결과: 파트별 업무·실적 (기준정보 화면과 같은 열) ----------------
def factor(u, loc):
    return (f'IF({u}="하루",IF(OR({loc}="교대",{loc}="DAY",{loc}="SWING",{loc}="GY"),365,260),'
            f'IF({u}="주",52,IF({u}="월",12,IF({u}="년",1,0))))')

def sheet_result(wb):
    """결과 = 기준정보 '파트별 업무·실적'과 같은 열. 오른쪽 끝 보조 열 2개(숨김)로 집계 작업·기준값 행을 찾아요."""
    ws = wb.create_sheet(WORK)
    kinds = {"대분류": "calc", "중분류": "calc", "소분류명": "calc", "TYPE": "calc", M_AX: "calcpct", TGT: "calcpct", IN_AX: "calcpct"}
    cols = [(c, 16 if c in ("파트", "소분류명") else 9, "", kinds.get(c, "calc")) for c in WORK_SCREEN]
    cols += [("(보조) 집계 작업 행", 8, "결과 줄이 가리키는 '집계 작업' 행", "calc"),
             ("(보조) 기준값 행", 8, "실적 조사: 같은 파트·코드의 '기준값' 행", "calc")]
    QW, QB = KEY, col(len(WORK_SCREEN) + 2)
    real = f'{PURPOSE_CELL}="실적 조사"'
    W = lambda c, r: f'INDEX({WK}${c}$2:${c}${NFREQ+1},${QW}{r})'
    B = lambda name, r: f'IF(${QB}{r}="","",INDEX({BASE}${SL[name]}$2:${SL[name]}${NFREQ+1},${QB}{r})&"")'
    num = lambda x: f'IF({x}="","",VALUE({x}))'
    base_unit = lambda r: f'IF(${QB}{r}="",{W("P", r)},INDEX({BASE}${SL[UNIT]}$2:${SL[UNIT]}${NFREQ+1},${QB}{r}))'
    blank = lambda r: f'${QW}{r}=""'
    fm = {
        "(보조) 집계 작업 행": lambda r: f'=IFERROR(MATCH(ROW()-1,{WK}$Z$2:$Z${NFREQ+1},0),"")',
        "(보조) 기준값 행": lambda r: (f'=IF(OR({blank(r)},NOT({real})),"",IFERROR(MATCH({W("A", r)}&"|"&{W("B", r)},'
                                     f'{BASE}${KEY}$2:${KEY}${NFREQ+1},0),""))'),
        "연도": lambda r: f'=IF({blank(r)},"",{YEAR_CELL})',
        "파트": lambda r: f'=IF({blank(r)},"",{W("A", r)})',
        "코드": lambda r: f'=IF({blank(r)},"",{W("B", r)})',
        "대분류": lambda r: xlsx.dlookup("C", r), "중분류": lambda r: xlsx.dlookup("D", r),
        "소분류명": lambda r: xlsx.dlookup("E", r), "TYPE": lambda r: xlsx.dlookup("F", r),
        # 기준 조사 → (입력) / 실적 조사 → (입력)은 기준값에서, 조사 값은 (실측)으로. (회귀) 빈도는 웹앱이 채워요 (여기선 빈칸)
        IN_FREQ: lambda r: f'=IF({blank(r)},"",IF({real},{num(B(IN_FREQ, r))},{W("O", r)}))',
        REG_FREQ: lambda r: '=""',
        UNIT: lambda r: f'=IF({blank(r)},"",IF({real},{base_unit(r)},{W("P", r)}))',
        IN_MIN: lambda r: f'=IF({blank(r)},"",IF({real},{num(B(IN_MIN, r))},{W("Q", r)}))',
        TGT: lambda r: f'=IF(OR({blank(r)},NOT({real})),"",{num(B(TGT, r))})',
        M_FREQ: lambda r: (f'=IF(OR({blank(r)},NOT({real})),"",{W("O", r)}*{factor(W("P", r), W("E", r))}'
                           f'/MAX(1,{factor(f"{SL[UNIT]}{r}", W("E", r))}))'),
        M_MIN: lambda r: f'=IF(OR({blank(r)},NOT({real})),"",{W("Q", r)})',
        IN_AX: lambda r: f'=IF(OR({blank(r)},NOT({real})),"",{num(B(IN_AX, r))})',
        M_AX: lambda r: (f'=IF(OR({SL[M_MIN]}{r}="",{SL[IN_MIN]}{r}="",N({SL[IN_MIN]}{r})=0),"",'
                         f'1-{SL[M_MIN]}{r}/{SL[IN_MIN]}{r})'),
        "비고": lambda r: (f'=IF({blank(r)},"",IF({real},IF(${QB}{r}="","기준값 없음 — (입력) 값을 채워요",{B("비고", r)}),'
                         f'"출처: "&{W("S", r)}))'),
    }
    header(ws, cols, 40, freeze="D2"); body(ws, cols, NFREQ, fm)
    for r in range(2, NFREQ + 2):
        for name in (IN_FREQ, IN_MIN, M_FREQ, M_MIN):
            ws[f"{SL[name]}{r}"].number_format = "0.00"
    ws.auto_filter.ref = f"A1:{SL['비고']}{NFREQ+1}"
    for c in (QW, QB):                 # 계산용 보조 열은 숨겨요 (붙여 넣을 때는 A~{비고}열만)
        ws.column_dimensions[c].hidden = True
    return ws

# ---------------- 파트요약 ----------------
def sheet_summary(wb):
    ws = wb.create_sheet("파트요약")
    cols = [
        ("파트", 16, "", "calc"),
        ("교대 업무 (h/년)", 10, "수행 위치가 교대·DAY·SWING·GY인 업무 연간 시간 합 (AX 적용 전)", "calc"),
        ("오피스 업무 (h/년)", 10, "수행 위치가 오피스인 업무 연간 시간 합 (AX 적용 전)", "calc"),
        ("비가동 1인 (h/년)", 10, "설문의 비가동(1인 기준) 연간 시간 합", "calc"),
        ("오피스 인원", 8, "파트설정의 사용 오피스 인원", "calc"),
        ("오피스 인당 업무 (h/년)", 10, "오피스 업무 ÷ 오피스 인원", "calc"),
        ("1인 가용 (h/년)", 10, "2,080 − 비가동", "calc"),
        ("오피스 부하율", 9, "인당 업무 ÷ 1인 가용. 100%를 넘으면 과부하", "calc"),
    ]
    rng = lambda c: f"{WK}${c}$2:${c}${NFREQ+1}"
    def shift_sum(r):
        return "+".join(f'SUMIFS({rng("R")},{rng("A")},A{r},{rng("E")},"{s}")' for s in SHIFT_LOCS)
    fm = {
        "파트": lambda r: f'=IF(파트설정!D{r}="","",파트설정!D{r})',
        "교대 업무 (h/년)": lambda r: f'=IF(A{r}="","",{shift_sum(r)})',
        "오피스 업무 (h/년)": lambda r: f'=IF(A{r}="","",SUMIFS({rng("R")},{rng("A")},A{r},{rng("E")},"오피스"))',
        "비가동 1인 (h/년)": lambda r: f'=IF(A{r}="","",SUMIFS({rng("R")},{rng("A")},A{r},{rng("D")},"비가동"))',
        "오피스 인원": lambda r: f'=IF(A{r}="","",파트설정!{PL["사용 오피스 인원"]}{r})',
        "오피스 인당 업무 (h/년)": lambda r: f'=IF(OR(A{r}="",E{r}="",E{r}=0),"",C{r}/E{r})',
        "1인 가용 (h/년)": lambda r: f'=IF(A{r}="","",2080-D{r})',
        "오피스 부하율": lambda r: f'=IF(OR(F{r}="",G{r}=0),"",F{r}/G{r})',
    }
    header(ws, cols, 52); body(ws, cols, NP, fm)
    for r in range(2, NP + 2):
        for c in "BCDEFG": ws[f"{c}{r}"].number_format = "#,##0.0"
        ws[f"H{r}"].number_format = "0%"
    return ws

# ---------------- 안내 (조사 연도·조사 목적 설정 포함) ----------------
def guide(wb, sample):
    ws = wb.active; ws.title = "안내"
    ws.column_dimensions["A"].width = 24; ws.column_dimensions["B"].width = 100
    ws.cell(row=1, column=1, value="파트별 업무·실적 집계").font = f(True, "1F3B77", 13)
    for r, (k, v, desc) in enumerate([("조사 연도", mi.POR, "결과 시트의 '연도' (기준정보 › 파트별 업무·실적의 연도 탭)"),
                                      ("조사 목적", "기준 조사", "기준 조사 = (입력) 빈도·건당 시간 / 실적 조사 = (실측) 빈도·건당 시간")], start=3):
        ws.cell(row=r, column=1, value=k).font = f(True)
        c = ws.cell(row=r, column=2, value=v); c.fill = IN_FILL; c.font = f(color="0000FF", bold=True); c.border = BORDER
        c.comment = Comment(desc, "양식")
    d = DataValidation(type="list", formula1='"' + ",".join(PURPOSES) + '"', allow_blank=False)
    ws.add_data_validation(d); d.add("B4")
    lines = [
        ("상태", "샘플 데이터 (가상 값): H1-포토설비1(DAY만 1명 기록)과 H1-포토공정(오피스 5일 기록) 예시가 들어 있어요."
                 if sample else "빈 양식. 파트설정의 회색 예시 행은 지우고 입력하세요."),
        ("용도", "일일 기록과 정기 업무 설문을 모아 시뮬레이터의 '파트별 업무·실적' 시트(기준정보 화면과 같은 열)를 만들어요."),
        ("순서", "① 위 조사 연도·조사 목적을 정해요  ② 파트설정: 기준정보 › 인원에서 그 연도 줄을 붙여 넣기(A~W열, 같은 열이에요)  "
                 "③ 기록취합: 일일 기록 양식의 '기록' 시트 A~J열 붙여 넣기  ④ 설문취합: 정기 업무 설문의 '설문' 시트 A~F열 붙여 넣기  "
                 "⑤ (실적 조사만) 기준값: 기준정보 › 파트별 업무·실적에서 그 연도 줄을 붙여 넣기(엑셀로 내보내기의 연도~비고 열)  "
                 "⑥ 집계 작업 확인, 필요하면 '확정' 칸으로 미세 조정  ⑦ '파트별 업무·실적' 결과의 연도~비고 열을 시뮬레이터 입력 파일의 같은 시트에 붙여 넣기"),
        ("조사 목적", "기준 조사: 조사 값이 (입력) 빈도·건당 시간이 돼요(처음 조사, AX 전 기준). "
                    "실적 조사: (입력) 값·파트 목표·보고 실적은 '기준값'에서 가져오고, 조사 값은 (실측) 빈도·건당 시간으로 들어가요 → 웹앱 실적 보정 화면에서 비교해요. "
                    "(실측) 빈도는 기준값의 빈도 단위로 바꿔 적어요."),
        ("교대 업무 추정", "근무대마다 (기록 건수 ÷ 기록한 근무 횟수) × 그 근무대 배치 인원을 구해 DAY·SWING·GY를 더해요. "
                         "기록이 없는 근무대는 기록된 근무대의 1인 평균 × 배치 인원으로 채워요."),
        ("오피스 업무 추정", "오피스 업무는 파트 전체 업무를 조사해요. 빈도 = 기록 건수 ÷ 오피스 조사일수. "
                          "파트요약에서 오피스 인원(파트설정: 총원 − 교대 배치 환산, 보정 가능)으로 나눠 인당 업무량을 보여 줘요."),
        ("기록 근무 횟수", "일일 기록에 나온 (날짜 × 조사자 × 근무대) 수로 자동으로 세요. 그 근무에 기록한 업무가 하나도 없으면 빠지니, "
                        "그럴 때는 파트설정의 '보정' 칸에 실제 근무 횟수를 넣어요."),
        ("값의 우선순위", "확정(직접 입력) → 설문 → 조사 순서로 '사용' 값을 정해요. 결과 시트에는 '사용' 값이 가요(비고에 출처)."),
        ("근무대 전용 업무", "GY 순찰처럼 특정 근무대에만 있는 업무는 그 근무대를 기록하지 않으면 0으로 나와요. 설문이나 확정 값으로 채워요."),
        ("행 수", f"기록취합 {NLOG}행, 설문취합 {NSUR}행, 집계 작업·결과 {NFREQ}행(파트 수 × 업무 수)까지 계산해요. 넘으면 마지막 행을 아래로 복사해요."),
        ("업무구분", "'업무구분' 시트는 시뮬레이터 입력 파일(또는 웹앱 내보내기)의 업무구분 시트와 같아요. 바뀌면 그대로 붙여 넣고 오른쪽 끝 '선택 라벨' 열은 그대로 둬요."),
    ]
    r = 6
    for a, b in lines:
        ws.cell(row=r, column=1, value=a).font = f(True)
        c = ws.cell(row=r, column=2, value=b); c.font = f(); c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="노란 칸").fill = IN_FILL; ws.cell(row=r, column=2, value="직접 입력하거나 붙여 넣는 칸").font = f(); r += 1
    ws.cell(row=r, column=1, value="회색 칸").fill = CHK_FILL; ws.cell(row=r, column=2, value="자동 계산 칸 (수정하지 마세요)").font = f()

def build(path, sample):
    wb = Workbook()
    guide(wb, sample)
    sheet_parts(wb, sample); sheet_log(wb, sample); sheet_survey(wb, sample); sheet_base(wb)
    sheet_work(wb); sheet_result(wb); sheet_summary(wb); mi.survey_dict_sheet(wb); xlsx.lists_sheet(wb)
    wb._sheets = [wb[n] for n in ["안내", "파트설정", "기록취합", "설문취합", "기준값", "집계 작업", WORK, "파트요약", "업무구분", "목록"]]
    wb.save(path)

if __name__ == "__main__":
    OUT = sys.argv[1] if len(sys.argv) > 1 else md.DEFAULT_OUT
    os.makedirs(OUT, exist_ok=True)
    build(os.path.join(OUT, "파트별업무실적_집계_샘플.xlsx"), True)
    build(os.path.join(OUT, "파트별업무실적_집계양식.xlsx"), False)
    print("ok")
