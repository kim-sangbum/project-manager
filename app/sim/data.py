"""시뮬레이터 입력 엑셀(templates/시뮬레이터_입력양식.xlsx 형식)을 읽고, 검사하고, 다시 내보내요.

엑셀 시트 이름과 열 이름은 한국어 그대로 쓰고, 입력 열만 골라 DataFrame으로 들고 있어요.
자동으로 붙는 열(업무구분 JOIN, (실측) 자동화율, 입력 안내, 상태)은 저장하지 않고 화면·내보내기 때 다시 만들어요.

시트 5개 (SPEC 3장):
- 업무구분 = 소분류 마스터 + 연도별 공통 AX 목표('2026 목표' …, 연도 수 제한 없음)
- 파트별 업무·실적 = 연도별 스냅샷 (키: 연도 + 파트 + 코드). (입력) 기준값·파트 목표·보고 실적과 (실측) 조사값을 한 줄에
- 조직변경 = 파트 신설·폐지·병합·그룹 이동·파트 묶음 (계획/실적, 1행 1파트)
- 인원 = 연도별 확정 스냅샷 (키: 연도 + 파트). (변동) 열은 기록
- 설비 = 파트별 연도별 챔버·설비 대수
POR 연도·현재 연도는 엑셀이 아니라 앱 설정 파일(config/settings.json)에 있어요.
예전 11시트 파일을 가져오면 새 구조로 바꿔요(_from_legacy).
"""
from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = ROOT / "templates" / "시뮬레이터_입력_샘플.xlsx"
TEMPLATE_PATH = ROOT / "templates" / "시뮬레이터_입력양식.xlsx"

DEFAULT_YEAR = 2026            # 연도 정보가 하나도 없을 때만 써요
SLOTS = ["DAY", "SWING", "GY"]
SHIFT_LOCS = {"교대", "DAY", "SWING", "GY"}
UNITS = ["하루", "주", "월", "년"]
JOBS = ["공정", "설비"]
CHANGE_COLS = ["(변동) 신입", "(변동) 전입", "(변동) 전출", "(변동) 퇴직"]
YEAR_COL = re.compile(r"^(\d{4}) 목표$")
SETTING_KEYS = ("POR 연도", "현재 연도")

# 시트 이름
DICT, WORK, ORG, HEAD, EQUIP = "업무구분", "파트별 업무·실적", "조직변경", "인원", "설비"

# 파트별 업무·실적 열
IN_FREQ, UNIT, IN_MIN = "(입력) 빈도", "빈도 단위", "(입력) 건당 소요시간(분)"
REG_FREQ = "(회귀) 빈도"          # 미래 연도 빈도의 1차 회귀 예측 (설정 [적용] 때 계산, 화면에서 못 고침). (입력) 빈도가 있으면 그 값을 써요
REG_WINDOW = 3                    # 회귀에 쓰는 실적 연도 수: 현재 연도 −2년 ~ 현재 연도 (없으면 있는 만큼, 1개면 기울기 0)
TGT, M_FREQ, M_MIN = "파트 목표(%)", "(실측) 빈도", "(실측) 건당 소요시간(분)"
IN_AX, M_AX = "(입력) 자동화율(%)", "(실측) 자동화율(%)"
JOIN_COLS = ["대분류", "중분류", "소분류명", "TYPE"]          # 업무구분에서 자동으로 붙여요

# 조직변경 열·유형
RESULT, NOTE, HINT, STATUS, JOB = "결과 (적용처)", "비고 / 상세내용", "입력 안내", "상태", "직군"
ORG_TYPES = ["파트 신설", "파트 폐지", "파트 병합", "그룹 이동", "파트 묶음"]
ORG_KINDS = ["계획", "실적"]
ORG_HINTS = {"파트 신설": "배속될 그룹명 (예: P4)", "파트 폐지": "(입력 불필요 — 비워 두세요)",
             "파트 병합": "통합될 존속 파트명 (예: H2-식각설비1)", "그룹 이동": "이동할 새 그룹명 (예: P3)",
             "파트 묶음": "묶음 이름 (예: B1 H1 포토설비)"}
LATE = "⚠️ 미반영 계획"

# 시트별 입력 열 (엑셀 열 이름 그대로). 업무구분은 여기에 더해 연도 목표 열을 있는 만큼 읽어요.
SHEETS: dict[str, list[str]] = {
    DICT: ["코드", "직군", "대분류", "중분류", "소분류명", "TYPE", "비가동 종류", "수행 위치",
           "라인 내 물리 업무", "연기 가능", "묶을 때 방식", "설명"],
    WORK: ["연도", "파트", "코드", IN_FREQ, REG_FREQ, UNIT, IN_MIN, TGT, M_FREQ, M_MIN, IN_AX, "비고"],
    ORG: ["연도", "구분", "변경 유형", "대상 파트", RESULT, NOTE],
    HEAD: ["연도", "SITE", "그룹", "파트", "직군", "총원", *CHANGE_COLS,
           "배치 DAY", "배치 SWING", "배치 GY", "최소 DAY", "최소 SWING", "최소 GY",
           "교대 배분 DAY", "교대 배분 SWING", "교대 배분 GY", "파트 ID", "전신 파트 ID", "참고 파트", "비고"],
    EQUIP: ["파트", "연도", "목표 챔버 수", "실적 챔버 수", "목표 설비 수", "실적 설비 수"],
}
EDIT_SHEETS = list(SHEETS)          # 기준정보 화면의 탭 순서 = 엑셀 시트 순서
KEY_COL = {DICT: "코드", WORK: "파트", ORG: "대상 파트", HEAD: "파트", EQUIP: "파트"}
REQUIRED_SHEETS = [HEAD, DICT, WORK]      # 이 셋은 꼭 있어야 계산할 수 있어요
YEARLY = (HEAD, WORK)                     # 연도별 스냅샷 시트 (화면에서 연도 탭)

