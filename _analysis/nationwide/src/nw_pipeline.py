#!/usr/bin/env python3
"""
전국 확장 분석 파이프라인 (다문화가정 아동 교육지원 수요·공급 불균형)

단계(각 단계는 runs/<run_id>/ 아래에 결과를 쓰고 status 에 기록):
  N0 gate     기존(유성구) 분석 완료·무결성 검증
  N1 audit    bigdata/ 원자료 인벤토리, 전국 공급자료 5종 자동 식별·스키마/결측 조사
  N2 regions  SGIS 시군구 경계 → 기초지자체 단위(일반구는 시로 통합), 2024 인구
  N3 demand   외국인주민 현황(2025.11.1.) 시군구·읍면동 다문화가구 자녀, 외국인주민 자녀 연령
  N4 supply   공급자료(있는 것만) 적재 → 좌표/주소로 기초지자체 배정, 가족센터 프로그램 분류
  N5 compare  시군구별 수요·공급 비교표(공급 유형별 분리, 합산 지표 없음)
  N6 select   사전 고정 규칙(config)으로 대표지역 선정 (+유성구)
  N7 access   대표지역 행정동 수요 × 시설 좌표로 접근성·MCLP (조건 충족 지역만)
  N8 figures  지도·그래프
  N9 report   data_audit.md, final_report.md 등

입력 원본은 읽기만 한다. GPU 사용 안 함.
"""
import argparse, datetime as dt, hashlib, json, logging, math, os, re, shutil, sys, time, traceback, zipfile
from pathlib import Path

NW = Path(__file__).resolve().parents[1]
CFG = json.loads((NW / "config" / "config.json").read_text(encoding="utf-8"))
ROOT = (NW / CFG["bigdata_root"]).resolve()   # config 기준 상대경로
AN = Path(CFG.get("analysis_dir", str(ROOT / "_analysis")))
SGIS_DIR = AN / "work" / "sgis"          # 이전 분석에서 zip 에서 추출한 경계·통계(읽기 전용으로 재사용)
KST = dt.timezone(dt.timedelta(hours=9))
STATUS = NW / "status"; LOGD = NW / "logs"
for d in (STATUS, LOGD, NW / "runs", NW / "reports"):
    d.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("nw")
if not log.handlers:
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOGD / "execution.log", encoding="utf-8"); fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fh.formatter)
    log.addHandler(fh); log.addHandler(sh)

SIDO = {"11": "서울특별시", "21": "부산광역시", "22": "대구광역시", "23": "인천광역시", "24": "광주광역시", "25": "대전광역시", "26": "울산광역시",
        "29": "세종특별자치시", "31": "경기도", "32": "강원특별자치도", "33": "충청북도", "34": "충청남도", "35": "전북특별자치도", "36": "전라남도",
        "37": "경상북도", "38": "경상남도", "39": "제주특별자치도"}
SIDO_ALIAS = {"서울": "11", "부산": "21", "대구": "22", "인천": "23", "광주": "24", "대전": "25", "울산": "26", "세종": "29", "경기": "31", "강원": "32",
              "충북": "33", "충청북": "33", "충남": "34", "충청남": "34", "전북": "35", "전라북": "35", "전남": "36", "전라남": "36", "경북": "37", "경상북": "37",
              "경남": "38", "경상남": "38", "제주": "39"}
SW_NAMES = {"서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "강원도",
            "충청북도", "충청남도", "전북특별자치도", "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"}

SOURCE_TYPOS = {"부천기오정구": "부천시오정구", "청순군": "청송군"}   # 원자료 표기 오류(보정 사실을 보고서에 기록)

def now():
    return dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

def jdump(o, p):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(o, ensure_ascii=False, indent=2, default=str), encoding="utf-8"); tmp.replace(p)

def jload(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def sido_code_from_text(t):
    t = str(t or "").strip()
    for full, code in [(v, k) for k, v in SIDO.items()] + [("강원도", "32"), ("전라북도", "35")]:
        if t.startswith(full):
            return code
    for a, code in SIDO_ALIAS.items():
        if t.startswith(a):
            return code
    return None

# ====================================================================== 상태 파일
def status_update(**kw):
    st = jload(STATUS / "execution_status.json", {}) or {}
    st.update(kw); st["last_update"] = now()
    jdump(st, STATUS / "execution_status.json")
    _progress(st)
    return st

def _progress(st):
    L = ["# 전국 분석 진행 현황 (analysis_progress.md)", "", f"- 갱신: {st.get('last_update')}",
         f"- 기존(유성구) 분석 상태: {st.get('previous_job_status')}", f"- 전국 분석 코드: {st.get('code_ready')}",
         f"- 자동 대기 시스템: {st.get('watcher_status')}", f"- 전국 분석 시작 여부: {st.get('nationwide_started')}",
         f"- 최근 실행 ID: {st.get('current_run_id')}", f"- 현재 단계: {st.get('current_step')}", f"- 오류 여부: {st.get('error')}", "",
         "| 단계 | 상태 | 시작 | 종료 | 비고 |", "|---|---|---|---|---|"]
    for k, v in (st.get("steps") or {}).items():
        L.append(f"| {k} | {v.get('state')} | {v.get('start','')} | {v.get('end','')} | {str(v.get('note') or v.get('error') or '').replace('|','/')[:200]} |")
    (NW / "reports").mkdir(exist_ok=True)
    (NW / "reports" / "analysis_progress.md").write_text("\n".join(L) + "\n", encoding="utf-8")

# ====================================================================== N0 기존 작업 검증
def check_previous_job():
    pj = CFG["previous_job"]; res = {"checked_at": now(), "checks": {}}
    st = jload(pj["status_file"], {}) or {}
    steps = st.get("steps", {})
    res["checks"]["status_overall"] = st.get("overall")
    res["checks"]["all_required_steps_done"] = all(steps.get(s, {}).get("state") == "완료" for s in pj["required_steps"])
    res["checks"]["done_flag_exists"] = Path(pj["done_flag"]).exists()
    pid = None
    try:
        pid = int(Path(pj["pid_file"]).read_text().strip())
    except Exception:
        pass
    alive = False
    if pid:
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="ignore")
            alive = "supervisor.sh" in cmd and Path(f"/proc/{pid}").stat().st_uid == os.getuid()
        except FileNotFoundError:
            alive = False
    # 우리 프로젝트(이 경로)의 pipeline.py 가 실행 중인지: 내 UID + cmdline 경로로만 판정
    running = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != os.getuid():
                continue
            cmd = (p / "cmdline").read_bytes().decode(errors="ignore").replace("\x00", " ")
            cwd = os.readlink(p / "cwd") if (p / "cwd").exists() else ""
        except Exception:
            continue
        if int(p.name) == os.getpid() or "nw_pipeline" in cmd or "nw_daemon" in cmd or cwd.startswith(str(NW)):
            continue
        if re.search(r"(^|/|\s)scripts/pipeline\.py", cmd) and (cwd.startswith(str(AN)) or str(AN) in cmd):
            running.append({"pid": int(p.name), "cmd": cmd[:200]})
    res["checks"]["supervisor_pid"] = pid; res["checks"]["supervisor_alive"] = alive; res["checks"]["project_pipeline_processes"] = running
    missing = [o for o in pj["required_outputs"] if not (AN / o).exists() or (AN / o).stat().st_size == 0]
    res["checks"]["missing_or_empty_outputs"] = missing
    fails = None
    if Path(pj["validation_file"]).exists():
        import csv
        with open(pj["validation_file"], encoding="utf-8-sig") as f:
            fails = sum(1 for r in csv.DictReader(f) if r["result"] != "PASS")
    res["checks"]["validation_fail_count"] = fails
    if alive or running:
        res["state"] = "실행중"
    elif st.get("overall") == "완료" and res["checks"]["all_required_steps_done"] and res["checks"]["done_flag_exists"] and not missing and fails == 0:
        res["state"] = "정상완료"
    elif st.get("overall") and st.get("overall") != "완료":
        res["state"] = "실패또는부분완료"
    else:
        res["state"] = "판정불가"
    jdump(res, STATUS / "previous_job_check.json")
    return res

