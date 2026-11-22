import sys, os, importlib.util, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("md", os.path.join(HERE, "make_dict.py"))
md = importlib.util.module_from_spec(spec); spec.loader.exec_module(md)

FONT = md.FONT
f, BORDER, HDR_FILL, IN_FILL, CHK_FILL, EX_FILL = md.f, md.BORDER, md.HDR_FILL, md.IN_FILL, md.CHK_FILL, md.EX_FILL

spec2 = importlib.util.spec_from_file_location("mi", os.path.join(HERE, "make_input.py"))
mi = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(mi)
xlsx = mi.xlsx
dict_sheet, lists_sheet, xref, LABELS, lookup = mi.survey_dict_sheet, xlsx.lists_sheet, xlsx.ref, mi.LABELS, mi.lookup

def guide(wb, title, lines, cols):
    ws = wb.active; ws.title = "안내"
    ws.column_dimensions["A"].width = 22; ws.column_dimensions["B"].width = 95
    ws.cell(row=1, column=1, value=title).font = f(True, "1F3B77", 13)
    r = 2
    for a, b in lines:
        ws.cell(row=r, column=1, value=a).font = f(True)
        c = ws.cell(row=r, column=2, value=b); c.font = f(); c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="열 설명").font = f(True, "1F3B77", 11); r += 1
    for name, _, desc, _kind in cols:
        ws.cell(row=r, column=1, value=name).font = f(True)
        c = ws.cell(row=r, column=2, value=desc or "-"); c.font = f(); c.alignment = Alignment(wrap_text=True)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="색 안내").font = f(True, "1F3B77", 11); r += 1
    ws.cell(row=r, column=1, value="노란 칸").fill = IN_FILL
    ws.cell(row=r, column=2, value="직접 입력하는 칸").font = f(); r += 1
    ws.cell(row=r, column=1, value="회색 칸").fill = CHK_FILL
    ws.cell(row=r, column=2, value="자동 계산 칸 (수정하지 마세요)").font = f(); r += 1
    ws.cell(row=r, column=1, value="진한 회색 행").fill = EX_FILL
    ws.cell(row=r, column=2, value="예시 행. 형식을 확인한 뒤 지우고 입력하세요").font = f()

def table(wb, name, cols, example, formulas, validations, nrows=500):
    ws = wb.create_sheet(name, 1)
    for ci, (title, w, desc, kind) in enumerate(cols, start=1):
        c = ws.cell(row=1, column=ci, value=title)
        c.font = f(True, "FFFFFF"); c.fill = HDR_FILL; c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if desc: c.comment = Comment(desc, "양식")
        ws.column_dimensions[c.column_letter].width = w
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    last = 1 + nrows
    for r in range(2, last + 1):
        for ci, (title, w, desc, kind) in enumerate(cols, start=1):
            c = ws.cell(row=r, column=ci); c.border = BORDER
            if kind == "calc":
                c.value = formulas[title](r); c.fill = CHK_FILL; c.font = f(color="475569")
            else:
                if r == 2 and example.get(title) is not None:
                    c.value = example[title]; c.fill = EX_FILL; c.font = f(color="0000FF", italic=True)
                else:
                    c.fill = IN_FILL; c.font = f(color="0000FF")
            if kind == "date": c.number_format = "yyyy-mm-dd"
            if kind == "num1": c.number_format = "0.0"
    for title, (typ, src) in validations.items():
        col = chr(64 + [c[0] for c in cols].index(title) + 1)
        if typ == "list":
            d = DataValidation(type="list", formula1=src, allow_blank=True, showErrorMessage=True,
                               errorTitle="목록에서 고르세요", error="드롭다운 목록의 값만 넣을 수 있어요.")
        elif typ == "int":
            d = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                               showErrorMessage=True, errorTitle="숫자", error="0 이상의 정수를 넣어요.")
        elif typ == "num":
            d = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                               showErrorMessage=True, errorTitle="숫자", error="0 이상의 숫자를 넣어요.")
        else:
            d = DataValidation(type="date", operator="greaterThan", formula1="1", allow_blank=True,
                               showErrorMessage=True, errorTitle="날짜", error="날짜를 넣어요 (예: 2026-11-23).")
        ws.add_data_validation(d); d.add(f"{col}2:{col}{last}")
    ws.auto_filter.ref = f"A1:{chr(64+len(cols))}{last}"
    return ws