# 저장 전 검사 규칙 ------------------------------------------------------------
REQUIRED_COLS = {
    HEAD: ["연도", "SITE", "그룹", "파트", "직군", "총원"],
    DICT: ["코드", "직군", "대분류", "중분류", "소분류명", "TYPE"],
    WORK: ["연도", "파트", "코드", UNIT, IN_MIN],          # 빈도는 (입력) 또는 (회귀) 중 하나 (아래 검사)
    ORG: ["연도", "구분", "변경 유형", "대상 파트"],
    EQUIP: ["파트", "연도"],
}
NUM_COLS = {
    HEAD: ["연도", "총원", *CHANGE_COLS, *(f"{k} {s}" for k in ("배치", "최소", "교대 배분") for s in SLOTS)],
    WORK: ["연도", IN_FREQ, REG_FREQ, IN_MIN, TGT, M_FREQ, M_MIN, IN_AX],
    ORG: ["연도"],
    EQUIP: ["연도", "목표 챔버 수", "실적 챔버 수", "목표 설비 수", "실적 설비 수"],
}
RATE_COLS = {HEAD: [f"교대 배분 {s}" for s in SLOTS], WORK: [TGT, IN_AX]}   # 0~1 (= 0~100%)
INT_COLS = {HEAD: ["연도", "총원", *CHANGE_COLS, *(f"{k} {s}" for k in ("배치", "최소") for s in SLOTS)], ORG: ["연도"]}
KEYS = {HEAD: ["연도", "파트"], DICT: ["코드"], WORK: ["연도", "파트", "코드"], EQUIP: ["파트", "연도"],
        ORG: ["연도", "변경 유형", "대상 파트"]}
CHOICES = {(HEAD, "직군"): JOBS, (DICT, "직군"): JOBS + ["공통"], (WORK, UNIT): UNITS,
           (ORG, "구분"): ORG_KINDS, (ORG, "변경 유형"): ORG_TYPES}
PART_REF_SHEETS = [WORK, EQUIP]           # '파트' 열이 인원 시트를 가리켜요 (조직변경은 '대상 파트')
CODE_REF_SHEETS = [WORK]


@dataclass
class Dataset:
    """가져온 입력 데이터 묶음. tables[시트 이름] = DataFrame, settings = 앱 설정(POR·현재 연도)"""
    tables: dict[str, pd.DataFrame]
    source: str = ""
    messages: dict[str, list[str]] = field(default_factory=dict)  # 시트별 검사 메시지
    settings: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)                 # 가져올 때 바꾼 내용 (예전 양식 변환)

    def t(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, empty(name))

    def copy(self) -> "Dataset":
        return Dataset({k: v.copy() for k, v in self.tables.items()}, self.source, dict(self.messages),
                       dict(self.settings), list(self.notes))


def empty(name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=SHEETS[name])


def year_cols(df: pd.DataFrame) -> list[str]:
    """업무구분의 연도 목표 열을 연도 순으로"""
    return sorted((c for c in df.columns if isinstance(c, str) and YEAR_COL.match(c)), key=lambda c: int(c[:4]))


def target_years(ds: Dataset) -> list[int]:
    return [int(c[:4]) for c in year_cols(ds.t(DICT))]


def columns(name: str, df: pd.DataFrame | None = None) -> list[str]:
    cols = list(SHEETS[name])
    if name == DICT and df is not None:
        cols += year_cols(df)
    return cols


def num_cols(name: str, df: pd.DataFrame | None = None) -> list[str]:
    if name == DICT:
        return year_cols(df) if df is not None else []
    return NUM_COLS.get(name, [])


def rate_cols(name: str, df: pd.DataFrame | None = None) -> list[str]:
    return num_cols(name, df) if name == DICT else RATE_COLS.get(name, [])


def _clean(name: str, df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).strip())
    cols = columns(name, df)
    df = df[[c for c in cols if c in df.columns]].copy()
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]
    key = KEY_COL[name]
    df = df[df[key].notna() & (df[key].astype(str).str.strip() != "")]
    nums = num_cols(name, df)
    for c in nums:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in df.columns:
        if c in nums:
            continue
        # 글자 열은 비어 있어도 글자 열로 (표에서 고칠 때 숫자 칸으로 잡히지 않게)
        df[c] = df[c].astype(object).map(lambda v: v.strip() if isinstance(v, str) else (None if pd.isna(v) else v))
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 앱 설정 (POR·현재 연도)
def config_path() -> Path:
    """앱 설정 파일. 테스트는 환경 변수 SIM_CONFIG로 다른 파일을 써요."""
    return Path(os.environ.get("SIM_CONFIG") or ROOT / "config" / "settings.json")


def load_config() -> dict:
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for k in SETTING_KEYS:
        try:
            out[k] = int(raw[k])
        except (KeyError, TypeError, ValueError):
            pass
    return out


