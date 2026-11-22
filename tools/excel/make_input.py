"""시뮬레이터 입력 파일 (샘플 / 빈 양식) 생성: 웹앱이 한 번에 가져오는 데이터 묶음.

여기서는 샘플 데이터만 만들고, 엑셀 쓰기는 웹앱의 [엑셀로 내보내기]와 같은 작성기(app/sim/xlsx.py)를 써요.
그래서 양식·샘플·내보내기 파일의 시트와 열이 기준정보 화면과 똑같아요.
시트 5개: 업무구분 · 파트별 업무·실적 · 조직변경 · 인원 · 설비 (+ 안내, 목록).
POR 연도·현재 연도는 엑셀에 넣지 않고 웹앱 설정(config/settings.json)에서 정해요.
"""
import sys, os, importlib.util, zlib
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("md", os.path.join(HERE, "make_dict.py"))
md = importlib.util.module_from_spec(spec); spec.loader.exec_module(md)
from sim import xlsx  # noqa: E402  (make_dict가 app 경로를 넣어 둬요)
from sim.data import DICT, EQUIP, HEAD, IN_FREQ, ORG, SHEETS, WORK, Dataset, regress_freq  # noqa: E402

YEARS = [2025, 2026, 2027, 2028, 2029, 2030]
POR = YEARS[0]              # 기준 스냅샷 (AX 없음)
ACT = 2026                  # 실적 연도 (보고 실적·실측 조사가 있는 해) = 샘플의 현재 연도
GROWTH = 1.04               # 연도별 설비(챔버) 증가율 — 설비 규모에 비례하는 업무 빈도도 같이 늘어요
SHIFT = ("교대", "DAY", "SWING", "GY")
SLOTS = ("DAY", "SWING", "GY")
WS_WORK = "파트별 업무·실적"

import sys as _sys
_sys.path.insert(0, HERE)
from sample_org import *  # noqa: 샘플 조직 데이터

# ---------- 업무 코드 ----------
LEAVES = []  # (code, 직군, 소분류, TYPE, 위치, AX2030)
_seq = {}
for row in md.ROWS:
    k = md.JPFX[row[0]] + "-" + md.TPFX[row[4]]
    _seq[k] = _seq.get(k, 0) + 1
    LEAVES.append((f"{k}-{_seq[k]:03d}", row[0], row[3], row[4], row[6], row[8]))
CODE = {(j, name): c for c, j, name, *_ in LEAVES}

# ---------- 샘플 값 ----------
BASE = {  # (직군, 소분류): (빈도, 단위, 건당 분, 파트 크기로 늘릴지)
    ("공정","Hold Lot 판정"):(6,"하루",20,1), ("공정","Lot 처분 입력 (Release/Scrap)"):(6,"하루",10,1),
    ("공정","FDC 알람 원인 확인"):(8,"하루",15,1), ("공정","Recipe·파라미터 점검"):(2,"하루",30,1),
    ("공정","Rework 판정"):(2,"하루",20,1), ("공정","Hot Lot 우선 진행 관리"):(3,"하루",15,1),
    ("공정","Split Lot 진행 관리"):(2,"하루",20,1), ("공정","교대 인수인계"):(3,"하루",30,0),
    ("공정","교대 일지 작성"):(3,"하루",15,0), ("공정","일일 수율·계측 데이터 리뷰"):(4,"하루",60,1),
    ("공정","SPC 관리 한계 갱신"):(2,"월",90,0), ("공정","Recipe 변경 검토·승인"):(3,"주",60,1),
    ("공정","공정 변경 문서 작성"):(2,"주",120,1), ("공정","일일 생산 회의"):(1,"하루",150,0),
    ("공정","주간 실적 보고서 작성"):(1,"주",240,0), ("공정","수기 보고·취합"):(5,"주",60,0),
    ("공정","개선 실험 설계·분석"):(3,"주",240,1), ("공정","영향 Lot 추적·격리"):(10,"년",240,0),
    ("공정","원인 데이터 분석"):(20,"년",960,0), ("공정","유관부서·고객 대응 보고"):(20,"년",240,0),
    ("설비","알람 확인·원격 리셋"):(16,"하루",15,1), ("설비","현장 확인·조치"):(6,"하루",30,1),
    ("설비","중성화 작업"):(1,"하루",60,1), ("설비","Chamber Vent·Purge"):(1,"하루",45,1),
    ("설비","소모 부품 교체"):(1,"하루",120,1), ("설비","Chamber Clean"):(1,"하루",90,1),
    ("설비","Seasoning·Qual 진행"):(1,"하루",60,1), ("설비","PM Code 입력"):(2,"하루",15,1),
    ("설비","고장 진단"):(2,"하루",60,1), ("설비","부품 교체 수리"):(1,"하루",120,1),
    ("설비","Vendor 출동 대응"):(2,"주",180,1), ("설비","교대 인수인계"):(4,"하루",30,0),
    ("설비","야간 설비 순찰"):(2,"하루",40,0), ("설비","일상 점검 (체크시트)"):(1,"하루",60,1),
    ("설비","소모품·가스 잔량 확인"):(3,"하루",20,1), ("설비","Spare Part 재고 확인·청구"):(3,"주",60,0),
    ("설비","MTBF·고장 이력 분석"):(2,"주",180,1), ("설비","일일 설비 회의"):(1,"하루",150,0),
    ("설비","월간 설비 가동률 보고"):(1,"월",240,0), ("설비","긴급 복구 작업"):(12,"년",240,0),
    ("설비","원인 분석·재발 방지"):(6,"년",480,0), ("설비","가스·케미컬 누출 알람 대응"):(4,"년",240,0),
    ("공통","연차"):(15,"년",480,0), ("공통","법정 교육 (안전 등)"):(4,"년",240,0),
    ("공통","직무 교육"):(4,"년",480,0), ("공통","식사"):(1,"하루",60,0), ("공통","휴식"):(2,"하루",15,0),
}
RAMP = [0.0, 0.15, 0.4, 0.65, 0.85, 1.0]     # POR(2025)은 AX 목표 0