# ====================================================================== 공통 로더
def _norm(s):
    return re.sub(r"[\s_()\[\]·.\-/]", "", str(s or "")).lower()

def read_table(path, member=None):
    """CSV/XLSX(또는 zip 안의 파일) → DataFrame 목록 [(label, df)]"""
    import pandas as pd, io
    out = []
    def _csv(b, label):
        for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-16"):
            try:
                df = pd.read_csv(io.BytesIO(b), encoding=enc, dtype=str, low_memory=False)
                if df.shape[1] >= 2:
                    out.append((label, df, enc)); return
            except Exception:
                continue
        raise ValueError(f"CSV 인코딩 판별 실패: {label}")
    def _xlsx(b, label):
        x = pd.ExcelFile(io.BytesIO(b))
        for sn in x.sheet_names:
            raw = x.parse(sn, header=None, dtype=str)
            if raw.empty:
                continue
            # 헤더 행 자동 탐색: 비어있지 않은 셀이 가장 많은 상위 15행 중 첫 행
            cnt = raw.head(15).notna().sum(axis=1)
            h = int(cnt.idxmax()) if len(cnt) else 0
            df = x.parse(sn, header=h, dtype=str)
            out.append((f"{label}::{sn}", df, "xlsx"))
    p = Path(path)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if n.endswith("/"):
                    continue
                ext = Path(n).suffix.lower()
                if ext in (".csv", ".txt"):
                    _csv(z.read(n), f"{p.name}!{n}")
                elif ext in (".xlsx", ".xls"):
                    _xlsx(z.read(n), f"{p.name}!{n}")
    elif p.suffix.lower() in (".csv", ".txt"):
        _csv(p.read_bytes(), p.name)
    elif p.suffix.lower() in (".xlsx", ".xls"):
        _xlsx(p.read_bytes(), p.name)
    return out

ALIASES = {
    "name": ["시설명", "센터명", "도서관명", "학교명", "개방시설명", "개방장소명", "센터명", "기관명", "시설이름", "명칭"],
    "program": ["프로그램명", "프로그램이름", "사업명", "교육명", "강좌명"],
    "target": ["참여대상", "교육대상", "대상", "참가대상", "이용대상"],
    "desc": ["프로그램내용", "내용", "설명", "사업내용", "프로그램소개", "교육내용", "상세"],
    "category": ["프로그램분류", "분류", "사업분류", "구분", "영역", "유형"],
    "place": ["진행장소", "운영장소", "교육장소", "장소", "프로그램장소"],
    "org": ["센터정보", "운영기관명", "운영기관", "센터명", "기관명", "관리기관명"],
    "period": ["행사기간", "운영기간", "교육기간", "기간", "시작일", "운영시작일"],
    "capacity": ["정원", "수용가능인원", "수용인원", "모집인원", "인원"],
    "current": ["현원", "이용인원", "이용아동수"],
    "lat": ["위도", "lat", "latitude", "y좌표"],
    "lon": ["경도", "lon", "lng", "longitude", "x좌표"],
    "road": ["소재지도로명주소", "도로명주소", "주소", "소재지", "시설주소"],
    "jibun": ["소재지지번주소", "지번주소"],
    "sido": ["시도명", "시도"],
    "sgg": ["시군구명", "시군구"],
    "level": ["학교급구분", "학교급"],
    "status": ["운영상태", "운영여부", "개방여부", "폐교여부", "상태"],
    "ftype": ["도서관유형", "시설유형", "개방시설유형구분", "시설구분", "시설종류"],
    "hours": ["평일운영시작시각", "운영시간", "평일운영시간", "이용시간"],
    "refdate": ["데이터기준일자", "기준일자", "기준일"],
    "provider": ["제공기관명"],
}

def find_col(df, key):
    cols = {_norm(c): c for c in df.columns}
    for a in ALIASES[key]:
        if _norm(a) in cols:
            return cols[_norm(a)]
    for a in ALIASES[key]:
        for nc, c in cols.items():
            if _norm(a) in nc:
                return c
    return None

def detect_type(fname, df_cols):
    n = _norm(fname); cols = " ".join(_norm(c) for c in df_cols)
    for pat in CFG["exclude_name_patterns"]:
        if _norm(pat) in n:
            return None
    kw = CFG["dataset_keywords"]
    if "학교급" in cols or any(_norm(k) in n for k in kw["school"]):
        return "school"
    if "프로그램명" in cols or ("프로그램" in n and any(_norm(k) in n for k in kw["family_program"])):
        return "family_program"
    if "도서관명" in cols or "도서관유형" in cols or any(_norm(k) in n for k in kw["library"]):
        return "library"
    if "개방시설" in cols or "개방장소" in cols or any(_norm(k) in n for k in kw["open_facility"]):
        return "open_facility"
    if any(_norm(k) in n for k in kw["childcenter_nat"]) or "지역아동센터" in cols:
        return "childcenter_nat"
    if any(_norm(k) in n for k in kw["family_program"]):
        return "family_program"
    return None

# ====================================================================== N1 audit
def candidate_files():
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or "_analysis" in p.relative_to(ROOT).parts:
            continue
        out.append(p)
    return out

def n1_audit(run):
    import pandas as pd
    reg = {"audited_at": now(), "files": []}
    for p in candidate_files():
        st = p.stat()
        rec = dict(path=str(p.relative_to(ROOT)), size=st.st_size, sha256=sha256(p), ext=p.suffix.lower(),
                   fs_mtime=dt.datetime.fromtimestamp(st.st_mtime, KST).strftime("%Y-%m-%d %H:%M"), dataset_type=None, tables=[])
        if p.suffix.lower() in (".csv", ".txt", ".xlsx", ".xls") or (p.suffix.lower() == ".zip" and "SGIS" not in p.name):
            if "외국인주민" in p.name:
                rec["dataset_type"] = "foreign_stats"
            else:
                try:
                    for label, df, enc in read_table(p):
                        t = detect_type(p.name + " " + label, df.columns)
                        info = dict(label=label, encoding=enc, rows=int(len(df)), cols=[str(c) for c in df.columns][:60], type=t,
                                    missing_rate={str(c): round(float(df[c].isna().mean() if c in df else 1), 3) for c in df.columns[:60]},
                                    dup_rows=int(df.duplicated().sum()))
                        for k in ("lat", "lon", "road", "sgg", "refdate", "name", "program", "capacity", "current", "status"):
                            info[f"col_{k}"] = find_col(df, k)
                        rc = info["col_refdate"]
                        if rc:
                            vc = df[rc].dropna().astype(str).str[:10].value_counts().head(5)
                            info["refdate_values"] = vc.to_dict()
                        info["has_region_code"] = any(re.search(r"(행정|법정|시군구|지역)코드|adm_cd|sgg_cd", str(c), re.I) for c in df.columns)
                        info["has_coords"] = bool(info["col_lat"] and info["col_lon"])
                        rec["tables"].append(info)
                        rec["dataset_type"] = rec["dataset_type"] or t
                except Exception as e:
                    rec["error"] = f"{type(e).__name__}: {e}"
        elif "SGIS" in p.name:
            rec["dataset_type"] = "sgis"
        reg["files"].append(rec)
    types = {}
    for f in reg["files"]:
        if f["dataset_type"]:
            types.setdefault(f["dataset_type"], []).append(f["path"])
    reg["found_types"] = types
    reg["missing_supply_types"] = [t for t in ["family_program", "childcenter_nat", "school", "library", "open_facility"] if t not in types]
    jdump(reg, run / "results" / "dataset_registry.json")
    return f"파일 {len(reg['files'])}개; 식별 {sorted(types)}; 미확보 공급자료 {reg['missing_supply_types']}"