def save_config(values: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    cur = load_config()
    cur.update({k: int(v) for k, v in values.items() if k in SETTING_KEYS})
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def settings(ds: Dataset) -> dict:
    return {k: int(v) for k, v in ds.settings.items() if k in SETTING_KEYS and v is not None}


def years_in_use(ds: Dataset) -> tuple[int, int]:
    """실제로 쓰는 (POR 연도, 현재 연도): 설정값이 없거나 POR 스냅샷이 없으면 첫 인원 스냅샷 (계산 엔진과 같은 규칙)"""
    st, snaps = settings(ds), snapshot_years(ds)
    first = snaps[0] if snaps else DEFAULT_YEAR
    por = st.get("POR 연도", first)
    if snaps and por not in snaps:
        por = first
    return por, st.get("현재 연도", por)


# ---------------------------------------------------------------- 가져오기·내보내기
def load_excel(src) -> Dataset:
    """src: 파일 경로 또는 업로드된 파일(bytes-like)."""
    raw = src.read() if hasattr(src, "read") else Path(src).read_bytes()
    xl = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
    conf = load_config()
    notes: list[str] = []
    if HEAD not in xl.sheet_names and "파트" in xl.sheet_names:
        tables = _from_legacy(xl, conf, notes)
    else:
        tables = {n: _clean(n, pd.read_excel(xl, sheet_name=n)) if n in xl.sheet_names else empty(n) for n in SHEETS}
    ds = Dataset(tables, getattr(src, "name", str(src)), settings=conf, notes=notes)
    ds.messages = validate(ds)
    return ds


def load_sample() -> Dataset:
    return load_excel(SAMPLE_PATH)


def display_table(name: str, df: pd.DataFrame, ds: Dataset) -> pd.DataFrame:
    """화면·내보내기용 표: 입력 열 + 자동 열(업무구분 JOIN, (실측) 자동화율, 입력 안내, 상태). 자동 열은 저장하지 않아요."""
    df = df.copy()
    if name == WORK:
        d = ds.t(DICT).drop_duplicates("코드").set_index("코드")
        pos = list(df.columns).index("코드") + 1
        for i, c in enumerate(JOIN_COLS):
            df.insert(pos + i, c, df["코드"].map(d[c]) if c in d.columns else None)
        inp = pd.to_numeric(df[IN_MIN], errors="coerce")
        meas = pd.to_numeric(df[M_MIN], errors="coerce")
        conv = (1 - meas / inp).where(inp > 0)
        df.insert(list(df.columns).index(IN_AX) + 1, M_AX, conv.round(3))
    elif name == ORG:
        cur = years_in_use(ds)[1]
        df.insert(0, STATUS, [LATE if k == "계획" and pd.notna(y) and int(y) <= cur else ""
                              for k, y in zip(df["구분"], df["연도"])])
        jobs = ds.t(HEAD).drop_duplicates("파트", keep="last").set_index("파트")["직군"]
        df.insert(list(df.columns).index("대상 파트") + 1, JOB, df["대상 파트"].map(jobs))
        df.insert(list(df.columns).index(RESULT) + 1, HINT,
                  [ORG_HINTS.get(t, "") if _blank(r) else "" for t, r in zip(df["변경 유형"], df[RESULT])])
    return df


def derived_cols(name: str) -> list[str]:
    return {WORK: JOIN_COLS + [M_AX], ORG: [STATUS, JOB, HINT]}.get(name, [])


def locked_cols(name: str) -> list[str]:
    """저장하지만 화면에서 고칠 수 없는 열 (회귀 예측은 설정 [적용]으로만 바뀌어요)"""
    return {WORK: [REG_FREQ]}.get(name, [])


def freq_of(row) -> float | None:
    """그 줄의 빈도: (입력) 빈도가 있으면 그 값, 없으면 (회귀) 빈도"""
    v = row.get(IN_FREQ)
    if v is not None and not (isinstance(v, float) and pd.isna(v)):
        return float(v)
    v = row.get(REG_FREQ)
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else float(v)


def regress_freq(ds: Dataset) -> pd.DataFrame:
    """파트별 업무·실적의 미래 연도(현재 연도 초과) 줄에 (회귀) 빈도를 채운 표를 돌려줘요.
    파트 × 코드마다 실적 연도(현재 연도 −2년 ~ 현재 연도, 있는 만큼)의 (입력) 빈도로 1차 최소자승 회귀 y = ax + b.
    실적 연도가 1개면 기울기 0(그 값 그대로), 음수 예측은 0. 실적 연도 줄의 (회귀) 빈도는 비워요.
    (입력) 빈도가 있는 미래 줄도 (회귀) 빈도는 채워 두지만, 계산은 (입력) 빈도를 써요."""
    w = ds.t(WORK).copy()
    if w.empty:
        return w
    cur = years_in_use(ds)[1]
    yrs = pd.to_numeric(w["연도"], errors="coerce")
    window = [y for y in sorted(yrs.dropna().astype(int).unique()) if cur - (REG_WINDOW - 1) <= y <= cur]
    hist = w[yrs.isin(window) & w[IN_FREQ].notna()]
    fits = {}
    for (part, code), g in hist.groupby(["파트", "코드"]):
        xs, ys = g["연도"].astype(float).tolist(), g[IN_FREQ].astype(float).tolist()
        if len(set(xs)) >= 2:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
            fits[(part, code)] = (a, my - a * mx)
        else:
            fits[(part, code)] = (0.0, ys[-1])
    reg = []
    for y, part, code in zip(yrs, w["파트"], w["코드"]):
        f = fits.get((part, code))
        reg.append(round(max(0.0, f[0] * y + f[1]), 2) if f is not None and pd.notna(y) and y > cur else None)
    w[REG_FREQ] = pd.to_numeric(pd.Series(reg, index=w.index), errors="coerce")
    return w


def regression_changes(ds: Dataset) -> tuple[pd.DataFrame, int]:
    """(회귀) 빈도를 지금 데이터로 다시 계산한 표와, 저장된 값과 달라지는 줄 수 (0이면 최신)"""
    old = ds.t(WORK)
    new = regress_freq(ds)
    if old.empty:
        return new, 0
    a = pd.to_numeric(old[REG_FREQ], errors="coerce").reset_index(drop=True)
    b = pd.to_numeric(new[REG_FREQ], errors="coerce").reset_index(drop=True)
    return new, int((~((a - b).abs().lt(1e-9) | (a.isna() & b.isna()))).sum())


def reg_trend(values_by_year: dict[int, float], cur: int, years) -> dict[int, float]:
    """연도 → 값 (실적 연도만)으로 같은 규칙의 회귀선을 그려요 (대시보드 추세선용)"""
    xs = [y for y in sorted(values_by_year) if cur - (REG_WINDOW - 1) <= y <= cur]
    if not xs:
        return {}
    ys = [values_by_year[x] for x in xs]
    if len(xs) >= 2:
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        b = my - a * mx
    else:
        a, b = 0.0, ys[-1]
    return {y: max(0.0, a * y + b) for y in years}


def to_excel_bytes(ds: Dataset) -> bytes:
    """기준정보 [엑셀로 내보내기]: 양식과 같은 작성기(sim.xlsx)로, 화면과 같은 열 + 자동 열 수식 + 입력 검사."""
    from .xlsx import to_bytes
    return to_bytes(ds)


# ---------------------------------------------------------------- 예전 11시트 양식 변환
def _migrate_parts(raw: pd.DataFrame, por: int) -> pd.DataFrame:
    """예전 파트 시트(연도 열 없음, 2인 필수 Y/N)를 인원 시트로: 연도 = POR, 2인 필수 Y인 근무대는 최소 인원 2"""
    raw = raw.rename(columns=lambda c: str(c).strip())
    if "연도" not in raw.columns:
        raw.insert(0, "연도", por)
    for s in SLOTS:
        two = f"2인 필수 {s}"
        if two in raw.columns:
            mins = pd.to_numeric(raw.get(f"최소 {s}"), errors="coerce").fillna(0)
            raw[f"최소 {s}"] = [max(m, 2) if str(v).strip().upper() == "Y" else m for m, v in zip(mins, raw[two])]
    return raw


def _legacy(xl, name) -> pd.DataFrame:
    if name not in xl.sheet_names:
        return pd.DataFrame()
    return pd.read_excel(xl, sheet_name=name).rename(columns=lambda c: str(c).strip())


def _from_legacy(xl, conf: dict, notes: list[str]) -> dict[str, pd.DataFrame]:
    """예전 양식(파트·후보풀·업무사전·빈도표·AX목표_공통/파트·AX실적·조직개편안·조직변경·챔버수·실적조사·설정)을 5개 시트로."""
    notes.append("예전 양식(11시트)이라 새 5시트 구조로 바꿔 가져왔어요.")
    old_set = _legacy(xl, "설정")
    old_por = None
    if not old_set.empty and "항목" in old_set:
        v = pd.to_numeric(old_set.loc[old_set["항목"] == "POR 연도", "값"], errors="coerce").dropna()
        old_por = int(v.iloc[0]) if len(v) else None
    raw_parts = _legacy(xl, "파트")
    por = conf.get("POR 연도") or old_por or (int(pd.to_numeric(raw_parts["연도"]).min()) if "연도" in raw_parts else DEFAULT_YEAR)
    out = {HEAD: _clean(HEAD, _migrate_parts(raw_parts, por))}
    out[EQUIP] = _clean(EQUIP, _legacy(xl, "챔버수"))

    d = _legacy(xl, "업무사전").rename(columns={"소분류": "소분류명", "묶을 때 처리 방식": "묶을 때 방식"})
    tc = _legacy(xl, "AX목표_공통")
    if not d.empty and not tc.empty:
        d = d.merge(tc[["코드"] + year_cols(tc)], on="코드", how="left")
    out[DICT] = _clean(DICT, d) if not d.empty else empty(DICT)

    fq = _legacy(xl, "빈도표")
    tp, ac, sv = _legacy(xl, "AX목표_파트"), _legacy(xl, "AX실적"), _legacy(xl, "실적조사")
    years = {por} | {int(y) for t in (tp, ac, sv) if "연도" in t for y in pd.to_numeric(t["연도"], errors="coerce").dropna()}
    rows = []
    if not fq.empty:
        base = fq.rename(columns={"빈도": IN_FREQ, "건당 시간 (분, POR 기준)": IN_MIN})
        look = lambda t, col: {(r["파트"], r["코드"], int(r["연도"])): r[col] for _, r in t.iterrows()
                               if col in t and pd.notna(r.get("연도")) and pd.notna(r.get(col))}
        tgt, act = look(tp, "목표"), look(ac, "실적")
        src = {k: v for k, v in look(ac, "출처").items()}
        sf, sm = look(sv, "조사 빈도"), look(sv, "조사 건당 시간 (분)")
        for y in sorted(years):
            for _, r in base.iterrows():
                k = (r["파트"], r["코드"], y)
                rows.append({"연도": y, "파트": r["파트"], "코드": r["코드"], IN_FREQ: r[IN_FREQ], UNIT: r["빈도 단위"],
                             IN_MIN: r[IN_MIN], TGT: tgt.get(k), M_FREQ: sf.get(k), M_MIN: sm.get(k), IN_AX: act.get(k),
                             "비고": "조사 보정" if src.get(k) == "조사 보정" else None})
    out[WORK] = _clean(WORK, pd.DataFrame(rows, columns=SHEETS[WORK]))
    if len(years) > 1:
        notes.append(f"빈도표를 {', '.join(map(str, sorted(years)))}년 스냅샷으로 복사하고 AX목표_파트·AX실적·실적조사를 같은 줄에 합쳤어요.")

    org = []
    plans = _legacy(xl, "조직개편안")
    if not plans.empty:
        first = plans["개편안"].dropna().iloc[0]
        if plans["개편안"].nunique() > 1:
            notes.append(f"조직개편안이 여러 개라 첫 번째 '{first}'만 조직변경(파트 묶음, 계획)으로 옮겼어요.")
        p = plans[plans["개편안"] == first]
        for (name, part), g in p.groupby(["묶음", "파트"], sort=False):
            org.append({"연도": int(pd.to_numeric(g["적용 시작 연도"]).min()), "구분": "계획", "변경 유형": "파트 묶음",
                        "대상 파트": part, RESULT: name, NOTE: None})
    org += _changes_from_snapshots(out[HEAD], conf.get("현재 연도"))
    old_org = _legacy(xl, "조직변경")
    if len(old_org):
        notes.append(f"예전 조직변경 {len(old_org)}줄(라인·그룹 신설, 이름 변경 등)은 새 변경 유형에 없어서 옮기지 않았어요. "
                     "파트 신설·폐지는 인원 스냅샷에서 만들었어요.")
    if not _legacy(xl, "후보풀").empty:
        notes.append("후보풀은 없어졌어요 (묶음은 조직변경의 파트 묶음 계획대로만 반영해요).")
    out[ORG] = _clean(ORG, pd.DataFrame(org, columns=SHEETS[ORG]))
    return out


def _changes_from_snapshots(parts: pd.DataFrame, cur: int | None) -> list[dict]:
    """인원 스냅샷에서 파트 신설·폐지 행을 만들어요 (예전 양식 변환용)."""
    ys = sorted(int(y) for y in parts["연도"].dropna().unique())
    rows, prev = [], None
    for y in ys:
        now = parts[parts["연도"] == y].set_index("파트")
        if prev is not None:
            kind = "실적" if cur is not None and y <= cur else "계획"
            for n in now.index.difference(prev.index):
                rows.append({"연도": y, "구분": kind, "변경 유형": "파트 신설", "대상 파트": n, RESULT: now.loc[n, "그룹"], NOTE: None})
            for n in prev.index.difference(now.index):
                rows.append({"연도": y, "구분": kind, "변경 유형": "파트 폐지", "대상 파트": n, RESULT: None, NOTE: None})
        prev = now
    return rows


# ---------------------------------------------------------------- 연도 스냅샷
def snapshot_years(ds: Dataset, name: str = HEAD) -> list[int]:
    return sorted(int(y) for y in ds.t(name)["연도"].dropna().unique())


def add_year(ds: Dataset, year: int, name: str = HEAD) -> dict[str, pd.DataFrame]:
    """새 연도 스냅샷: 직전 연도(없으면 가장 가까운 다음 연도)를 복사해요. 바뀐 표만 돌려줘요.
    - 인원: (변동)은 0, 비고는 비워요.
    - 파트별 업무·실적: (입력) 빈도·단위·건당 시간만 복사하고 파트 목표·실측·보고 실적·비고는 비워요.
    - 두 시트 모두: 업무구분에 그 연도 목표 열이 없으면 직전 연도 값으로 만들어요."""
    t = ds.t(name)
    years = snapshot_years(ds, name)
    if year in years:
        raise ValueError(f"{year}년 스냅샷이 이미 있어요")
    if not years:
        raise ValueError("복사할 스냅샷이 없어요")
    before = [y for y in years if y < year]
    src = before[-1] if before else years[0]
    new = t[t["연도"] == src].copy()
    new["연도"] = year
    if name == HEAD:
        for c in CHANGE_COLS:
            new[c] = 0
        new["비고"] = None
    else:
        for c in (TGT, M_FREQ, M_MIN, IN_AX):
            new[c] = float("nan")
        new["비고"] = None
        if year > years_in_use(ds)[1]:              # 미래 연도: (입력) 빈도는 비우고 (회귀) 빈도로 예측
            new[IN_FREQ] = float("nan")
    out = {name: pd.concat([t, new], ignore_index=True).sort_values("연도", kind="stable").reset_index(drop=True)}
    if name == WORK:
        tmp = ds.copy()
        tmp.tables[WORK] = out[WORK]
        out[WORK] = regress_freq(tmp)
    tc = ds.t(DICT)
    col = f"{year} 목표"
    if col not in tc.columns and not tc.empty:
        tc = tc.copy()
        prev = [c for c in year_cols(tc) if int(c[:4]) < year]
        tc[col] = tc[prev[-1]] if prev else 0.0
        out[DICT] = tc[SHEETS[DICT] + year_cols(tc)]
    return out


def drop_year(ds: Dataset, year: int, name: str = HEAD) -> pd.DataFrame:
    t = ds.t(name)
    return t[t["연도"] != year].reset_index(drop=True)


def add_target_year(ds: Dataset, year: int, copy: bool = True) -> pd.DataFrame:
    """업무구분에 '{year} 목표' 열을 더해요. copy=True면 직전 연도(없으면 가장 가까운 다음 연도) 목표를 복사, 아니면 빈칸."""
    t = ds.t(DICT).copy()
    col = f"{year} 목표"
    if col in t.columns:
        raise ValueError(f"'{col}' 열이 이미 있어요")
    ys = [int(c[:4]) for c in year_cols(t)]
    src = max([y for y in ys if y < year], default=min(ys) if ys else None)
    t[col] = t[f"{src} 목표"] if copy and src is not None else float("nan")
    return t[SHEETS[DICT] + year_cols(t)]


def drop_target_year(ds: Dataset, year: int) -> tuple[pd.DataFrame | None, str]:
    """업무구분에서 '{year} 목표' 열을 지워요. 파트별 업무·실적에 그 연도 파트 목표가 있으면 지우지 않아요: (표, 막은 사유)."""
    t = ds.t(DICT)
    col = f"{year} 목표"
    if col not in t.columns:
        return None, f"'{col}' 열이 없어요"
    w = ds.t(WORK)
    used = w[(pd.to_numeric(w["연도"], errors="coerce") == year) & w[TGT].notna()]
    if len(used):
        return None, (f"파트별 업무·실적에 {year}년 파트 목표가 {len(used)}줄 있어요 "
                      f"(예: {used.iloc[0]['파트']} · {used.iloc[0]['코드']}). 먼저 그 줄의 파트 목표를 비워요.")
    return t.drop(columns=[col]), ""


def late_plans(ds: Dataset) -> pd.Series:
    """현재 연도 이하인데 아직 '계획'인 조직변경 행 (True/False)"""
    t = ds.t(ORG)
    cur = years_in_use(ds)[1]
    if t.empty:
        return pd.Series(False, index=t.index)
    return (t["구분"] == "계획") & (pd.to_numeric(t["연도"], errors="coerce") <= cur)


# ---------------------------------------------------------------- 검사
def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip()) or v is pd.NA