def h(*a):  # 결정적인 0~1 값
    return (zlib.crc32("|".join(map(str, a)).encode()) % 1000) / 1000

def r5(x): return round(x * 20) / 20

IF, IU, IM = "(입력) 빈도", "빈도 단위", "(입력) 건당 소요시간(분)"

def freq_rows():
    out = []
    for site, line, part, job, head, slots, _ in PARTS:
        scale = head / 18
        for code, j, name, typ, loc, ax in LEAVES:
            if j not in (job, "공통"): continue
            fq, unit, mins, sc = BASE[(j, name)]
            if sum(slots) == 0 and loc in SHIFT: fq = 0
            if sc: fq = round(fq * scale * (0.85 + 0.3 * h(part, code)), 1)
            mins = round(mins * (0.9 + 0.2 * h(code, part, "t")))
            out.append({"파트": part, "코드": code, IF: fq, IU: unit, IM: mins, "_loc": loc, "_typ": typ})
    return calibrate(out)

# 보정 목표 (2026-11-22, 사용자 확인: 현장은 오피스·교대 모두 90% 이상 차 있고, 오피스는 OT로 100%를 넘기도 해요):
# POR에서 파트마다 오피스 업무 = 오피스 인원 업무 가능량의 95~110%(100% 넘는 파트 = OT로 버팀),
# 교대 업무 = 배치 자리의 90~96%. 파트별 값은 이름으로 정해지는 고정 난수라 다시 만들어도 같아요.
# (1인 가용: 교대 2,080 − 근무 외 비가동 168h, 오피스는 식사·휴식 하루 1.5h도 빼요)
OFFICE_FILL, SHIFT_FILL = (0.95, 1.10), (0.90, 0.96)


def fill(rng, part, kind):
    lo, hi = rng
    return lo + (hi - lo) * h(part, kind, "fill")


OUT_ALLOW, IN_DAY = 168.0, 1.5