# ====================================================================== N2 regions
def n2_regions(run):
    import geopandas as gpd, pandas as pd, pyogrio
    g = pyogrio.read_dataframe(SGIS_DIR / "bnd_sigungu_00_2025_2Q.shp").to_crs(5179)
    g["sido_cd"] = g.SIGUNGU_CD.str[:2]; g["sido_nm"] = g.sido_cd.map(SIDO)
    g["base_nm"] = g.SIGUNGU_NM.str.split(" ").str[0]               # '수원시 장안구' → '수원시'
    g["key"] = g.sido_cd + "|" + g.base_nm
    # 인구(2024)
    def rd(name):
        f = [p for p in SGIS_DIR.iterdir() if p.name.endswith(name)][0]
        return pd.read_csv(f, encoding="cp949", dtype={"행정구역코드": str})
    pop = rd("인구총괄(총인구).csv"); age = rd("성연령별인구.csv")
    def pick(df, item):
        s = df[(df.행정구역코드.str.len() == 5) & (df.통계항목 == item)][["행정구역코드", "통계값"]]
        return s.assign(통계값=pd.to_numeric(s.통계값, errors="coerce")).set_index("행정구역코드").통계값
    P = pd.DataFrame({"pop_total_2024": pick(pop, "to_in_001"), "age0_4": pick(age, "in_age_001"), "age5_9": pick(age, "in_age_002"),
                      "age10_14": pick(age, "in_age_003"), "age15_19": pick(age, "in_age_004")})
    g = g.merge(P, left_on="SIGUNGU_CD", right_index=True, how="left")
    gm = g[["SIGUNGU_CD", "SIGUNGU_NM", "key", "sido_cd"]].copy(); gm.to_csv(run / "data_processed" / "sgis_sigungu_to_basic_unit.csv", index=False, encoding="utf-8-sig")
    u = g.dissolve(by="key", aggfunc={"sido_cd": "first", "sido_nm": "first", "base_nm": "first", "pop_total_2024": "sum", "age0_4": "sum", "age5_9": "sum", "age10_14": "sum", "age15_19": "sum", "SIGUNGU_CD": lambda s: ",".join(sorted(s))}).reset_index()
    u["n_general_gu"] = u.SIGUNGU_CD.str.count(",") + 1
    u["age0_19_2024"] = u[["age0_4", "age5_9", "age10_14", "age15_19"]].sum(axis=1)
    u["area_km2"] = u.area / 1e6
    u.to_file(run / "data_processed" / "basic_units.gpkg", driver="GPKG")
    u.drop(columns="geometry").to_csv(run / "data_processed" / "basic_units.csv", index=False, encoding="utf-8-sig")
    jdump({"n_sgis_sigungu": len(g), "n_basic_units": len(u), "n_with_general_gu": int((u.n_general_gu > 1).sum()),
           "pop_missing": int(u.pop_total_2024.isna().sum()), "pop_total": float(u.pop_total_2024.sum())}, run / "results" / "n2_regions.json")
    return f"SGIS 시군구 {len(g)}개 → 기초지자체 {len(u)}개(일반구 통합 {(u.n_general_gu>1).sum()}개 시)"

# ====================================================================== N3 demand
def _num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    v = str(v).strip().replace(",", "")
    if v == "*": return "*"
    try: return float(v)
    except ValueError: return None