def _label(name: str, r) -> str:
    if name in YEARLY:
        bits = [_fmt(r.get("연도")), r.get("파트"), r.get("코드") if name == WORK else None]
        return f" ({' · '.join(str(b) for b in bits if not _blank(b))})" if not _blank(r.get("파트")) else ""
    if name == ORG:
        bits = [_fmt(r.get("연도")), r.get("변경 유형"), r.get("대상 파트")]
        return f" ({' · '.join(str(b) for b in bits if not _blank(b))})" if not _blank(r.get("대상 파트")) else ""
    k = KEY_COL[name]
    return f" ({r.get(k)})" if not _blank(r.get(k)) else ""


def _fmt(v):
    try:
        return f"{int(v)}"
    except (TypeError, ValueError):
        return str(v)


def _snap_at(parts: pd.DataFrame, year: int) -> pd.DataFrame:
    """그해 쓰는 인원 스냅샷 (그해 것이 없으면 직전 연도, 그보다 앞이면 첫 스냅샷). 파트 이름이 인덱스예요."""
    ys = sorted(int(y) for y in parts["연도"].dropna().unique())
    if not ys:
        return parts.iloc[0:0].set_index("파트")
    before = [y for y in ys if y <= year]
    sy = before[-1] if before else ys[0]
    return parts[parts["연도"] == sy].drop_duplicates("파트").set_index("파트")