def calibrate(rows):
    def hours(r):
        fct = {"하루": 365 if r["_loc"] in SHIFT else 260, "주": 52, "월": 12, "년": 1}[r[IU]]
        return r[IF] * fct * r[IM] / 60
    heads = {p[2]: (p[4], sum(p[5])) for p in PARTS}
    slot_of = {p[2]: p[5] for p in PARTS}
    for part, (head, slots) in heads.items():
        rs = [r for r in rows if r["파트"] == part and r["_typ"] != "비가동" and r[IF]]
        cur_shift = slots * 8 * 365 / (2080 - OUT_ALLOW)
        off = [r for r in rs if r["_loc"] not in SHIFT]
        sh = [r for r in rs if r["_loc"] in SHIFT]
        off_h, sh_h = sum(map(hours, off)), sum(map(hours, sh))
        if off_h:
            fo = (head - cur_shift) * (2080 - OUT_ALLOW - IN_DAY * 260) * fill(OFFICE_FILL, part, "office") / off_h
            for r in off: r[IF] = round(r[IF] * fo, 2)
        if sh_h and slots:
            # 근무대마다 업무를 나눠 보고(교대 = 교대 배분 비율, DAY 등 = 그 근무대), 가장 바쁜 근무대가 목표 비율이 되게 맞춰요.
            # 합계로 맞추면 배치가 고르지 않은 파트(예: 1/1/2)는 한 근무대가 100%를 넘어 자리가 올라가요.
            split = dict(zip(SLOTS, SHIFT_SPLIT.get(part, (1 / 3, 1 / 3, 1 / 3))))
            seats = dict(zip(SLOTS, slot_of[part]))
            scal, fix = {x: 0.0 for x in SLOTS}, {x: 0.0 for x in SLOTS}
            for r in sh:
                share = split if r["_loc"] == "교대" else {x: 1.0 if x == r["_loc"] else 0.0 for x in SLOTS}
                for x in SLOTS:
                    (fix if r["_typ"] == "이슈" else scal)[x] += hours(r) * share[x]
            target = fill(SHIFT_FILL, part, "shift")
            fs = min((seats[x] * 365 * (8 - IN_DAY) * target - fix[x]) / scal[x] for x in SLOTS if scal[x] > 0 and seats[x] > 0)
            for r in sh:
                if r["_typ"] != "이슈": r[IF] = round(r[IF] * fs, 2)
    for r in rows:
        r.pop("_loc"); r.pop("_typ")
    return rows

def targets():
    """코드 → {연도: 공통 목표}"""
    return {code: {y: r5(ax * k) for y, k in zip(YEARS, RAMP)} for code, j, name, typ, loc, ax in LEAVES if typ != "비가동"}

PART_TARGETS = {("P3-계측공정", CODE[("공정","수기 보고·취합")]): 0.5}      # 실적 연도 파트 목표 (공통 목표 덮어씀)

def actual_rate(part, code, job, typ, loc, slots):
    tg = targets().get(code, {}).get(ACT)
    if not tg or typ == "비가동" or (sum(slots) == 0 and loc in SHIFT): return None
    return round(tg * (0.5 + 0.8 * h(part, code, "a")), 2)

def work_rows():
    """파트별 업무·실적 = 연도별 스냅샷 (2025 POR ~ 2030).
    - 설비 규모에 비례하는 업무(BASE의 4번째 값 1)는 해마다 설비 증가율만큼 빈도가 늘어요(파트마다 조금씩 다르게) → 업무량 추이
    - 실적 연도(2026) 줄에는 (입력) 보고 실적과 (실측) 조사값을 넣어요. 실측은 실적 자동화율과 일부러 차이가 나는 줄을 섞어요(실적 보정 시연용)"""
    info = {c: (j, name, typ, loc) for c, j, name, typ, loc, ax in LEAVES}
    slots = {p[2]: p[5] for p in PARTS}
    base = freq_rows()
    out = []
    for i, y in enumerate(YEARS):
        for fr in base:
            part, code = fr["파트"], fr["코드"]
            j, name, typ, loc = info[code]
            scale = BASE[(j, name)][3] and typ != "비가동"
            g = (GROWTH * (0.98 + 0.04 * h(part, code, "g"))) ** i if scale else 1.0
            fq = round(fr[IF] * g, 2)
            row = {"연도": y, "파트": part, "코드": code, IF: fq, IU: fr[IU], IM: fr[IM],
                   "파트 목표(%)": None, "(실측) 빈도": None, "(실측) 건당 소요시간(분)": None, "(입력) 자동화율(%)": None, "비고": None}
            if y == ACT:
                a = actual_rate(part, code, j, typ, loc, slots[part])
                row["파트 목표(%)"] = PART_TARGETS.get((part, code))
                row["(입력) 자동화율(%)"] = a
                if a is not None and fq:
                    hv = h(part, code, "s")
                    true_a = a + (0.12 if hv < 0.08 else -0.10 if hv > 0.95 else 0.0)
                    meas = fr[IM] * (1 - true_a) * (1.12 if 0.5 < hv < 0.52 else 1.0)
                    row["(실측) 빈도"] = round(fq * (0.95 + 0.1 * h(part, code, "mf")), 2)
                    row["(실측) 건당 소요시간(분)"] = round(meas, 1)
            out.append(row)
    return out