# ---------- 1. 일일 기록 양식 ----------
def daily(path):
    wb = Workbook()
    cols = [
        ("날짜", 12, "업무를 한 날짜", "date"),
        ("파트", 14, "예: H1-포토설비1", "in"),
        ("조사자 ID", 10, "익명 번호 (예: 01, 02). 이름은 적지 않아요", "in"),
        ("근무대", 9, "그 업무를 한 근무대: DAY / SWING / GY / 오피스", "in"),
        ("업무 (대 > 중 > 소)", 52, "드롭다운에서 소분류를 골라요", "in"),
        ("건수", 7, "이 줄에 기록하는 업무 건수", "in"),
        ("소요 시간 (분, 합계)", 10, "이 줄 건수 전체에 든 순수 작업 시간(분). 대기 시간은 빼요", "in"),
        ("오늘 이슈 있었음", 9, "이 날 품질 사고·환경안전·대형 다운 같은 이슈가 있었으면 Y", "in"),
        ("미룰 수 있었음", 9, "이 업무를 미룰 수 있었나요? 교대는 다음 근무대로, 오피스는 다음 날로", "in"),
        ("비고", 24, "", "in"),
        ("코드", 10, "자동", "calc"),
        ("TYPE", 8, "자동", "calc"),
        ("건당 시간 (분)", 9, "자동: 소요 시간 ÷ 건수", "calc"),
        ("입력 검사", 16, "자동. OK가 아니면 고쳐요", "calc"),
    ]
    formulas = {
        "코드": lambda r: lookup("A", r, "E"),
        "TYPE": lambda r: lookup("F", r, "E"),
        "건당 시간 (분)": lambda r: f'=IF(OR(F{r}="",G{r}="",F{r}=0),"",G{r}/F{r})',
        "입력 검사": lambda r: (f'=IF(E{r}="","",IF(K{r}="업무구분에 없음","업무를 목록에서 고르세요",'
                              f'IF(OR(A{r}="",B{r}="",C{r}="",D{r}=""),"날짜·파트·ID·근무대 필요",'
                              f'IF(OR(F{r}="",F{r}<=0),"건수 필요",IF(OR(G{r}="",G{r}<=0),"소요 시간 필요",'
                              f'IF(H{r}="","이슈 여부 필요",IF(AND(L{r}="루틴",I{r}=""),"미룰 수 있었는지 필요","OK")))))))'),
    }
    example = {"날짜": datetime.date(2026, 11, 23), "파트": "H1-포토설비1", "조사자 ID": "01", "근무대": "GY",
               "업무 (대 > 중 > 소)": "PM 업무 > PM 사전 작업 > 중성화 작업 [E-EV-003]", "건수": 2,
               "소요 시간 (분, 합계)": 90, "오늘 이슈 있었음": "N", "미룰 수 있었음": "N", "비고": "예시 행"}
    validations = {"날짜": ("date", None), "근무대": ("list", xref("근무대")), "업무 (대 > 중 > 소)": ("list", LABELS),
                   "건수": ("int", None), "소요 시간 (분, 합계)": ("num", None),
                   "오늘 이슈 있었음": ("list", xref("YN")), "미룰 수 있었음": ("list", xref("YN"))}
    guide(wb, "업무 조사 — 일일 기록 양식", [
        ("용도", "1~2주 동안 하루·주 단위로 생기는 업무와 이슈를 기록해요. 결과는 파트별 빈도표의 근거가 돼요."),
        ("누가", "파트별로 지정된 엔지니어 2~3명 (초기). 이름 대신 조사자 ID(익명 번호)를 써요."),
        ("기록 방법", "업무를 할 때마다 '기록' 시트에 한 줄씩 적어요. 같은 업무를 여러 번 했으면 건수와 합계 시간을 한 줄에 적어도 돼요."),
        ("소요 시간", "엔지니어가 직접 손을 쓴 순수 작업 시간만 적어요. 설비·시스템을 기다린 시간은 빼요."),
        ("이슈", "이슈 대응 업무도 한 줄씩 적어요. 이슈가 있었던 날은 모든 줄의 '오늘 이슈 있었음'을 Y로 적어요."),
        ("미룰 수 있었음", "루틴 업무만 적어요. 교대는 다음 근무대로, 오피스는 다음 날로 미뤄도 문제가 없었으면 Y."),
        ("기록하지 않는 것", "월·분기·년 단위 업무와 연차·교육·식사·휴식은 파트 리더의 정기 업무 설문으로 받아요."),
        ("업무 목록", "'업무구분' 시트가 드롭다운의 원본이에요. 업무 목록이 바뀌면 시뮬레이터 입력 파일(또는 웹앱 내보내기)의 업무구분 시트를 그대로 붙여 넣고, 오른쪽 끝 '선택 라벨' 열은 그대로 둬요."),
    ], cols)
    table(wb, "기록", cols, example, formulas, validations)
    dict_sheet(wb); lists_sheet(wb)
    wb._sheets = [wb[n] for n in ["안내", "기록", "업무구분", "목록"]]
    wb.save(path)