def _prev_snap(parts: pd.DataFrame, year: int) -> pd.DataFrame | None:
    ys = sorted(int(y) for y in parts["연도"].dropna().unique() if int(y) < year)
    return _snap_at(parts, ys[-1]) if ys else None


def org_problems(org: pd.DataFrame, parts: pd.DataFrame) -> list[tuple[int, str]]:
    """조직변경 행마다 인원 스냅샷과 맞는지 (행 번호 0부터, 사유). 결과 칸 규칙과 묶음 직군도 봐요."""
    out = []
    org = org.reset_index(drop=True)
    for i, r in org.iterrows():
        t, part, res = r.get("변경 유형"), r.get("대상 파트"), r.get(RESULT)
        try:
            y = int(r.get("연도"))
        except (TypeError, ValueError):
            continue
        if _blank(part) or t not in ORG_TYPES:
            continue
        now, prev = _snap_at(parts, y), _prev_snap(parts, y)
        groups = set(now["그룹"].dropna().astype(str))
        if t != "파트 폐지" and _blank(res):
            out.append((i, f"{RESULT}이(가) 비어 있어요 — {ORG_HINTS[t]}"))
            continue
        if t == "파트 폐지":
            if not _blank(res):
                out.append((i, f"파트 폐지에는 {RESULT}을(를) 비워요 ('{res}')"))
            if part in now.index:
                out.append((i, f"{y}년 인원 스냅샷에 '{part}'가 아직 있어요 (폐지하면 그해 스냅샷에서 빼요)"))
            elif prev is None or part not in prev.index:
                out.append((i, f"{y}년 전에 운영하던 파트가 아니에요 ('{part}')"))
        elif t == "파트 신설":
            if str(res) not in groups:
                out.append((i, f"{y}년 인원 스냅샷에 없는 그룹이에요 ('{res}')"))
            if part not in now.index:
                out.append((i, f"{y}년 인원 스냅샷에 신설 파트 '{part}'가 없어요"))
            elif str(now.loc[part, "그룹"]) != str(res):
                out.append((i, f"'{part}'의 {y}년 그룹은 '{now.loc[part, '그룹']}'예요 ('{res}'와 달라요)"))
            if prev is not None and part in prev.index:
                out.append((i, f"'{part}'는 {y}년 전에도 있던 파트예요"))
        elif t == "파트 병합":
            if str(res) == str(part):
                out.append((i, "병합 대상과 존속 파트가 같아요"))
            elif str(res) not in now.index:
                out.append((i, f"존속 파트 '{res}'가 {y}년 인원 스냅샷에 없어요"))
            if part in now.index:
                out.append((i, f"{y}년 인원 스냅샷에 병합된 '{part}'가 아직 있어요 (그해 스냅샷에서 빼요)"))
        elif t == "그룹 이동":
            if str(res) not in groups:
                out.append((i, f"{y}년 인원 스냅샷에 없는 그룹이에요 ('{res}')"))
            elif part in now.index and str(now.loc[part, "그룹"]) != str(res):
                out.append((i, f"'{part}'의 {y}년 그룹은 '{now.loc[part, '그룹']}'예요 ('{res}'와 달라요)"))
            if part not in now.index:
                out.append((i, f"{y}년 인원 스냅샷에 '{part}'가 없어요"))
        elif t == "파트 묶음":
            if part not in set(parts["파트"].dropna()):
                out.append((i, f"인원 시트에 없는 파트예요 ('{part}')"))
    # 묶음: 같은 묶음은 같은 직군, 한 파트는 묶음 하나에만
    b = org[(org["변경 유형"] == "파트 묶음") & org["대상 파트"].notna() & org[RESULT].notna()]
    job = parts.drop_duplicates("파트", keep="last").set_index("파트")["직군"]
    for name, g in b.groupby(RESULT, sort=False):
        jobs = {job.get(p) for p in g["대상 파트"] if p in job.index}
        if len(jobs) > 1:
            for i in g.index:
                out.append((i, f"묶음 '{name}'에 다른 직군이 섞여 있어요 ({' · '.join(sorted(map(str, jobs)))})"))
    for part, g in b.groupby("대상 파트", sort=False):
        if g[RESULT].nunique() > 1:
            for i in g.index:
                out.append((i, f"'{part}'가 묶음 여러 개({', '.join(g[RESULT].unique())})에 들어 있어요 (한 파트는 묶음 하나)"))
    return sorted(out)