def n3_demand(run):
    import openpyxl, pandas as pd, numpy as np
    fx = [p for p in ROOT.iterdir() if p.is_file() and "외국인주민현황_통계표" in p.name][0]
    wb = openpyxl.load_workbook(fx, read_only=True, data_only=True)
    def rows_of(prefix):
        n = [s for s in wb.sheetnames if s.strip().startswith(prefix)][0]
        return [list(r) for r in wb[n].iter_rows(values_only=True)]
    units = pd.read_csv(run / "data_processed" / "basic_units.csv", dtype=str)
    sgis_map = pd.read_csv(run / "data_processed" / "sgis_sigungu_to_basic_unit.csv", dtype=str)
    valid_keys = set(units.key)
    # --- 8-2: 시도/시군구/일반구 행 목록과 외국인주민 자녀
    r82 = rows_of("8-2.")
    recs = []; sido = None; last_city = None
    for r in r82:
        nm = str(r[0]).strip() if r[0] else ""; nm = SOURCE_TYPOS.get(nm, nm)
        if not nm or nm in ("구분", "전국") or r[1] is None or isinstance(r[1], str) and not re.match(r"^[\d,*]+$", str(r[1])):
            continue
        if nm in SW_NAMES:
            sido = sido_code_from_text(nm); last_city = None; continue
        is_gu = last_city is not None and nm.startswith(last_city) and len(nm) > len(last_city)
        if not is_gu:
            last_city = nm if nm.endswith("시") else None
        recs.append(dict(sido_cd=sido, name=nm, level="일반구" if is_gu else "기초", parent=last_city if is_gu else nm,
                         fr_child_total=_num(r[1]), fr_child_naturalized=_num(r[4]), fr_child_domestic=_num(r[7])))
    d82 = pd.DataFrame(recs)
    base = d82[d82.level == "기초"].copy()
    # 세종: 시트 표기 확인 후 키 정규화
    base["key"] = base.sido_cd + "|" + base.name.replace({"세종특별자치시": "세종시"})
    # 시트 이름 ↔ SGIS 기초단위 매칭
    unmatched = sorted(set(base.key) - valid_keys); sgis_only = sorted(valid_keys - set(base.key))
    # --- 11: 다문화가구원(시도·시군구·일반구·읍면동 혼재) → 8-2 목록 순서로 시군구 행 판정
    r11 = rows_of("11.")
    order = {}  # sido -> list of names in order (기초+일반구)
    for _, x in d82.iterrows():
        order.setdefault(x.sido_cd, []).append(x["name"])
    mc_rows = []; dong_rows = []; sido = None; cur_basic = None; cur_unit = None; remaining = {}
    lv = {(x.sido_cd, x["name"]): x for _, x in d82.iterrows()}
    for r in r11:
        nm = str(r[0]).strip() if r[0] else ""; nm = SOURCE_TYPOS.get(nm, nm)
        if not nm or nm in ("구분", "전국") or r[1] is None:
            continue
        if not re.match(r"^[\d,*.]+$", str(r[1])):
            continue
        if nm in SW_NAMES:
            sido = sido_code_from_text(nm); cur_basic = cur_unit = None
            remaining = {n: n for n in order.get(sido, [])}
            continue
        canon = remaining.get(nm)
        if canon is None and cur_basic:                     # 일반구가 짧은 이름으로 적힌 경우('완산구')
            full = cur_basic + nm
            if full in remaining and lv[(sido, full)].level == "일반구":
                canon = full
        if canon is not None:
            x = lv[(sido, canon)]
            remaining.pop(canon, None); cur_unit = canon
            if x.level == "기초":
                cur_basic = canon
            mc_rows.append(dict(sido_cd=sido, name=canon, level=x.level, mc_members=_num(r[1]), mc_children=_num(r[6]), mc_children_nat=_num(r[7]), mc_children_dom=_num(r[8]),
                                mc_marriage_nat=_num(r[3])))
        else:
            dong_rows.append(dict(sido_cd=sido, basic=cur_basic, unit=cur_unit, dong=nm, mc_children=_num(r[6]), mc_members=_num(r[1])))
    mc = pd.DataFrame(mc_rows); dg = pd.DataFrame(dong_rows)
    mcb = mc[mc.level == "기초"].copy(); mcb["key"] = mcb.sido_cd + "|" + mcb.name.replace({"세종특별자치시": "세종시"})
    # 세종처럼 읍면동이 시 바로 아래 오는 경우, 혹은 군 단위: 이미 처리됨
    # --- 9-2 연령(시군구 0~18세): 기초 단위만
    r92 = rows_of("9-2.")
    ages = []; sido = None; cur = None; seen = {}
    for r in r92:
        nm = str(r[0]).strip() if r[0] else ""; nm = SOURCE_TYPOS.get(nm, nm)
        if not nm or nm in ("구분",) or r[1] is None:
            continue
        if nm in SW_NAMES:
            sido = sido_code_from_text(nm); cur = None; continue
        if nm == "전국":
            cur = None; continue
        m = re.match(r"^(\d+)세$", nm)
        if m and cur:
            ages.append(dict(sido_cd=sido, name=cur, age=int(m.group(1)), n=_num(r[1])))
        elif not m:
            cur = nm
    ag = pd.DataFrame(ages)
    def band(df, lo, hi):
        s = df[(df.age >= lo) & (df.age <= hi)]
        v = pd.to_numeric(s.n, errors="coerce")
        return pd.Series({"sum_known": float(v.sum()), "n_blind": int((s.n == "*").sum())})
    if len(ag):
        agb = ag.groupby(["sido_cd", "name"]).apply(lambda d: pd.concat([band(d, 0, 6).add_prefix("a0_6_"), band(d, 7, 12).add_prefix("a7_12_"), band(d, 13, 15).add_prefix("a13_15_"), band(d, 16, 18).add_prefix("a16_18_")])).reset_index()
    else:
        agb = pd.DataFrame(columns=["sido_cd", "name"])
    agb["key"] = agb.sido_cd + "|" + agb.name.replace({"세종특별자치시": "세종시"})
    # --- 결합
    D = units[["key", "sido_cd", "sido_nm", "base_nm", "pop_total_2024", "age0_19_2024", "area_km2", "n_general_gu"]].merge(
        base[["key", "fr_child_total", "fr_child_naturalized", "fr_child_domestic"]], on="key", how="left").merge(
        mcb[["key", "mc_members", "mc_children", "mc_children_nat", "mc_children_dom", "mc_marriage_nat"]], on="key", how="left").merge(
        agb.drop(columns=["sido_cd", "name"], errors="ignore"), on="key", how="left")
    for c in ["pop_total_2024", "age0_19_2024", "area_km2"]:
        D[c] = pd.to_numeric(D[c], errors="coerce")
    for c in ["mc_children", "fr_child_total"]:
        D[c + "_blind"] = D[c] == "*"
        D[c] = pd.to_numeric(D[c], errors="coerce")
    D["mc_children_per_1000_age0_19"] = (D.mc_children / D.age0_19_2024 * 1000).round(2)
    D["mc_children_share_national"] = D.mc_children / D.mc_children.sum()
    D = D.sort_values("mc_children", ascending=False).reset_index(drop=True)
    D["rank_mc_children"] = np.arange(1, len(D) + 1)
    D.to_csv(run / "results" / "sigungu_demand.csv", index=False, encoding="utf-8-sig")
    # 검증: 시도 합 vs 시트 시도 행, 일반구 합 vs 시 행, 읍면동 합 vs 시군구
    sido_rows = {sido_code_from_text(str(r[0]).strip()): _num(r[6]) for r in r11 if r[0] and str(r[0]).strip() in SW_NAMES}
    nat = next(_num(r[6]) for r in r11 if r[0] and str(r[0]).strip() == "전국")
    chk = {"n_basic_in_sheet": int(len(base)), "n_basic_units_sgis": int(len(units)), "sheet_only_keys": unmatched, "sgis_only_keys": sgis_only,
           "national_mc_children_sheet": nat, "sum_basic_mc_children": float(D.mc_children.sum()), "blind_basic_mc_children": int(D.mc_children_blind.sum())}
    by_sido = D.groupby("sido_cd").mc_children.sum()
    chk["sido_mismatch"] = {k: (float(by_sido.get(k, 0)), v) for k, v in sido_rows.items() if v not in (None, "*") and abs(by_sido.get(k, 0) - v) > 0.5}
    # 읍면동 → 기초단위 검증(공표값 합 일치율)
    dg["mc_children_num"] = pd.to_numeric(dg.mc_children, errors="coerce")
    dg["key"] = dg.sido_cd + "|" + dg.basic.fillna("").replace({"세종특별자치시": "세종시"})
    dsum = dg.groupby("key").agg(dong_sum=("mc_children_num", "sum"), dong_blind=("mc_children", lambda s: int((s == "*").sum())), n_dong=("dong", "size"))
    cmp = D.set_index("key")[["mc_children"]].join(dsum)
    cmp["dong_sum_equals"] = (cmp.dong_sum - cmp.mc_children).abs() < 0.5
    chk["dong_level_units"] = int(cmp.n_dong.notna().sum()); chk["dong_sum_equal_units"] = int(cmp.dong_sum_equals.sum())
    chk["dong_blind_cells_total"] = int(dg.mc_children.eq("*").sum())
    cmp.reset_index().to_csv(run / "results" / "dong_vs_sigungu_check.csv", index=False, encoding="utf-8-sig")
    dg.to_csv(run / "data_processed" / "dong_mc_children_2025-11-01.csv", index=False, encoding="utf-8-sig")
    # 일반구 → SGIS 코드 (읍면동 경계 결합용)
    gu = d82.copy(); gu["unit_norm"] = gu.name
    sg = sgis_map.copy(); sg["unit_norm"] = sg.SIGUNGU_NM.str.replace(" ", "", regex=False)
    gu = gu.merge(sg[["sido_cd", "unit_norm", "SIGUNGU_CD"]], on=["sido_cd", "unit_norm"], how="left")
    gu.to_csv(run / "data_processed" / "sheet_unit_to_sgis_code.csv", index=False, encoding="utf-8-sig")
    chk["source_typos_corrected"] = SOURCE_TYPOS
    chk["sheet_units_without_sgis_code"] = gu[gu.SIGUNGU_CD.isna() & ~gu.name.isin(base[base.name.isin(gu[gu.level=='일반구'].parent)].name)].name.tolist()[:30]
    wb.close()
    jdump(chk, run / "results" / "n3_demand_checks.json")
    return f"기초지자체 {len(D)}개, 다문화가구 자녀 합 {D.mc_children.sum():.0f} (시트 전국 {nat}); 읍면동 합 일치 {chk['dong_sum_equal_units']}/{chk['dong_level_units']}"

# ====================================================================== N4 supply
def _to_points(df, latc, lonc):
    import geopandas as gpd, pandas as pd, numpy as np
    lat = pd.to_numeric(df[latc], errors="coerce"); lon = pd.to_numeric(df[lonc], errors="coerce")
    swap = (lat > 100) & (lon < 50)                     # 위경도 뒤바뀜
    lat, lon = lat.where(~swap, lon), lon.where(~swap, lat)
    ok = lat.between(32.5, 39.5) & lon.between(124, 132.5)
    return gpd.GeoDataFrame(df.assign(_lat=lat.where(ok), _lon=lon.where(ok), _coord_ok=ok), geometry=gpd.points_from_xy(lon.where(ok), lat.where(ok)), crs=4326)

def _addr_key(addr, units_names):
    t = str(addr or "").split()
    if len(t) < 2:
        return None
    if t[0].startswith("전남광주"):
        sc = "24" if t[1].endswith("구") else "36"      # 2026 통합 표기: 자치구=옛 광주, 시·군=옛 전남
    else:
        sc = sido_code_from_text(t[0])
    if not sc:
        return None
    if sc == "29":
        return "29|세종시"
    k = f"{sc}|{t[1]}"
    return k if k in units_names else None