# ---------- 2. 정기 업무 설문 양식 ----------
def survey(path):
    wb = Workbook()
    cols = [
        ("파트", 14, "예: H1-포토설비1", "in"),
        ("업무 (대 > 중 > 소)", 52, "드롭다운에서 소분류를 골라요", "in"),
        ("빈도", 7, "단위 기간에 몇 번 하는지", "in"),
        ("빈도 단위", 9, "하루 / 주 / 월 / 년. 분기는 '년 4회'로 적어요", "in"),
        ("건당 시간 (분)", 9, "1회에 드는 순수 작업 시간(분)", "in"),
        ("비고", 24, "", "in"),
        ("코드", 10, "자동", "calc"),
        ("TYPE", 8, "자동", "calc"),
        ("수행 위치", 9, "자동", "calc"),
        ("연간 시간 (h)", 10, "자동: 빈도 × 연 환산 × 건당 시간 ÷ 60. 하루 단위는 교대 365일, 그 외 260일", "calc"),
        ("입력 검사", 16, "자동. OK가 아니면 고쳐요", "calc"),
    ]
    formulas = {
        "코드": lambda r: lookup("A", r, "B"),
        "TYPE": lambda r: lookup("F", r, "B"),
        "수행 위치": lambda r: lookup("H", r, "B"),
        "연간 시간 (h)": lambda r: (f'=IF(OR(C{r}="",D{r}="",E{r}=""),"",C{r}*IF(D{r}="하루",'
                                   f'IF(OR(I{r}="교대",I{r}="DAY",I{r}="SWING",I{r}="GY"),365,260),'
                                   f'IF(D{r}="주",52,IF(D{r}="월",12,1)))*E{r}/60)'),
        "입력 검사": lambda r: (f'=IF(B{r}="","",IF(G{r}="업무구분에 없음","업무를 목록에서 고르세요",'
                              f'IF(A{r}="","파트 필요",IF(OR(C{r}="",C{r}<0),"빈도 필요",'
                              f'IF(D{r}="","빈도 단위 필요",IF(OR(E{r}="",E{r}<0),"건당 시간 필요",'
                              f'IF(COUNTIFS($A$2:$A$501,A{r},$B$2:$B$501,B{r})>1,"같은 업무 중복","OK")))))))'),
    }
    example = {"파트": "H1-포토설비1", "업무 (대 > 중 > 소)": "보고·회의 > 보고서 > 월간 설비 가동률 보고 [E-RT-008]",
               "빈도": 1, "빈도 단위": "월", "건당 시간 (분)": 120, "비고": "예시 행"}
    validations = {"업무 (대 > 중 > 소)": ("list", LABELS), "빈도": ("num", None),
                   "빈도 단위": ("list", xref("빈도 단위")), "건당 시간 (분)": ("num", None)}
    guide(wb, "업무 조사 — 정기 업무 설문 양식", [
        ("용도", "1~2주 일일 기록으로는 잡히지 않는 월·분기·년 단위 업무와 비가동 시간을 파트 단위로 받아요."),
        ("누가", "파트 리더가 파트별로 한 번 작성해요."),
        ("작성 대상", "① 월·분기·년 단위로 하는 업무 (예: 월간 보고, 분기 점검)  ② 비가동: 연차·교육(근무 외), 식사·휴식(근무 중)"),
        ("비가동 작성 예", "연차: 년 15회 × 480분 · 법정 교육: 년 4회 × 240분 · 식사: 하루 1회 × 60분 · 휴식: 하루 2회 × 15분 (1인 기준)"),
        ("분기 업무", "빈도 단위에 분기가 없어요. 분기 1회는 '년 4회'로 적어요."),
        ("연간 시간", "자동 계산이에요. 숫자가 지나치게 크거나 작으면 빈도 단위를 다시 확인해요."),
        ("업무 목록", "'업무구분' 시트가 드롭다운의 원본이에요. 업무 목록이 바뀌면 시뮬레이터 입력 파일(또는 웹앱 내보내기)의 업무구분 시트를 그대로 붙여 넣고, 오른쪽 끝 '선택 라벨' 열은 그대로 둬요."),
    ], cols)
    table(wb, "설문", cols, example, formulas, validations)
    dict_sheet(wb); lists_sheet(wb)
    wb._sheets = [wb[n] for n in ["안내", "설문", "업무구분", "목록"]]
    wb.save(path)

if __name__ == "__main__":
    OUT = sys.argv[1] if len(sys.argv) > 1 else md.DEFAULT_OUT
    os.makedirs(OUT, exist_ok=True)
    daily(os.path.join(OUT, "조사_일일기록양식.xlsx"))
    survey(os.path.join(OUT, "조사_정기업무설문양식.xlsx"))
    print("ok")