def check_table(name: str, df: pd.DataFrame, ds: Dataset, hidden: pd.DataFrame | None = None) -> tuple[list[str], list[str]]:
    """저장 전 검사: (오류, 경고). 오류가 하나라도 있으면 저장하지 않아요.
    행 번호는 화면 표의 행 번호(1부터)예요. df는 그 시트 전체(연도별 시트는 화면에 보이는 연도분만 넘겨도 돼요).
    hidden = 화면 필터 밖이지만 함께 저장되는 같은 시트의 줄 (키 중복만 같이 봐요)."""
    errs: list[str] = []
    warns: list[str] = []
    df = df.drop(columns=[c for c in derived_cols(name) if c in df.columns]).reset_index(drop=True)
    others = ds.t(name)
    if name in YEARLY and "연도" in df.columns and not df.empty:
        shown = set(pd.to_numeric(df["연도"], errors="coerce").dropna().astype(int))
        others = others[~others["연도"].isin(shown)]
    all_parts = pd.concat([others, df], ignore_index=True) if name == HEAD else ds.t(HEAD)
    part_names = {str(x) for x in all_parts["파트"].dropna()}
    codes = {str(x) for x in (df if name == DICT else ds.t(DICT))["코드"].dropna()}
    req, nums, rates = REQUIRED_COLS.get(name, []), num_cols(name, df), rate_cols(name, df)
    ints = INT_COLS.get(name, [])

    for i, r in df.iterrows():
        row, lab, bad = i + 1, _label(name, r), []
        miss = [c for c in req if c in df.columns and _blank(r.get(c))]
        if miss:
            bad.append(f"{' · '.join(miss)}이(가) 비어 있어요")
        for c in nums:
            v = r.get(c)
            if c in miss or _blank(v):
                continue
            x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
            if pd.isna(x):
                bad.append(f"{c}에 숫자가 아닌 값('{v}')이 있어요"); continue
            if x < 0:
                bad.append(f"{c}는 0 이상이어야 해요 ({x:g})")
            elif c in rates and x > 1:
                bad.append(f"{c}는 0~1(0~100%) 사이여야 해요 ({x:g})")
            elif c in ints and x != int(x):
                bad.append(f"{c}는 정수여야 해요 ({x:g})")
            elif "연도" in c and not 1900 <= x <= 2200:
                bad.append(f"{c}가 연도가 아니에요 ({x:g})")
        for (sh, c), opts in CHOICES.items():
            if sh == name and c in df.columns and not _blank(r.get(c)) and r.get(c) not in opts:
                bad.append(f"{c}는 {' / '.join(opts)} 중 하나여야 해요 ('{r.get(c)}')")
        if name in CODE_REF_SHEETS and not _blank(r.get("코드")) and str(r.get("코드")) not in codes:
            bad.append(f"업무구분에 없는 코드예요 ('{r.get('코드')}')")
        if name in PART_REF_SHEETS and not _blank(r.get("파트")) and str(r.get("파트")) not in part_names:
            bad.append(f"인원 시트에 없는 파트예요 ('{r.get('파트')}')")
        if name == WORK and _blank(r.get(IN_FREQ)) and _blank(r.get(REG_FREQ)):
            bad.append(f"{IN_FREQ}이(가) 비어 있어요 (미래 연도는 설정 [적용]으로 {REG_FREQ}을(를) 채울 수 있어요)")
        if name == WORK and not _blank(r.get(M_MIN)):
            base = pd.to_numeric(pd.Series([r.get(IN_MIN)]), errors="coerce").iloc[0]
            if pd.isna(base) or base <= 0:
                bad.append(f"{M_MIN}을(를) 넣으려면 {IN_MIN}이(가) 0보다 커야 해요")
        if name == HEAD:
            n = lambda c: pd.to_numeric(pd.Series([r.get(c)]), errors="coerce").fillna(0).iloc[0]
            if sum(n(f"배치 {s}") for s in SLOTS) > 0:
                tot = sum(n(f"교대 배분 {s}") for s in SLOTS)
                if abs(tot - 1) > 0.005:
                    bad.append(f"교대 배분 DAY+SWING+GY 합이 100%가 아니에요 ({tot:.0%})")
            low = [s for s in SLOTS if n(f"배치 {s}") < n(f"최소 {s}")]
            if low:
                bad.append(f"배치가 최소 인원보다 적어요 ({', '.join(low)})")
            ref = r.get("참고 파트")
            if not _blank(ref) and str(ref) not in part_names:
                bad.append(f"참고 파트 '{ref}'가 인원 시트에 없어요")
        errs += [f"{row}행{lab}: {b}" for b in bad]

    # 중복 키
    keys = [k for k in KEYS.get(name, []) if k in df.columns]
    if keys:
        sub = df[keys].astype(str)
        full = df[keys].notna().all(axis=1)
        dup = sub[full & sub.duplicated(keep=False)]
        for _, g in dup.groupby(keys, sort=False):
            rows = ", ".join(str(i + 1) for i in g.index)
            errs.append(f"{rows}행: 같은 {' + '.join(keys)}가 중복돼요 ({' · '.join(g.iloc[0])})")
        if hidden is not None and len(hidden):
            out_keys = set(map(tuple, hidden[keys].astype(str).to_numpy()))
            for i, k in enumerate(map(tuple, sub.to_numpy())):
                if full.iloc[i] and k in out_keys:
                    errs.append(f"{i + 1}행: 같은 {' + '.join(keys)}가 필터 밖 줄에 이미 있어요 ({' · '.join(k)})")
    if name == HEAD and "파트 ID" in df.columns:
        d = df[df["파트 ID"].notna() & df["연도"].notna()]
        for _, g in d[d.duplicated(["연도", "파트 ID"], keep=False)].groupby(["연도", "파트 ID"]):
            errs.append(f"{', '.join(str(i + 1) for i in g.index)}행: 같은 연도에 파트 ID가 중복돼요 ({g.iloc[0]['파트 ID']})")

    # 조직변경: 결과 칸 규칙 + 인원 스냅샷과 맞는지
    if name == ORG:
        lab = {i: _label(ORG, r) for i, r in df.iterrows()}
        errs += [f"{i + 1}행{lab[i]}: {msg}" for i, msg in org_problems(df, ds.t(HEAD))]
        late = int(((df["구분"] == "계획") & (pd.to_numeric(df["연도"], errors="coerce") <= years_in_use(ds)[1])).sum())
        if late:
            warns.append(f"현재 연도 이하인데 '계획'인 행이 {late}줄 있어요 ({LATE}) — 실제로 반영됐으면 '실적'으로 바꿔요")

    # 다른 시트와의 연결
    if name == DICT:
        used = set()
        for sh in CODE_REF_SHEETS:
            used |= {str(x) for x in ds.t(sh)["코드"].dropna()}
        gone = sorted(used - codes)
        if gone:
            errs.append(f"다른 시트(파트별 업무·실적)에서 쓰는 코드를 지웠어요: {', '.join(gone[:8])}{' …' if len(gone) > 8 else ''}")
    if name == HEAD:
        used = set()
        for sh in PART_REF_SHEETS:
            used |= {str(x) for x in ds.t(sh)["파트"].dropna()}
        used |= {str(x) for x in ds.t(ORG)["대상 파트"].dropna()}
        gone = sorted(used - part_names)
        if gone:
            warns.append(f"모든 연도에서 빠진 파트를 다른 시트가 쓰고 있어요: {', '.join(gone[:8])}")
        warns += _headcount_warnings(df, others)
        if not errs:
            warns += _slot_warnings(df, others, ds)
        org = ds.t(ORG)
        if not org.empty:
            probs = org_problems(org, all_parts)
            if probs:
                warns.append(f"조직변경 시트와 안 맞는 줄이 {len(probs)}건 있어요 — 예: {probs[0][0] + 1}행 {probs[0][1]}")
    return errs, warns