def assign_units(gdf, units, addr_col=None):
    import geopandas as gpd
    g = gdf.to_crs(5179)
    j = gpd.sjoin(g, units[["key", "geometry"]], predicate="within", how="left")
    j = j[~j.index.duplicated(keep="first")]
    g["key"] = j["key"]; g["key_method"] = g["key"].notna().map({True: "좌표", False: None})
    if addr_col:
        keys = set(units.key)
        fill = g[g.key.isna()][addr_col].map(lambda a: _addr_key(a, keys))
        g.loc[fill.index, "key"] = fill; g.loc[fill.dropna().index, "key_method"] = "주소"
    return g

KW_MC = ["다문화", "이주배경", "결혼이민", "이중언어", "중도입국", "외국인", "이민자", "다가정"]
KW_CHILD = ["자녀", "아동", "청소년", "초등", "중학", "고등", "학생", "유아", "아이", "학령", "어린이", "키즈", "학년", "중도입국", "기초학습"]
RE_CHILD = re.compile(r"(초|중|고)\s?\d|\d\s?~\s?\d+\s?세|만\s?\d+\s?세|\d+\s?세")
KW_EDU = ["학습", "교육", "공부", "진로", "한국어", "언어", "독서", "멘토", "숙제", "기초학력", "코딩", "수학", "국어", "영어", "방과후", "학업", "책", "교실", "공부방", "검정고시"]
KW_CASH = ["교육활동비", "교육비지원", "장학금"]

def classify_program(name, target="", desc=""):
    """참여대상(target)을 아동 여부 판정에 우선 사용. 반환 (분류, 사유)"""
    nm = re.sub(r"\s", "", str(name or "")); tg = re.sub(r"\s", "", str(target or "")); ds = re.sub(r"\s", "", str(desc or ""))
    allt = nm + tg + ds
    mc = any(k in allt for k in KW_MC)
    ch = (any(k in tg for k in KW_CHILD) or bool(RE_CHILD.search(str(target or "")))) if tg else (any(k in nm + ds for k in KW_CHILD))
    ed = any(k in nm + ds for k in KW_EDU) or "기초학습" in allt
    if mc and ch and any(k in nm for k in KW_CASH):
        return "A2_교육비지원(장소 무관)", "현금성 교육비 지원 — 장소 기반 공급에서 제외"
    if mc and ch and ed:
        return "A_확정(다문화·아동·교육)", ""
    if ch and ed and not mc:
        return "B_불확실", "아동 학습 프로그램이나 다문화 대상 여부 불명"
    if mc and ed and not ch:
        return "B_불확실", "다문화 대상 교육이나 참여대상에 아동 표기 없음(성인 대상 가능성)"
    if mc and ch and not ed:
        return "B_불확실", "다문화 아동 대상이나 교육 프로그램 여부 불명"
    return "C_비교육·비대상", ""

def n4_supply(run):
    import geopandas as gpd, pandas as pd
    reg = jload(run / "results" / "dataset_registry.json")
    units = gpd.read_file(run / "data_processed" / "basic_units.gpkg")
    out = {}
    for t in ["family_program", "childcenter_nat", "school", "library", "open_facility"]:
        files = reg["found_types"].get(t, [])
        if not files:
            out[t] = {"state": "자료 없음(미실시)"}; continue
        frames = []
        for f in files:
            for label, df, enc in read_table(ROOT / f):
                if detect_type(f + " " + label, df.columns) in (t, None):
                    df["_source"] = label; frames.append(df)
        if not frames:
            out[t] = {"state": "파일은 있으나 표 인식 실패"}; continue
        df = pd.concat(frames, ignore_index=True)
        C = {k: find_col(df, k) for k in ALIASES}
        n0 = len(df)
        info = {"rows_raw": n0, "columns_used": {k: v for k, v in C.items() if v}}
        if t == "family_program":
            txtcols = [c for c in [C["program"], C["target"], C["desc"], C["category"]] if c]
            _g = lambda c: df[c].fillna("").astype(str) if c else pd.Series([""] * len(df), index=df.index)
            descs = (_g(C["desc"]) + " " + _g(C["category"]))
            cl = pd.Series([classify_program(a, b, c) for a, b, c in zip(_g(C["program"]), _g(C["target"]), descs)], index=df.index)
            df["edu_class"] = cl.str[0]; df["edu_class_reason"] = cl.str[1]
            dkeys = [c for c in [C["org"], C["program"], C["period"], C["place"]] if c]
            df["_dup"] = df.duplicated(subset=dkeys, keep="first") if dkeys else False
            info["n_duplicates"] = int(df._dup.sum())
            info["class_counts"] = df[~df._dup].edu_class.value_counts().to_dict()
            info["text_columns"] = txtcols
            # 위치: 좌표 > 장소 주소 > 운영기관 주소
            if C["lat"] and C["lon"]:
                g = _to_points(df, C["lat"], C["lon"])
            else:
                g = gpd.GeoDataFrame(df.assign(_coord_ok=False), geometry=gpd.points_from_xy([None] * len(df), [None] * len(df)), crs=4326)
            addr = C["place"] if C["place"] and df[C["place"]].astype(str).str.contains(r"[시군구]\s", regex=True).mean() > 0.3 else C["road"]
            g = assign_units(g, units, addr)
            if C["org"] and df[C["org"]].astype(str).str.contains(">").mean() > 0.5:
                ks = set(units.key)
                def _ck(v):
                    a = [x.strip() for x in str(v).split(">")]
                    if len(a) < 2: return None
                    sc = sido_code_from_text(a[0]); tok = a[1].split()[0] if a[1].split() else ""
                    if a[0].startswith("세종"): return "29|세종시"
                    k = f"{sc}|{tok}"; return k if k in ks else None
                ck = df[C["org"]].map(_ck)
                miss = g.key.isna() & ck.notna().values
                g.loc[miss, "key"] = ck[miss.values].values; g.loc[miss, "key_method"] = "센터정보(시도>시군구)"
                g["center_key"] = ck.values
                info["center_vs_place_key_mismatch"] = int(((g.key != g.center_key) & g.center_key.notna() & g.key.notna()).sum())
            if g.key.isna().all() and C["sido"] and C["sgg"]:
                ks = set(units.key)
                g["key"] = (df[C["sido"]].map(sido_code_from_text) + "|" + df[C["sgg"]].astype(str).str.split().str[0]).where(lambda s: s.isin(ks))
                g["key_method"] = "시도·시군구명"
            info["location_basis"] = "운영장소" if addr == C["place"] and addr else ("운영기관 주소" if addr else "시도·시군구명 또는 미상")
        else:
            if C["status"]:
                st = df[C["status"]].astype(str)
                info["status_values"] = st.value_counts().head(10).to_dict()
                closed = st.str.contains("폐|휴|중지|미운영|비개방|불가", regex=True) & ~st.str.contains("운영중|개방", regex=True)
                df = df[~closed]; info["dropped_closed"] = int(closed.sum())
            if C["name"] and C["road"]:
                dup = df.duplicated(subset=[C["name"], C["road"]], keep="first"); info["n_duplicates"] = int(dup.sum()); df = df[~dup]
            if C["lat"] and C["lon"]:
                g = _to_points(df, C["lat"], C["lon"])
            else:
                g = gpd.GeoDataFrame(df.assign(_coord_ok=False), geometry=gpd.points_from_xy([None] * len(df), [None] * len(df)), crs=4326)
            g = assign_units(g, units, C["road"] or C["jibun"])
            if t == "school" and C["level"]:
                g["school_level"] = g[C["level"]].astype(str)
        info["rows_kept"] = int(len(g)); info["coord_ok"] = int(g._coord_ok.sum()) if "_coord_ok" in g else 0
        info["assigned"] = int(g.key.notna().sum()); info["assign_methods"] = g.key_method.value_counts().to_dict()
        info["refdate"] = g[C["refdate"]].astype(str).str[:10].value_counts().head(5).to_dict() if C["refdate"] else "컬럼 없음"
        info["state"] = "적재 완료"
        keep = [c for c in [C["name"], C["program"], C["target"], C["org"], C["place"], C["road"], C["capacity"], C["current"], C["ftype"], C["hours"], C["refdate"]] if c]
        keep += [c for c in ["edu_class", "edu_class_reason", "_dup", "school_level", "_coord_ok", "key", "key_method", "center_key", "_source"] if c in g.columns]
        if C.get("period") and C["period"] not in keep: keep.append(C["period"])
        gg = g[list(dict.fromkeys(keep)) + ["geometry"]].copy()
        gg.columns = [str(c) for c in gg.columns]
        gg.drop(columns="geometry").to_csv(run / "data_processed" / f"supply_{t}.csv", index=False, encoding="utf-8-sig")
        gpts = gg[g._coord_ok.values] if "_coord_ok" in g else gg.iloc[0:0]
        if len(gpts):
            gpts.to_file(run / "data_processed" / f"supply_{t}.gpkg", driver="GPKG")
        info["column_map"] = {k: v for k, v in C.items() if v}
        out[t] = info
    jdump(out, run / "results" / "n4_supply.json")
    return "; ".join(f"{k}:{v.get('state')}({v.get('rows_kept','-')})" for k, v in out.items())