def chamber_rows():
    out = []
    for site, line, part, job, head, sl, note in PARTS:
        base = CHAMBER_BASE[part]
        for i, y in enumerate(YEARS):
            if part in END_YEAR and y > END_YEAR[part]: continue
            t = round(base * (GROWTH ** (i - 1)))                     # 2026 = CHAMBER_BASE
            a = round(t * (0.96 + 0.04 * h(part, "c", y))) if y <= ACT else None
            out.append({"파트": part, "연도": y, "목표 챔버 수": t, "실적 챔버 수": a,
                        "목표 설비 수": round(t / 3.5), "실적 설비 수": round(a / 3.5) if a else None})
    for part, ys in NEW_CHAMBERS.items():
        for y, t in ys.items():
            out.append({"파트": part, "연도": y, "목표 챔버 수": t, "실적 챔버 수": None, "목표 설비 수": round(t / 3.5), "실적 설비 수": None})
    return out

# 빈 양식의 예시 행: 모든 시트가 같은 파트(EX_PART)와 업무(중성화 작업)를 가리키게 해요
_EXC = CODE[("설비","중성화 작업")]
EXAMPLES = {
    WS_WORK: [{"연도": POR, "파트": EX_PART, "코드": _EXC, IF: 1, IU: "하루", IM: 60, "파트 목표(%)": None,
               "(실측) 빈도": 1, "(실측) 건당 소요시간(분)": 55, "(입력) 자동화율(%)": 0.05, "비고": "예시"}],
    "조직변경": [{"연도": 2028, "구분": "계획", "변경 유형": "파트 묶음", "대상 파트": EX_PART, "결과 (적용처)": "예시 묶음",
                 "비고 / 상세내용": "예시: 같은 결과 이름끼리 한 묶음"}],
    "설비": [{"파트": EX_PART, "연도": POR, "목표 챔버 수": 60, "실적 챔버 수": 58, "목표 설비 수": 17, "실적 설비 수": 17}],
}

# ---------- ④ 인원 ----------
CHANGE_KINDS = ("신입", "전입", "전출", "퇴직")

def part_snapshots():
    """인원 시트 = 연도별 확정 스냅샷 (키: 연도 + 파트). 그 연도에 운영하는 파트만 넣고, 그해 인원 변동은 (변동) 열과 비고에 적어요.
    총원 = 직전 연도 총원 + 신입 + 전입 − 전출 − 퇴직 (신설 파트는 직전 총원 0)."""
    base = [(site, g, part, job, head, sl, note, PART_ID[part], YEARS[0], END_YEAR.get(part, 9999), None)
            for site, g, part, job, head, sl, note in PARTS]
    base += [(site, g, part, job, head, sl, note, pid, start, 9999, ref)
             for site, g, part, job, head, sl, note, pid, start, ref in NEW_PARTS]
    rows = []
    for y in YEARS:
        for site, g, part, job, head, sl, note, pid, start, end, ref in base:
            if not start <= y <= end:
                continue
            ch = [c for c in HEADCOUNT if c[0] == part and c[1] == y]
            kinds = {k: sum(abs(c[2]) for c in ch if c[3] == k) for k in CHANGE_KINDS}
            total = head + sum(c[2] for c in HEADCOUNT if c[0] == part and c[1] <= y)
            on = sum(sl) > 0
            dist = SHIFT_SPLIT.get(part, (1/3, 1/3, 1/3))
            mn = 1 if on else 0
            fixed = note.replace(" · 신설", "").replace("신설", "")
            notes = [fixed] + (["신설"] if y == start and start > YEARS[0] else []) + \
                    [f"{c[3]} {abs(c[2])}명" + (f" ({c[4]})" if c[4] else "") for c in ch]
            rows.append({"연도": y, "SITE": site, "그룹": g, "파트": part, "직군": job, "총원": total,
                         **{f"(변동) {k}": kinds[k] for k in CHANGE_KINDS},
                         "배치 DAY": sl[0], "배치 SWING": sl[1], "배치 GY": sl[2],
                         "최소 DAY": mn, "최소 SWING": mn, "최소 GY": 2 if "최소 2명" in note else mn,
                         "교대 배분 DAY": dist[0] if on else None, "교대 배분 SWING": dist[1] if on else None,
                         "교대 배분 GY": dist[2] if on else None,
                         "파트 ID": pid, "참고 파트": ref, "비고": " · ".join(n for n in notes if n)})
    return rows





def dict_rows(example=False):
    tg = targets()
    rows = md.dict_records({c: {y: v for y, v in d.items()} for c, d in tg.items()},
                           [md.ROWS[22]] if example else None)
    for r in rows:                                   # 연도 목표 열이 모든 행에 있게 (비가동은 빈칸)
        for y in YEARS:
            r.setdefault(f"{y} 목표", None)
    return rows