def _headcount_warnings(df: pd.DataFrame, others: pd.DataFrame) -> list[str]:
    """총원 = 직전 연도 총원 + 신입 + 전입 − 전출 − 퇴직 이 맞지 않으면 경고 (저장은 막지 않아요)."""
    allp = pd.concat([others, df], ignore_index=True)
    allp = allp[allp["연도"].notna() & allp["파트"].notna()]
    years = sorted(int(y) for y in allp["연도"].unique())
    if len(years) < 2:
        return []
    out = []
    for i, r in df.reset_index(drop=True).iterrows():
        try:
            y = int(r["연도"])
        except (TypeError, ValueError):
            continue
        prev_years = [p for p in years if p < y]
        if not prev_years or _blank(r.get("총원")):
            continue
        prev = allp[(allp["연도"] == prev_years[-1]) & (allp["파트"] == r["파트"])]
        base = float(prev["총원"].iloc[0]) if len(prev) and pd.notna(prev["총원"].iloc[0]) else 0.0
        ch = [pd.to_numeric(pd.Series([r.get(c)]), errors="coerce").fillna(0).iloc[0] for c in CHANGE_COLS]
        expect = base + ch[0] + ch[1] - ch[2] - ch[3]
        if abs(expect - float(r["총원"])) > 0.01:
            out.append(f"{i + 1}행 ({y} · {r['파트']}): 총원 {float(r['총원']):g}명 ≠ {prev_years[-1]}년 {base:g}명 + 변동 "
                       f"{expect - base:+g}명 = {expect:g}명")
    return out