# ====================================================================== N5 compare
def n5_compare(run):
    import pandas as pd, numpy as np
    D = pd.read_csv(run / "results" / "sigungu_demand.csv")
    sup = jload(run / "results" / "n4_supply.json", {})
    T = D[["key", "sido_nm", "base_nm", "mc_children", "mc_children_per_1000_age0_19", "fr_child_total", "a7_12_sum_known", "a13_15_sum_known", "age0_19_2024"]].copy()
    notes = []
    def cnt(t, filt=None, cap=None):
        p = run / "data_processed" / f"supply_{t}.csv"
        if not p.exists():
            return None
        s = pd.read_csv(p, dtype=str)
        if filt is not None:
            s = filt(s)
        c = s.groupby("key").size()
        return c
    fp = run / "data_processed" / "supply_family_program.csv"
    if fp.exists():
        s = pd.read_csv(fp, dtype=str); s = s[s.get("_dup", "False").astype(str) != "True"]
        T["prog_A_confirmed"] = T.key.map(s[s.edu_class.str.startswith("A_")].groupby("key").size()).fillna(0)
        T["prog_B_uncertain"] = T.key.map(s[s.edu_class.str.startswith("B")].groupby("key").size()).fillna(0)
        T["prog_A_per_1000_children"] = (T.prog_A_confirmed / T.mc_children * 1000).round(2)
        T["prog_unassigned"] = int(s.key.isna().sum())
    else:
        notes.append("가족센터 프로그램 자료 없음 → 확인된 교육 프로그램 지표 미산출")
    for t, col in [("childcenter_nat", "n_childcenter"), ("library", "n_library"), ("open_facility", "n_open_facility")]:
        c = cnt(t)
        if c is not None:
            T[col] = T.key.map(c).fillna(0)
        else:
            notes.append(f"{t} 자료 없음 → {col} 미산출")
    c = cnt("school", lambda s: s[s.get("school_level", pd.Series(dtype=str)).astype(str).str.contains("초등|중학", regex=True)] if "school_level" in s else s)
    if c is not None:
        T["n_school_elem_mid"] = T.key.map(c).fillna(0)
    else:
        notes.append("school 자료 없음 → n_school_elem_mid 미산출")
    p = run / "data_processed" / "supply_childcenter_nat.csv"
    if p.exists():
        s = pd.read_csv(p, dtype=str); capc = [c for c in s.columns if "정원" in c]
        if capc:
            T["childcenter_capacity"] = T.key.map(s.assign(_c=pd.to_numeric(s[capc[0]], errors="coerce")).groupby("key")._c.sum())
            T["mc_children_per_childcenter"] = (T.mc_children / T.n_childcenter.replace(0, np.nan)).round(1)
    T.to_csv(run / "results" / "sigungu_demand_supply_comparison.csv", index=False, encoding="utf-8-sig")
    jdump({"notes": notes, "columns": T.columns.tolist()}, run / "results" / "n5_compare.json")
    return f"비교표 {len(T)}행; " + ("; ".join(notes) if notes else "공급 지표 모두 산출")

# ====================================================================== N6 select
def n6_select(run):
    import pandas as pd
    T = pd.read_csv(run / "results" / "sigungu_demand_supply_comparison.csv")
    R = CFG["selection_rule"]
    E = T[T.mc_children >= R["min_mc_children"]].copy()
    if "prog_A_per_1000_children" in T:
        basis = "primary"; E = E.sort_values(["prog_A_per_1000_children", "mc_children"], ascending=[True, False])
    else:
        basis = "fallback(공급 미반영 잠정)"; E = E.sort_values("mc_children_per_1000_age0_19", ascending=False)
    sel = E.head(R["n_select"]).key.tolist()
    for k in R["always_include"]:
        if k not in sel:
            sel.append(k)
    S = T[T.key.isin(sel)].copy(); S["selection_basis"] = basis
    S.to_csv(run / "results" / "representative_regions.csv", index=False, encoding="utf-8-sig")
    jdump({"basis": basis, "rule": R, "n_eligible": int(len(E)), "selected": sel}, run / "results" / "n6_select.json")
    return f"{basis}: {sel}"