def dataset(example=False) -> Dataset:
    """샘플(또는 빈 양식 예시 행) 데이터 묶음"""
    if example:
        t = {DICT: dict_rows(True), WORK: EXAMPLES[WS_WORK], ORG: EXAMPLES["조직변경"],
             HEAD: [r for r in part_snapshots() if r["파트"] == EX_PART][:1], EQUIP: EXAMPLES["설비"]}
    else:
        org = [dict(zip(["연도", "구분", "변경 유형", "대상 파트", "결과 (적용처)", "비고 / 상세내용"], x)) for x in ORG_CHANGES]
        t = {DICT: dict_rows(), WORK: work_rows(), ORG: org, HEAD: part_snapshots(), EQUIP: chamber_rows()}
    tables = {}
    for name, rows in t.items():
        df = pd.DataFrame(rows)
        cols = SHEETS[name] + ([c for c in df.columns if c.endswith(" 목표")] if name == DICT else [])
        tables[name] = df.reindex(columns=cols)
    ds = Dataset(tables, settings={"POR 연도": POR, "현재 연도": ACT})
    if not example:
        # 미래 연도(2027~) 줄은 남기되 (입력) 빈도는 비우고, 실적 연도(2025·2026)로 1차 회귀한 (회귀) 빈도를 채워요
        w = ds.tables[WORK]
        w.loc[w["연도"] > ACT, IN_FREQ] = float("nan")
        ds.tables[WORK] = regress_freq(ds)
    return ds


# 조사 엑셀(일일 기록·정기 설문·빈도표 집계)에 넣는 업무구분 시트: 입력 파일과 같은 열 + 드롭다운용 '선택 라벨'
LABEL_COL = xlsx.col(len(SHEETS[DICT]) + len(YEARS) + 2)          # 입력 검사 다음 열
LABELS = f"업무구분!${LABEL_COL}$2:${LABEL_COL}$1000"


def survey_dict_sheet(wb):
    ws, n = xlsx.dict_sheet(wb, dataset().t(DICT), nrows=300)
    ci = n + 1
    assert xlsx.col(ci) == LABEL_COL
    c = ws.cell(row=1, column=ci, value="선택 라벨 (자동)")
    c.font = xlsx.f(True, "FFFFFF"); c.fill = xlsx.HDR_FILL; c.border = xlsx.BORDER
    ws.column_dimensions[LABEL_COL].width = 60
    for r in range(2, 1001):
        x = ws.cell(row=r, column=ci, value=f'=IF(E{r}="","",C{r}&" > "&D{r}&" > "&E{r}&" ["&A{r}&"]")')
        x.font = xlsx.f(color="475569"); x.fill = xlsx.CHK_FILL
    return ws


def lookup(dcol, r, label_col):
    """조사 엑셀: 선택 라벨(label_col 열)로 업무구분 dcol 열 값을 찾아요"""
    return (f'=IF({label_col}{r}="","",IFERROR(INDEX(업무구분!${dcol}$2:${dcol}$1000,'
            f'MATCH({label_col}{r},{LABELS},0))&"","업무구분에 없음"))')


SAMPLE_STATUS = ("샘플 데이터 (가상 값): 2개 SITE × SITE별 3개 그룹 × (공정 1 + 설비 2) = 18개 파트, 316명. POR 2025, 실적 2026. "
                 "2027년 P4 그룹 신설, 2028~2029년 계획 묶음 3개, 2029년 P3-이온주입설비 폐지. 인원·파트별 업무·실적은 2025~2030 연도별 스냅샷이고, "
                 "설비 규모에 비례하는 업무 빈도는 2026년에 약 4% 늘었고, 2027년 이후 빈도는 (회귀) 빈도(2025·2026 실적의 1차 회귀)예요.")


def build(path, ex):
    xlsx.build(dataset(ex), example=ex, status=None if ex else SAMPLE_STATUS).save(path)


if __name__ == "__main__":
    OUT = sys.argv[1] if len(sys.argv) > 1 else md.DEFAULT_OUT
    os.makedirs(OUT, exist_ok=True)
    build(os.path.join(OUT, "시뮬레이터_입력_샘플.xlsx"), False)
    build(os.path.join(OUT, "시뮬레이터_입력양식.xlsx"), True)
    print("ok", len(work_rows()), len(targets()), len(ORG_CHANGES))