def _slot_warnings(df: pd.DataFrame, others: pd.DataFrame, ds: Dataset) -> list[str]:
    """배치 자리를 채우는 데 드는 인원(자리 × 8h × 365 ÷ 1인 가용)이 총원보다 많으면 경고 (저장은 막지 않아요).
    그러면 교대·오피스로 나눈 FTE 확보가 틀어져요(오피스가 음수에서 시작). 파트·팀 전체 FTE 확보는 그대로예요."""
    from .engine import SHIFT_DAYS, SHIFT_HOURS, Model, build_profile
    tmp = ds.copy()
    tmp.tables[HEAD] = pd.concat([others, df], ignore_index=True)
    m = Model(tmp)
    out = []
    for i, r in df.reset_index(drop=True).iterrows():
        try:
            y, name = int(r["연도"]), r["파트"]
        except (TypeError, ValueError):
            continue
        part = m.snap.get(y, {}).get(name)
        if part is None or part.office_only:
            continue
        seats = sum(part.slots.values())
        fte = seats * SHIFT_HOURS * SHIFT_DAYS / build_profile(m, part, y, "none", None).person_avail
        if fte > part.head + 0.05:
            slots = "/".join(f"{part.slots[s]:g}" for s in SLOTS)
            out.append(f"{i + 1}행 ({y} · {name}): 배치 {slots} = {seats:g}자리를 채우려면 약 {fte:.1f}명이 필요한데 총원이 "
                       f"{part.head:g}명이에요 (교대·오피스로 나눈 FTE 확보가 틀어져요)")
    return out


def validate(ds: Dataset) -> dict[str, list[str]]:
    """가져온 데이터 전체 검사(경고 배너용): 시트별 메시지 목록. 문제가 없으면 빈 목록."""
    msg: dict[str, list[str]] = {n: [] for n in SHEETS}
    msg["설정"] = []
    for n in REQUIRED_SHEETS:
        if ds.t(n).empty:
            msg[n].append("데이터가 없어요 (필수 시트)")
    for n in EDIT_SHEETS:
        if ds.t(n).empty:
            if n not in REQUIRED_SHEETS:
                msg[n].append("비어 있어요")
            continue
        errs, _ = check_table(n, ds.t(n), ds)
        if errs:
            msg[n].append(f"오류 {len(errs)}건 — {errs[0]}{' 외' if len(errs) > 1 else ''}")
    snaps = snapshot_years(ds)
    por = settings(ds).get("POR 연도")
    if snaps and por is not None and por not in snaps:
        msg["설정"].append(f"POR 연도{f' {por}' if por else ''}의 인원 스냅샷이 없어서 {snaps[0]}년을 POR로 써요")
    n_late = int(late_plans(ds).sum())
    if n_late:
        msg[ORG].append(f"{LATE} {n_late}줄 — 현재 연도 이하인데 아직 '계획'이에요")
    return msg