# ====================================================================== N7 access/MCLP
def n7_access(run):
    import geopandas as gpd, pandas as pd, numpy as np, pyogrio
    sel = pd.read_csv(run / "results" / "representative_regions.csv")
    mc = CFG["mclp"]
    have = {t: (run / "data_processed" / f"supply_{t}.gpkg").exists() for t in ["family_program", "childcenter_nat", "school", "library", "open_facility"]}
    dg = pd.read_csv(run / "data_processed" / "dong_mc_children_2025-11-01.csv", dtype=str)
    umap = pd.read_csv(run / "data_processed" / "sheet_unit_to_sgis_code.csv", dtype=str)
    dong_attr = pyogrio.read_dataframe(SGIS_DIR / "bnd_dong_00_2025_2Q.shp", read_geometry=False)
    results = []
    for _, r in sel.iterrows():
        key = r.key; rec = {"key": key, "name": f"{r.sido_nm} {r.base_nm}"}
        if key == "25|유성구":
            rec["state"] = "기존 유성구 심층분석 결과 연결(_analysis/candidate_comparison.csv)"
            prev = AN / "results" / "accessibility_coverage_existing.csv"
            if prev.exists():
                a = pd.read_csv(prev).query("scenario=='D2_면적균등' and radius_m==2000").iloc[0]
                rec["prev_coverage_2km"] = float(a.coverage_rate)
        sido_cd, base = key.split("|")
        codes = umap[(umap.sido_cd == sido_cd) & ((umap.parent == base) | (umap.name == base))].SIGUNGU_CD.dropna().unique().tolist()
        fids = dong_attr.index[dong_attr.ADM_CD.str[:5].isin(codes)].tolist()
        if not fids:
            rec.setdefault("state", "행정동 경계 결합 실패 — 미실시"); results.append(rec); continue
        dong = pyogrio.read_dataframe(SGIS_DIR / "bnd_dong_00_2025_2Q.shp", fids=fids).to_crs(5179)
        dd = dg[(dg.sido_cd == sido_cd) & (dg.basic == base)].copy(); dd["n"] = pd.to_numeric(dd.mc_children, errors="coerce")
        dong = dong.merge(dd[["dong", "n", "mc_children"]], left_on="ADM_NM", right_on="dong", how="left")
        rec["n_dong"] = len(dong); rec["dong_matched"] = int(dong.n.notna().sum()); rec["dong_blind"] = int((dong.mc_children == "*").sum())
        if key != "25|유성구" and not (have["school"] or have["library"] or have["open_facility"] or have["childcenter_nat"]):
            rec["state"] = "시설 좌표 자료 없음 — 접근성·MCLP 미실시(행정동 수요만 확인)"; results.append(rec); continue
        if key == "25|유성구":
            results.append(rec); continue
        # --- 수요 격자(D2: 행정동 자녀를 면적에 균등 배분; '*' 동은 제외하고 표시)
        cell = mc["cell_m"]; minx, miny, maxx, maxy = dong.total_bounds
        xs = np.arange(minx + cell / 2, maxx, cell); ys = np.arange(miny + cell / 2, maxy, cell)
        X, Y = np.meshgrid(xs, ys)
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(X.ravel(), Y.ravel()), crs=5179)
        cells = gpd.sjoin(pts, dong[["ADM_NM", "n", "geometry"]], predicate="within")
        cells["w"] = cells.n / cells.groupby("ADM_NM").ADM_NM.transform("size")
        cells = cells[cells.w.notna()]
        x, y, w = cells.geometry.x.values, cells.geometry.y.values, cells.w.values
        region = dong.union_all()
        def pts_of(t, filt=None):
            p = run / "data_processed" / f"supply_{t}.gpkg"
            if not p.exists():
                return gpd.GeoDataFrame(geometry=[], crs=5179)
            g = gpd.read_file(p).to_crs(5179)
            g = g[g.within(region)]
            return filt(g) if filt is not None else g
        A = pts_of("family_program", lambda g: g[g.edu_class.astype(str).str.startswith("A_")])
        if len(A) == 0:
            A = geocode_A_sites(run, key, region)
        rec["A_site_source"] = "좌표/주소 변환" if len(A) else "없음"
        cand = pd.concat([pts_of(t).assign(cand_type=t) for t in ["childcenter_nat", "school", "library", "open_facility"]], ignore_index=True)
        rec["n_A_sites"] = len(A); rec["n_candidates"] = len(cand)
        if len(cand) < mc["min_candidates"]:
            rec["state"] = f"후보 시설 {len(cand)}개 < {mc['min_candidates']} — MCLP 미실시"; results.append(rec); continue
        dA = np.min(np.hypot(x[:, None] - A.geometry.x.values[None], y[:, None] - A.geometry.y.values[None]), axis=1) if len(A) else np.full(len(x), np.inf)
        rows = []
        for R_ in mc["radii_m"]:
            base_cov = float(w[dA <= R_].sum()); wu = w * (dA > R_)
            cv = (np.hypot(x[None, :] - cand.geometry.x.values[:, None], y[None, :] - cand.geometry.y.values[:, None]) <= R_).astype(float)
            gain = cv @ wu; i = int(np.argmax(gain))
            rows.append(dict(radius_m=R_, coverage_before=base_cov / w.sum(), best_candidate=str(cand.iloc[i].get(cand.columns[0])), best_type=cand.iloc[i].cand_type,
                             new_children=float(gain[i]), coverage_after=(base_cov + gain[i]) / w.sum()))
        pd.DataFrame(rows).to_csv(run / "results" / f"mclp_{key.replace('|','_')}.csv", index=False, encoding="utf-8-sig")
        rec["state"] = "접근성·MCLP 수행(직선거리 예비분석)" + ("" if len(A) else " — 지역 내 확인된(게시된) 교육 프로그램 장소 없음 → 기존 포괄 0으로 계산")
        rec["main"] = next(r_ for r_ in rows if r_["radius_m"] == mc["main_radius_m"])
        results.append(rec)
    jdump(results, run / "results" / "n7_access.json")
    return "; ".join(f"{r['name']}: {r.get('state')}" for r in results)

def geocode_A_sites(run, key, region, limit=30):
    """대표지역 안의 '확정' 프로그램 운영 주소만 Nominatim 으로 좌표 변환(캐시). 실패 시 빈 결과."""
    import geopandas as gpd, pandas as pd, requests
    p = run / "data_processed" / "supply_family_program.csv"
    if not p.exists():
        return gpd.GeoDataFrame(geometry=[], crs=5179)
    s = pd.read_csv(p, dtype=str)
    s = s[(s.key == key) & s.edu_class.astype(str).str.startswith("A_") & (s.get("_dup", "False").astype(str) != "True")]
    addr_cols = [c for c in s.columns if any(k in c for k in ["장소", "도로명주소", "주소"])]
    addrs = []
    for _, r in s.iterrows():
        for c in addr_cols:
            v = str(r[c] or "")
            if re.search(r"(로|길)\s*\d", v):
                addrs.append(v); break
    addrs = list(dict.fromkeys(addrs))[:limit]
    cache_p = NW / "status" / "geocode_cache.json"; cache = jload(cache_p, {}) or {}
    pts = []
    for a in addrs:
        q = re.sub(r"\(.*?\)|,.*$", "", a).strip()
        if q not in cache:
            try:
                time.sleep(1.2)
                r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "jsonv2", "countrycodes": "kr", "limit": 1},
                                 headers={"User-Agent": "nationwide-edu-access-analysis/1.0 (public-data idea contest script)"}, timeout=30)
                cache[q] = r.json() if r.status_code == 200 else []
            except Exception:
                cache[q] = []
            jdump(cache, cache_p)
        if cache[q]:
            pts.append(dict(addr=a, lon=float(cache[q][0]["lon"]), lat=float(cache[q][0]["lat"])))
    if not pts:
        return gpd.GeoDataFrame(geometry=[], crs=5179)
    g = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy([p["lon"] for p in pts], [p["lat"] for p in pts]), crs=4326).to_crs(5179)
    return g[g.within(region.buffer(5000))]

# ====================================================================== N8 figures
def n8_figures(run):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt, geopandas as gpd, pandas as pd, numpy as np
    from matplotlib import font_manager as fm
    for f in (AN / "work" / "fonts").glob("*.ttf"):
        fm.fontManager.addfont(str(f))
    matplotlib.rcParams["font.family"] = "NanumGothic"; matplotlib.rcParams["axes.unicode_minus"] = False
    U = gpd.read_file(run / "data_processed" / "basic_units.gpkg")
    T = pd.read_csv(run / "results" / "sigungu_demand_supply_comparison.csv")
    G = U.merge(T, on="key", how="left"); G["geometry"] = G.geometry.simplify(300)
    SRC = "자료: 행정안전부 「2025 지방자치단체 외국인주민 현황」(2025.11.1.) · SGIS 시군구 경계(2025.6.30.) · SGIS 2024 인구(0~19세)"
    figs = []
    fig, axs = plt.subplots(1, 2, figsize=(16, 10))
    for ax, col, ttl, cmap, bins in [(axs[0], "mc_children", "시군구별 다문화가구 자녀 수(명)", "OrRd", [200, 500, 1000, 2000, 4000, 20000]),
                                     (axs[1], "mc_children_per_1000_age0_19", "0~19세 인구 1,000명당 다문화가구 자녀 수(참고)", "PuRd", [10, 15, 20, 30, 50, 300])]:
        G.plot(column=col, cmap=cmap, scheme="UserDefined", classification_kwds=dict(bins=bins), legend=True, ax=ax, edgecolor="white", lw=0.2,
               missing_kwds=dict(color="#ddd", label="자료 없음"), legend_kwds=dict(loc="lower right", fontsize=8, fmt="{:.0f}"))
        yu = G[G.key == "25|유성구"]
        yu.boundary.plot(ax=ax, color="#0570b0", lw=1.5)
        c = yu.geometry.iloc[0].centroid; ax.annotate("유성구", (c.x, c.y), xytext=(-60, 30), textcoords="offset points", fontsize=9, color="#0570b0", arrowprops=dict(arrowstyle="-", color="#0570b0"))
        ax.set_axis_off(); ax.set_title(ttl, fontsize=13)
    fig.suptitle("전국 다문화가정 아동 교육지원 잠재 수요(대리지표) 분포", fontsize=16, fontweight="bold")
    fig.text(0.01, 0.01, SRC + "\n※ 자녀 수는 잠재 수요의 대리지표이며 실제 교육지원 필요 아동 수가 아님. 비율의 분모(2024)와 분자(2025.11.1.)는 기준시점이 다름.", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95)); fig.savefig(run / "figures" / "national_demand_map.png", dpi=170); plt.close(fig); figs.append("national_demand_map.png")
    top = T.sort_values("mc_children", ascending=False).head(25).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.barh([f"{a} {b}" for a, b in zip(top.sido_nm, top.base_nm)], top.mc_children, color=["#0570b0" if k == "25|유성구" else "#fc8d59" for k in top.key])
    ax.set_xlabel("다문화가구 자녀 수(명, 2025.11.1.)"); ax.set_title("다문화가구 자녀 수 상위 25개 시군구"); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(run / "figures" / "top25_sigungu_bar.png", dpi=170); plt.close(fig); figs.append("top25_sigungu_bar.png")
    # 수요 분포 집중도(로렌츠)
    v = np.sort(T.mc_children.dropna().values)[::-1]; cs = np.cumsum(v) / v.sum()
    fig, ax = plt.subplots(figsize=(6.5, 4.5)); ax.plot(np.arange(1, len(v) + 1) / len(v) * 100, cs * 100, color="#d7301f")
    for q in (10, 20):
        i = int(len(v) * q / 100); ax.axvline(q, ls=":", color="#999"); ax.text(q + 1, cs[i - 1] * 100 - 8, f"상위 {q}% 시군구\n= 자녀 {cs[i-1]*100:.0f}%", fontsize=8)
    ax.set_xlabel("시군구 누적 비율(자녀 수 많은 순, %)"); ax.set_ylabel("다문화가구 자녀 누적 비율(%)"); ax.set_title("잠재 수요의 지역 집중도"); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(run / "figures" / "demand_concentration.png", dpi=170); plt.close(fig); figs.append("demand_concentration.png")
    # 공급 지도(자료 있을 때만)
    sup_cols = [c for c in ["prog_A_confirmed", "n_childcenter", "n_school_elem_mid", "n_library", "n_open_facility"] if c in T]
    if sup_cols:
        n = len(sup_cols); fig, axs = plt.subplots(1, n, figsize=(6 * n, 8)); axs = np.atleast_1d(axs)
        lab = {"prog_A_confirmed": "확인된 다문화 아동 교육 프로그램 수", "n_childcenter": "지역아동센터 수(일반 돌봄)", "n_school_elem_mid": "초·중학교 수(후보)", "n_library": "도서관 수(후보)", "n_open_facility": "개방 공공시설 수(후보)"}
        for ax, c in zip(axs, sup_cols):
            G.plot(column=c, cmap="YlGnBu", scheme="Quantiles", k=5, legend=True, ax=ax, edgecolor="white", lw=0.2, legend_kwds=dict(loc="lower right", fontsize=7, fmt="{:.0f}"))
            ax.set_axis_off(); ax.set_title(lab[c], fontsize=11)
        fig.suptitle("교육지원 공급 현황(유형별 분리 — 합산하지 않음)", fontsize=15, fontweight="bold")
        fig.tight_layout(); fig.savefig(run / "figures" / "national_supply_map.png", dpi=150); plt.close(fig); figs.append("national_supply_map.png")
    if "prog_A_per_1000_children" in T:
        E = G[G.mc_children >= CFG["selection_rule"]["min_mc_children"]]
        fig, ax = plt.subplots(figsize=(9, 10)); G.plot(ax=ax, color="#eee", edgecolor="white", lw=0.2)
        E.plot(column="prog_A_per_1000_children", cmap="RdYlGn", scheme="Quantiles", k=5, legend=True, ax=ax, edgecolor="white", lw=0.2, legend_kwds=dict(loc="lower right", fontsize=8))
        ax.set_axis_off(); ax.set_title("다문화가구 자녀 1,000명당 확인된 교육 프로그램 수\n(자녀 300명 이상 시군구; 빨강 = 상대적 공급 부족 가능)", fontsize=12)
        fig.tight_layout(); fig.savefig(run / "figures" / "imbalance_map.png", dpi=170); plt.close(fig); figs.append("imbalance_map.png")
    return f"그림 {len(figs)}종: {figs}"

# ====================================================================== N9 report
def n9_report(run):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import nw_report
    return nw_report.build(run, NW, AN, CFG)

STEPS = [("N1_audit", n1_audit), ("N2_regions", n2_regions), ("N3_demand", n3_demand), ("N4_supply", n4_supply), ("N5_compare", n5_compare),
         ("N6_select", n6_select), ("N7_access", n7_access), ("N8_figures", n8_figures), ("N9_report", n9_report)]

def run_pipeline(run_id=None, only=None):
    run_id = run_id or dt.datetime.now(KST).strftime("run_%Y%m%d_%H%M%S")
    run = NW / "runs" / run_id
    for d in ("data_processed", "results", "figures", "reports"):
        (run / d).mkdir(parents=True, exist_ok=True)
    st = status_update(nationwide_started=True, current_run_id=run_id, error=False, steps={})
    steps = {}
    ok = True
    for name, fn in STEPS:
        if only and name not in only:
            continue
        prev = jload(run / "status_steps.json", {}) or {}
        if prev.get(name, {}).get("state") == "완료":
            steps[name] = prev[name]; continue
        steps[name] = {"state": "실행중", "start": now()}; status_update(current_step=name, steps=steps)
        log.info(f"[{run_id}] {name} 시작")
        try:
            note = fn(run)
            steps[name].update(state="완료", end=now(), note=note); log.info(f"[{run_id}] {name} 완료: {note}")
        except Exception as e:
            tb = traceback.format_exc(); log.error(f"[{run_id}] {name} 실패: {e}\n{tb}")
            (LOGD / f"error_{run_id}_{name}.log").write_text(tb, encoding="utf-8")
            steps[name].update(state="실패", end=now(), error=f"{type(e).__name__}: {e}"); ok = False
            status_update(steps=steps, error=True)
            jdump(steps, run / "status_steps.json")
            if name in ("N1_audit", "N2_regions", "N3_demand"):
                break                       # 이후 단계가 의존 → 중단
            continue
        jdump(steps, run / "status_steps.json"); status_update(steps=steps)
    status_update(current_step=None, steps=steps, last_run_result="성공" if ok else "일부 실패", last_run_finished=now())
    # 최신 성공 실행을 대표 위치로 복사(이전 실행은 runs/ 에 보존)
    if ok:
        for sub in ("results", "figures", "reports", "data_processed"):
            dst = NW / sub; dst.mkdir(parents=True, exist_ok=True)
            for f in (run / sub).glob("*"):
                if f.is_file() and f.stat().st_size < 200_000_000:
                    shutil.copy2(f, dst / f.name)
        (NW / "status" / "LATEST_SUCCESS_RUN").write_text(run_id)
    return ok, run_id

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--run-id"); ap.add_argument("--only", nargs="*"); ap.add_argument("--check-previous", action="store_true")
    a = ap.parse_args()
    if a.check_previous:
        print(json.dumps(check_previous_job(), ensure_ascii=False, indent=2)); sys.exit(0)
    ok, rid = run_pipeline(a.run_id, a.only)
    sys.exit(0 if ok else 1)
