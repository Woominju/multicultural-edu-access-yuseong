#!/usr/bin/env python3
"""
유성구 다문화가정 아동 교육지원 접근성 분석 파이프라인 (아이디어 공모전용)

- 원본 파일은 bigdata/ 루트에 있으며, 이 스크립트는 내용을 절대 수정하지 않는다(이름 변경만, SHA-256 검증).
- 모든 단계는 결과를 _analysis/ 아래에 저장하고 execution_status.json 에 상태를 기록한다.
- 이미 완료된 단계는 재실행 시 건너뛴다(--force 로 재실행).
- 원본 파일은 이름이 아니라 SHA-256 으로 식별하므로, 이름 변경 이후에도 재실행 가능하다.

실행:  python pipeline.py --all            (전체)
       python pipeline.py --step s08 --force
"""
import argparse, datetime as dt, hashlib, io, json, logging, math, os, re, shutil, sys, time, traceback, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .../bigdata
AN = ROOT / "_analysis"
LOG = AN / "logs"; RES = AN / "results"; FIG = AN / "figures"; REP = AN / "reports"; WORK = AN / "work"
for d in (LOG, RES, FIG, REP, WORK):
    d.mkdir(parents=True, exist_ok=True)
STATUS = AN / "execution_status.json"
UA = "yuseong-edu-access-analysis/1.0 (public-data idea contest script)"
KST = dt.timezone(dt.timedelta(hours=9))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG / "execution.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("pipeline")

def now():
    return dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

# ---------------------------------------------------------------- 원본 파일 식별(SHA-256)
KNOWN = {
    # sha256 : (자료키, 표준화 새 이름, 기준일 문자열, 근거)
    "5d7a4ed2b47c9777c6ed0fbc548ed70cbfa67f0a3a8c81fb04eb59a8adb3a9ad": ("cc_2021_01", "유성구_지역아동센터_현황_기준2021-01.xlsx", "2021-01", "시트 '최종(2021.1.)' 및 H2 셀 '(2021. 1월 현재)'"),
    "047a4a58d7e4d15c5732b2516d8574dfe60677eea0573c06bbd43f204731aa62": ("cc_2022_03", "유성구_지역아동센터_현황_기준2022-03.xlsx", "2022-03", "H2 셀 '(2022. 3월 현재)'; 파일명에 날짜 없음"),
    "18cf3a2b02f1fbdf664eaa7691df9606ac6ff40c2ae41cde6b136c4f2d12fd92": ("cc_2022_06", "유성구_지역아동센터_현황_기준2022-06.xlsx", "2022-06", "H2 셀 '(2022. 6월 현재)'; 파일명 '(1)'은 브라우저 중복 다운로드 표기"),
    "381cefb35f48469ba0b1306aa65f49cef51d2a42fe3710c0e68e1761987ba82f": ("cc_2022_12", "유성구_지역아동센터_현황_기준2022-12.xlsx", "2022-12", "H2 셀 '(2022. 12월 현재)' = 파일명 '(2022.12)'"),
    "a87a33aa32114a917a3e6939bf39dd146e851b934d7b612aeb9a73258ade9eec": ("cc_2023_06", "유성구_지역아동센터_현황_기준2023-06.xlsx", "2023-06", "H2 셀 '(2023. 6월 현재)' = 파일명 '(2023.6)'"),
    "472a63c2f32d772a3b74f4bb698c7c8f41485587eeb3c643d39c47994469996d": ("cc_2023_12_31", "유성구_지역아동센터_현황_기준2023-12-31.xlsx", "2023-12-31", "H2 셀 '(2023. 12. 31.기준)' = 파일명 (시트명 '2023.6.'은 이전 양식 잔존)"),
    "f21fb2d4565be48a0346016ab8056352e189f07442524205413475a4028494bd": ("cc_2024_06_30", "유성구_지역아동센터_현황_기준2024-06-30.xlsx", "2024-06-30", "H2 셀 '(2024. 6. 30. 기준)' = 파일명"),
    "7c0703b64335debdef4dad37a275096a470ac8eb847d7ac11ce18f599e3a15c5": ("cc_2024_12_31", "유성구_지역아동센터_현황_기준2024-12-31.xlsx", "2024-12-31", "I2 셀 '(2024. 12. 31. 기준)' = 파일명"),
    "63aeb706295f1b00734e15f0a70c4071c90eefc2ffb866613e8db0e2c0d3fd38": ("cc_2026_01_31", "유성구_지역아동센터_현황_기준2026-01-31.xlsx", "2026-01-31", "I2 셀 '(2026. 1. 31. 기준)' = 파일명"),
    "22fa7e62ce62bb287e4d718297852336dea535e3efab6a33f11a559368de28f3": ("cc_2026_06_30", "유성구_지역아동센터_현황_기준2026-06-30.xlsx", "2026-06-30", "I2 셀 '(2026. 6. 30. 기준)' = 파일명"),
    "e3c47486d49e2ca7e622fa85eed9a62fa3e12c2bb865aa707de588afb8a0a15f": ("foreign_xlsx", "전국_지방자치단체외국인주민현황_통계표_수정본_기준2025-11-01.xlsx", "2025-11-01", "동봉 설명자료 표지 '(2025. 11. 1. 기준)', 작성기준 '직전년도 11월 1일 0시'; 엑셀 수정일 2026-10-29(수정본)"),
    "27afa748398cdfa20df46e9f8f0ecb90367d71606718f1b23f1b8346843ef12a": ("foreign_pdf", "전국_지방자치단체외국인주민현황_설명자료_기준2025-11-01.pdf", "2025-11-01", "PDF 표지 '2025 지방자치단체 외국인주민 현황 (2025. 11. 1. 기준) 2026. 10.'; PDF 생성일 2026-10-28"),
    "5fe0724d911a901c95177eda6c0bf35edd2b3476a8eeee0cdf16a3df1d0daf7a": ("foreign_png", "전국_외국인주민현황_출입국통계연보와의차이안내_기준일미확인.png", "미확인", "통계 수치가 아닌 비교 안내 이미지; 이미지 내 자체 기준일 없음"),
    "f1cf0f9de453ac7eaacb273f39cee52851183372b9ddfda428a967c3a670b2c6": ("sgis_zip", "전국_SGIS행정구역통계및경계_경계기준2025-06-30_통계기준연도2024.zip", "경계 2025-06-30 / 통계 2024", "경계 shp BASE_DATE=20250630(2025년 2분기), 통계 CSV 기준연도=2024 ('2025년기준_2024년' = 2025 경계 기준으로 재집계한 2024 통계)"),
}

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

_SHA_CACHE = {}
def originals():
    """bigdata 루트의 원본 파일 목록 -> {key: Path} (SHA-256 기준)"""
    out = {}
    for p in sorted(ROOT.iterdir()):
        if p.is_file():
            st = p.stat(); ck = (str(p), st.st_size, st.st_mtime)
            if ck not in _SHA_CACHE:
                _SHA_CACHE[ck] = sha256(p)
            s = _SHA_CACHE[ck]
            out[KNOWN[s][0] if s in KNOWN else "unknown:" + p.name] = p
    return out

# ---------------------------------------------------------------- 상태 관리
def load_status():
    if STATUS.exists():
        return json.loads(STATUS.read_text(encoding="utf-8"))
    return {"pipeline": "yuseong_multicultural_edu_access", "created": now(), "steps": {}}

def save_status(st):
    st["updated"] = now()
    tmp = STATUS.with_suffix(".tmp"); tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8"); tmp.replace(STATUS)
    write_progress(st)

def write_progress(st):
    lines = ["# 분석 진행 현황 (analysis_progress.md)", "", f"- 갱신: {st.get('updated')}", f"- 전체 상태: **{st.get('overall','running')}**", "",
             "| 단계 | 설명 | 상태 | 시작 | 종료 | 시도 | 비고 |", "|---|---|---|---|---|---|---|"]
    for k, (desc, _f, _net) in STEPS.items():
        s = st["steps"].get(k, {})
        note = (s.get("note") or s.get("error", "") or "").replace("\n", " ").replace("|", "/")[:160]
        lines.append(f"| {k} | {desc} | {s.get('state','대기')} | {s.get('start','')} | {s.get('end','')} | {s.get('attempts','')} | {note} |")
    (AN / "analysis_progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def jdump(obj, p):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

# ================================================================= S01 파일 인벤토리
def s01_inventory():
    import openpyxl, pypdf, csv
    rows = []
    for p in sorted(ROOT.iterdir()):
        if not p.is_file():
            continue
        s = sha256(p); st = p.stat()
        r = dict(current_name=p.name, ext=p.suffix.lower(), size_bytes=st.st_size, sha256=s,
                 fs_mtime=dt.datetime.fromtimestamp(st.st_mtime, KST).strftime("%Y-%m-%d %H:%M:%S"),
                 dataset_key=KNOWN.get(s, ("unknown",))[0], sheets="", main_columns="", internal_date_text="",
                 doc_created="", doc_modified="", filename_date="", stat_ref_date=KNOWN.get(s, (None, None, "미확인"))[2],
                 publish_date="", provider="", source_url="", yuseong_info="")
        m = re.search(r"(20\d\d)[.\-_ ]?(\d{1,2})?[.\-_ ]?(\d{1,2})?", p.name)
        r["filename_date"] = m.group(0) if m else ""
        if r["ext"] == ".xlsx":
            wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
            r["sheets"] = " / ".join(wb.sheetnames)
            r["doc_created"] = str(wb.properties.created or ""); r["doc_modified"] = str(wb.properties.modified or "")
            ws = wb.worksheets[0]
            top = [list(x) for x in ws.iter_rows(min_row=1, max_row=6, values_only=True)]
            for row in top:
                for v in row:
                    if isinstance(v, str) and re.search(r"현재|기준", v) and re.search(r"20\d\d", v):
                        r["internal_date_text"] = v.strip()
                    if isinstance(v, str) and v.strip() == "연번":
                        r["main_columns"] = ", ".join(str(x).replace("\xa0", "").replace(" ", "") for x in row if x is not None)
            if r["dataset_key"] == "foreign_xlsx":
                r["main_columns"] = "시트별 상이(유형·연령·국적·체류기간·다문화가구원); 11번 시트: 합계/한국인배우자/결혼이민자및귀화자등/자녀(귀화·인지및외국국적, 국내출생)/기타동거인"
                r["internal_date_text"] = "엑셀 내부 기준일 표기 없음 → 동봉 PDF 표지 '2025. 11. 1. 기준'"
                r["provider"] = "행정안전부 사회통합지원과(작성: 국가데이터처 협업)"
                r["source_url"] = "https://www.mois.go.kr (정책자료>통계>승인통계, PDF 기재 공표방법)"
                r["publish_date"] = "2026-10 (PDF 표지 '2026. 10.')"
                r["yuseong_info"] = "유성구 13개 행정동별 다문화가구원(자녀 포함), 외국인주민 유형별, 구 단위 0~18세 연령별 자녀"
            elif r["dataset_key"].startswith("cc_"):
                r["provider"] = "대전광역시 유성구(공공데이터포털 파일데이터로 추정, 원 URL 미확인)"
                r["yuseong_info"] = "지역아동센터 시설명·운영주체·도로명주소·법정동·행정동 (정원·현원·좌표 없음)"
            wb.close()
        elif r["ext"] == ".pdf":
            rd = pypdf.PdfReader(p); md = rd.metadata or {}
            r["doc_created"] = str(md.get("/CreationDate", "")); r["doc_modified"] = str(md.get("/ModDate", ""))
            t = (rd.pages[0].extract_text() or "")
            r["internal_date_text"] = " ".join(t.split())[:120]
            r["sheets"] = f"{len(rd.pages)} pages"
            r["provider"] = "행정안전부 사회통합지원과"; r["publish_date"] = "2026-10 (표지)"
            r["source_url"] = "https://www.mois.go.kr (정책자료>통계>승인통계, PDF 기재 공표방법)"
            r["yuseong_info"] = "통계 정의(자녀=미성년, 5명 미만 '*' 블라인드), 유성구 외국인주민 12,704명(3.3%)"
        elif r["ext"] == ".zip":
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
            r["sheets"] = f"{len(names)} entries"
            r["main_columns"] = "통계 CSV: 기준연도,행정구역코드,통계항목,통계값 / 경계 shp: BASE_DATE,ADM_CD,ADM_NM (EPSG:5179)"
            r["internal_date_text"] = "경계 BASE_DATE=20250630; 통계 파일명 '2025년기준_2024년_*', 기준연도 컬럼=2024"
            r["provider"] = "국가데이터처(구 통계청) SGIS"; r["source_url"] = "https://sgis.mods.go.kr (SGIS 자료제공) – 정확한 다운로드 경로는 로컬 증거로 미확인"
            r["yuseong_info"] = "유성구 13개 행정동 경계(ADM_CD 25040xxx), 2024 행정동별 총인구·5세단위 연령별 인구"
        elif r["ext"] == ".png":
            r["provider"] = "행정안전부(외국인주민 현황 자료 동봉 이미지로 추정)"
            r["yuseong_info"] = "없음(통계 간 정의 차이 설명: 외국인주민 현황 기준일 매년 11.1., 공표 다음연도 11월 표기)"
        rows.append(r)
    with open(AN / "file_inventory.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    # 중복 검사
    from collections import Counter
    dup = [h for h, c in Counter(r["sha256"] for r in rows).items() if c > 1]
    jdump({"n_files": len(rows), "duplicate_sha256": dup, "unknown": [r["current_name"] for r in rows if r["dataset_key"] == "unknown"]}, RES / "s01_inventory_summary.json")
    return f"{len(rows)}개 파일, 동일해시 중복 {len(dup)}건"

# ================================================================= S02 파일명 표준화
def s02_rename():
    import csv, openpyxl
    inv = {}
    with open(AN / "file_inventory.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            inv[r["sha256"]] = r
    plan = []
    for p in sorted(ROOT.iterdir()):
        if not p.is_file():
            continue
        s = sha256(p)
        if s not in KNOWN:
            plan.append(dict(old_name=p.name, new_name="", sha256_before=s, sha256_after="", status="보류(미식별 파일)", evidence="")); continue
        key, new, ref, ev = KNOWN[s]
        # 증거 재확인: 지역아동센터는 엑셀 내부 기준일이 새 이름의 날짜와 일치해야 한다
        if key.startswith("cc_"):
            txt = inv.get(s, {}).get("internal_date_text", "")
            nums = re.findall(r"\d+", txt)
            parsed = "-".join([nums[0]] + [n.zfill(2) for n in nums[1:]]) if nums else ""
            if parsed != ref:
                plan.append(dict(old_name=p.name, new_name=new, sha256_before=s, sha256_after="", status=f"보류(내부기준일 '{txt}' 불일치)", evidence=ev)); continue
        if p.name == new:
            plan.append(dict(old_name=p.name, new_name=new, sha256_before=s, sha256_after=s, status="이미 표준화됨", evidence=ev)); continue
        target = ROOT / new
        if target.exists():
            plan.append(dict(old_name=p.name, new_name=new, sha256_before=s, sha256_after="", status="보류(대상 이름 이미 존재)", evidence=ev)); continue
        plan.append(dict(old_name=p.name, new_name=new, sha256_before=s, sha256_after="", status="변경예정", evidence=ev))
    # 매핑표 먼저 저장(변경 전)
    man = AN / "rename_manifest.csv"
    prev = []
    if man.exists():
        with open(man, encoding="utf-8-sig") as f:
            prev = [r for r in csv.DictReader(f) if r["status"] == "변경완료"]
    def write(rows):
        with open(man, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["old_name", "new_name", "sha256_before", "sha256_after", "status", "evidence", "renamed_at"]); w.writeheader()
            for r in rows:
                w.writerow({**{"renamed_at": ""}, **r})
    write(prev + plan)
    done = 0
    for r in plan:
        if r["status"] != "변경예정":
            continue
        src, dst = ROOT / r["old_name"], ROOT / r["new_name"]
        os.rename(src, dst)  # 같은 파일시스템 내 rename: 내용 불변
        after = sha256(dst)
        if after != r["sha256_before"]:
            raise RuntimeError(f"해시 불일치: {dst}")
        r["sha256_after"] = after; r["status"] = "변경완료"; r["renamed_at"] = now(); done += 1
    # 이전 실행에서 변경완료된 기록을 유지하고, 이번 실행에서 '이미 표준화됨' 항목은 중복 기록하지 않음
    final = prev + [r for r in plan if not (r["status"] == "이미 표준화됨" and any(x["new_name"] == r["new_name"] for x in prev))]
    write(final)
    return f"이번 실행 변경 {done}건, 누적 변경완료 {sum(1 for r in final if r['status']=='변경완료')}건"

# ================================================================= S03 외국인주민·다문화 통계(유성구)
DJ_GU = ["동구", "중구", "서구", "유성구", "대덕구"]

def _sheet_rows(wb, prefix):
    name = [n for n in wb.sheetnames if n.strip().startswith(prefix)][0]
    return name, [list(r) for r in wb[name].iter_rows(values_only=True)]

def _num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return v
    v = str(v).strip().replace(",", "")
    if v == "*": return "*"
    try: return float(v)
    except ValueError: return None

def _dj_window(rows):
    i0 = [i for i, r in enumerate(rows) if isinstance(r[0], str) and r[0].strip() == "대전광역시"]
    i0 = i0[0]
    i1 = next(i for i in range(i0 + 1, len(rows)) if isinstance(rows[i][0], str) and rows[i][0].strip().endswith(("특별자치시", "광역시", "특별시", "도")) and rows[i][0].strip() != "대전광역시")
    return i0, i1

def s03_foreign():
    import openpyxl, pandas as pd
    p = originals()["foreign_xlsx"]
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    out = {"source_file": p.name, "stat_ref_date": "2025-11-01", "publish": "2026-10 (행정안전부)"}
    # --- 11. 다문화가구원(읍면동)
    sn, rows = _sheet_rows(wb, "11.")
    cols = ["구분", "합계", "한국인배우자", "결혼이민자및귀화자등_소계", "결혼이민자", "귀화자등", "자녀_소계", "자녀_귀화인지및외국국적", "자녀_국내출생", "기타동거인_소계", "기타동거인_내국인", "기타동거인_외국인"]
    i0, i1 = _dj_window(rows)
    gu_idx = {r[0].strip(): i for i, r in enumerate(rows[i0:i1], start=i0) if isinstance(r[0], str) and r[0].strip() in DJ_GU}
    order = sorted(gu_idx.items(), key=lambda x: x[1])
    gu_tbl = pd.DataFrame([[_num(v) if j else v.strip() for j, v in enumerate(rows[i][:12])] for _, i in order], columns=cols)
    dj = pd.DataFrame([[_num(v) if j else v.strip() for j, v in enumerate(rows[i0][:12])]], columns=cols)
    ys = gu_idx["유성구"]; ye = min(i for g, i in gu_idx.items() if i > ys) if any(i > ys for i in gu_idx.values()) else i1
    dong = pd.DataFrame([[_num(v) if j else str(v).strip() for j, v in enumerate(r[:12])] for r in rows[ys + 1:ye] if r[0]], columns=cols)
    star = int((dong.iloc[:, 1:] == "*").sum().sum())
    ytot = gu_tbl[gu_tbl.구분 == "유성구"].iloc[0]
    child_sum = pd.to_numeric(dong["자녀_소계"], errors="coerce").sum()
    checks = {"n_dong": len(dong), "dong_child_sum": float(child_sum), "gu_child_total": float(ytot["자녀_소계"]),
              "dong_sum_equals_gu": bool(child_sum == ytot["자녀_소계"]), "blind_cells_in_dong_block": star,
              "blind_cells_in_child_subtotal": int((dong["자녀_소계"] == "*").sum())}
    dong.to_csv(RES / "yuseong_dong_multicultural_household_2025-11-01.csv", index=False, encoding="utf-8-sig")
    pd.concat([dj, gu_tbl]).to_csv(RES / "daejeon_gu_multicultural_household_2025-11-01.csv", index=False, encoding="utf-8-sig")
    out["sheet11"] = {"sheet": sn, "checks": checks}
    # --- 1-3. 외국인주민 유형(읍면동)
    sn, rows = _sheet_rows(wb, "1-3.")
    c13 = ["구분", "외국인주민_합계", "한국국적미보유_소계", "외국인근로자", "결혼이민자", "유학생", "외국국적동포", "기타외국인", "한국국적취득자", "외국인주민자녀_출생"]
    i0, i1 = _dj_window(rows)
    ys = next(i for i in range(i0, i1) if rows[i][0] == "유성구"); ye = next(i for i in range(ys + 1, i1) if rows[i][0] in DJ_GU)
    d13 = pd.DataFrame([[_num(v) if j else str(v).strip() for j, v in enumerate(r[:10])] for r in rows[ys:ye] if r[0]], columns=c13)
    d13.to_csv(RES / "yuseong_dong_foreign_residents_2025-11-01.csv", index=False, encoding="utf-8-sig")
    out["sheet1_3"] = {"sheet": sn, "n_rows": len(d13)}
    # --- 9-2 연령별(시군구): 유성구 0~18세
    sn, rows = _sheet_rows(wb, "9-2.")
    i0, i1 = _dj_window(rows)
    ys = next(i for i in range(i0, i1) if rows[i][0] == "유성구")
    c92 = ["구분", "계", "남", "여", "귀화인지외국국적_계", "귀화인지외국국적_남", "귀화인지외국국적_여", "국내출생_계", "국내출생_남", "국내출생_여"]
    age = pd.DataFrame([[_num(v) if j else str(v).strip() for j, v in enumerate(r[:10])] for r in rows[ys:ys + 20]], columns=c92)
    assert age.구분.iloc[1] == "0세" and age.구분.iloc[-1] == "18세", "연령 블록 파싱 오류"
    age.to_csv(RES / "yuseong_foreign_resident_children_by_age_2025-11-01.csv", index=False, encoding="utf-8-sig")
    a = age.iloc[1:].copy(); a["나이"] = a.구분.str.replace("세", "").astype(int)
    tot = float(age.계.iloc[0])
    bands = {"미취학(0~6세)": a[a.나이 <= 6].계.sum(), "초등학령(7~12세)": a[(a.나이 >= 7) & (a.나이 <= 12)].계.sum(),
             "중학령(13~15세)": a[(a.나이 >= 13) & (a.나이 <= 15)].계.sum(), "고등학령(16~18세)": a[a.나이 >= 16].계.sum()}
    out["sheet9_2"] = {"sheet": sn, "definition": "외국인주민 자녀(미성년, 귀화·인지 및 외국국적 + 국내출생)", "total": tot,
                       "sum_0_18": float(a.계.sum()), "bands": {k: float(v) for k, v in bands.items()},
                       "bands_share": {k: round(float(v) / tot, 4) for k, v in bands.items()}}
    out["note_reference_1524"] = ("사용자 제공 참고치: 대전광역시 공개 2024.11.1. 기준 유성구 다문화가구 자녀 1,524명. 기준일(2024.11.1.)이 본 자료(2025.11.1.)와 달라 결합하지 않음. "
                                  "본 자료의 유성구 값: 다문화가구원 자녀 1,500명(11번 시트), 외국인주민 자녀 1,544명(8-2·9-2 시트) — 정의가 서로 다름.")
    wb.close()
    jdump(out, RES / "s03_foreign_summary.json")
    return f"행정동 {len(dong)}개, 자녀 합 {child_sum:.0f} = 구 합계 {ytot['자녀_소계']:.0f}: {checks['dong_sum_equals_gu']}"

# ================================================================= S04 SGIS 경계·인구
def s04_sgis():
    import geopandas as gpd, pandas as pd, pyogrio
    zp = originals()["sgis_zip"]
    dst = WORK / "sgis"; dst.mkdir(exist_ok=True)
    want = ["bnd_dong_00_2025_2Q", "bnd_sigungu_00_2025_2Q", "성연령별인구.csv", "인구총괄(총인구).csv", "가구총괄.csv", "제공용 코드"]
    got = {}
    with zipfile.ZipFile(zp) as z:
        for n in z.namelist():
            if n.endswith("/") or not any(w in n for w in want):
                continue
            base = Path(n).name
            # 경로 탈출 방지: 파일명만 사용
            tp = dst / base
            if not tp.exists() or tp.stat().st_size != z.getinfo(n).file_size:
                with z.open(n) as src, open(tp, "wb") as f:
                    shutil.copyfileobj(src, f)
            got[base] = n
    jdump(got, RES / "s04_extracted_members.json")
    # 행정동 경계
    shp = dst / "bnd_dong_00_2025_2Q.shp"
    attrs = pyogrio.read_dataframe(shp, read_geometry=False)
    fids = attrs.index[attrs.ADM_CD.astype(str).str.startswith("25040")].tolist()
    g = pyogrio.read_dataframe(shp, fids=fids)
    g = g.set_crs(5179, allow_override=True) if g.crs is None else g
    crs_src = str(g.crs)
    g = g.to_crs(5179)
    g["area_km2"] = g.area / 1e6
    # 대전 시군구 경계(배경용)
    sshp = dst / "bnd_sigungu_00_2025_2Q.shp"
    sat = pyogrio.read_dataframe(sshp, read_geometry=False)
    ccol = [c for c in sat.columns if c.upper().endswith("_CD")][0]; ncol = [c for c in sat.columns if c.upper().endswith("_NM")][0]
    sf = sat.index[sat[ccol].astype(str).str.startswith("25")].tolist()
    sg = pyogrio.read_dataframe(sshp, fids=sf).to_crs(5179)
    sg = sg.rename(columns={ccol: "SGG_CD", ncol: "SGG_NM"})
    sg.to_file(RES / "daejeon_sigungu_2025Q2.gpkg", driver="GPKG")
    # 인구
    def rd(name):
        f = [p for p in dst.iterdir() if p.name.endswith(name)][0]
        try:
            return pd.read_csv(f, encoding="cp949", dtype={"행정구역코드": str})
        except UnicodeDecodeError:
            return pd.read_csv(f, encoding="utf-8", dtype={"행정구역코드": str})
    pop = rd("인구총괄(총인구).csv"); age = rd("성연령별인구.csv"); hh = rd("가구총괄.csv")
    def pick(df, item):
        s = df[(df.행정구역코드.str.startswith("25040")) & (df.통계항목 == item)][["행정구역코드", "통계값"]]
        return s.assign(통계값=pd.to_numeric(s.통계값, errors="coerce")).set_index("행정구역코드").통계값
    P = pd.DataFrame({"pop_total_2024": pick(pop, "to_in_001"), "age0_4_2024": pick(age, "in_age_001"), "age5_9_2024": pick(age, "in_age_002"),
                      "age10_14_2024": pick(age, "in_age_003"), "age15_19_2024": pick(age, "in_age_004"), "households_2024": pick(hh, "to_ga_001")})
    P["age0_19_2024"] = P[["age0_4_2024", "age5_9_2024", "age10_14_2024", "age15_19_2024"]].sum(axis=1)
    gu_row = P.loc["25040"].to_dict() if "25040" in P.index else {}
    P = P.drop(index="25040", errors="ignore")
    g = g.merge(P, left_on="ADM_CD", right_index=True, how="left")
    # 다문화 통계 결합(행정동 이름 기준; 유성구 내 동명 중복 없음 확인)
    mc = pd.read_csv(RES / "yuseong_dong_multicultural_household_2025-11-01.csv")
    fr = pd.read_csv(RES / "yuseong_dong_foreign_residents_2025-11-01.csv")
    fr = fr[fr.구분 != "유성구"]
    names_b, names_s = set(g.ADM_NM), set(mc.구분)
    join = {"boundary_only": sorted(names_b - names_s), "stats_only": sorted(names_s - names_b), "n_boundary": len(g), "n_stats": len(mc),
            "dup_names_boundary": int(g.ADM_NM.duplicated().sum())}
    for c in ["합계", "자녀_소계", "자녀_국내출생", "결혼이민자및귀화자등_소계"]:
        mc[c] = pd.to_numeric(mc[c], errors="coerce")
    g = g.merge(mc[["구분", "합계", "결혼이민자및귀화자등_소계", "자녀_소계", "자녀_국내출생"]].rename(columns={"구분": "ADM_NM", "합계": "mc_household_members", "결혼이민자및귀화자등_소계": "mc_marriage_naturalized", "자녀_소계": "mc_children", "자녀_국내출생": "mc_children_domestic_born"}), on="ADM_NM", how="left")
    fr["외국인주민_합계"] = pd.to_numeric(fr["외국인주민_합계"], errors="coerce")
    g = g.merge(fr[["구분", "외국인주민_합계"]].rename(columns={"구분": "ADM_NM", "외국인주민_합계": "foreign_residents_total"}), on="ADM_NM", how="left")
    g["mc_children_per_1000_age0_19"] = (g.mc_children / g.age0_19_2024 * 1000).round(1)
    g["mc_children_density_per_km2"] = (g.mc_children / g.area_km2).round(1)
    g = g.sort_values("mc_children", ascending=False).reset_index(drop=True)
    g.to_file(RES / "yuseong_dong_2025Q2.gpkg", driver="GPKG")
    g.to_crs(4326).to_file(RES / "yuseong_dong_2025Q2.geojson", driver="GeoJSON")
    g.drop(columns="geometry").to_csv(RES / "yuseong_dong_demand_table.csv", index=False, encoding="utf-8-sig")
    meta = {"crs_source": crs_src, "crs_used": "EPSG:5179 (Korea 2000 / Unified CS, m)", "boundary_base_date": sorted(set(g.BASE_DATE.astype(str))),
            "join_check": join, "gu_population_2024": gu_row, "dong_pop_sum_2024": float(P.pop_total_2024.sum()),
            "yuseong_area_km2": float(g.area_km2.sum()),
            "note": "인구(2024년 기준연도, 2025 경계로 집계)와 다문화 자녀(2025.11.1.)는 기준시점이 약 1년 다름 → 비율은 참고지표"}
    jdump(meta, RES / "s04_sgis_summary.json")
    if join["boundary_only"] or join["stats_only"]:
        return f"경고: 행정동 이름 불일치 {join}"
    return f"유성구 행정동 {len(g)}개 결합(이름 13/13 일치), 면적 {meta['yuseong_area_km2']:.1f}km²"

# ================================================================= S05 지역아동센터 시계열
def _norm_name(s):
    return re.sub(r"\s+", "", str(s or "")).replace("\xa0", "")

def s05_childcenters():
    import openpyxl, pandas as pd
    orig = originals()
    recs = []
    for key, p in sorted(orig.items()):
        if not key.startswith("cc_"):
            continue
        ref = [v for v in KNOWN.values() if v[0] == key][0][2]
        wb = openpyxl.load_workbook(p, data_only=True); ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        hi = next(i for i, r in enumerate(rows) if r and str(r[0]).strip() == "연번")
        hdr = [re.sub(r"\s", "", str(h or "")).replace("\xa0", "") for h in rows[hi]]
        for r in rows[hi + 1:]:
            if r[0] is None or not str(r[0]).strip().isdigit():
                continue
            d = {hdr[j]: r[j] for j in range(len(hdr)) if hdr[j] and hdr[j] != "None"}
            recs.append({"snapshot": ref, "file": p.name, "연번": int(r[0]), "구분": d.get("구분"), "시설명": _norm_name(d.get("시설명")),
                         "운영주체": d.get("운영주체"), "도로명주소": re.sub(r"\s+", " ", str(d.get("도로명주소") or "")).strip(),
                         "우편번호": d.get("우편번호"), "법정동": d.get("법정동"), "행정동": d.get("행정동")})
    df = pd.DataFrame(recs)
    df.to_csv(RES / "childcenter_all_snapshots_long.csv", index=False, encoding="utf-8-sig")
    snaps = sorted(df.snapshot.unique())
    pres = df.pivot_table(index="시설명", columns="snapshot", values="연번", aggfunc="count").reindex(columns=snaps).fillna(0).astype(int)
    pres.to_csv(RES / "childcenter_presence_matrix.csv", encoding="utf-8-sig")
    events = []
    for a, b in zip(snaps[:-1], snaps[1:]):
        A = df[df.snapshot == a].set_index("시설명"); B = df[df.snapshot == b].set_index("시설명")
        gone, new = sorted(set(A.index) - set(B.index)), sorted(set(B.index) - set(A.index))
        for n in gone:
            addr = A.loc[n, "도로명주소"]
            same_addr = [m for m in new if B.loc[m, "도로명주소"].replace(" ", "")[:12] == addr.replace(" ", "")[:12]]
            events.append({"from": a, "to": b, "event": "명칭변경 의심" if same_addr else "목록에서 사라짐(폐지·이전·명칭변경 가능)", "시설명": n, "주소": addr, "관련 신규": ",".join(same_addr)})
        for n in new:
            addr = B.loc[n, "도로명주소"]
            same_addr = [m for m in gone if A.loc[m, "도로명주소"].replace(" ", "")[:12] == addr.replace(" ", "")[:12]]
            events.append({"from": a, "to": b, "event": "명칭변경 의심(신규측)" if same_addr else "목록에 새로 등장(신규 개설 가능)", "시설명": n, "주소": addr, "관련 신규": ",".join(same_addr)})
        # 동일 시설명의 주소 변경
        for n in sorted(set(A.index) & set(B.index)):
            if A.loc[n, "도로명주소"].replace(" ", "") != B.loc[n, "도로명주소"].replace(" ", ""):
                events.append({"from": a, "to": b, "event": "주소 표기 변경(이전 또는 표기 수정)", "시설명": n, "주소": f"{A.loc[n,'도로명주소']} → {B.loc[n,'도로명주소']}", "관련 신규": ""})
    pd.DataFrame(events).to_csv(RES / "childcenter_change_events.csv", index=False, encoding="utf-8-sig")
    latest = df[df.snapshot == snaps[-1]].copy()
    latest.to_csv(RES / "childcenter_latest_2026-06-30.csv", index=False, encoding="utf-8-sig")
    counts = df.groupby("snapshot").size().to_dict()
    by_dong = latest.groupby("행정동").size().to_dict()
    jdump({"snapshots": snaps, "counts": counts, "latest_snapshot": snaps[-1], "latest_n": len(latest), "latest_by_dong": by_dong,
           "has_capacity_columns": False, "has_coordinates": False, "n_events": len(events)}, RES / "s05_childcenter_summary.json")
    return f"스냅샷 {len(snaps)}개, 최신 {snaps[-1]} {len(latest)}개소, 변동 이벤트 {len(events)}건"

# ================================================================= S06 지오코딩(Nominatim/OSM)
FAMILY_CENTER = {"시설명": "대전광역시 가족센터", "도로명주소": "테크노6로 40-17", "행정동": "관평동",
                 "근거": "대전광역시청 누리집 '가족센터(다문화가족 지원사업 수행) 현황' (https://www.daejeon.go.kr/drh/DrhContentsHtmlView.do?menuSeq=2269, 2026-11-03 확인): 소재지 유성구 테크노6로 40-17(관평동), 1,688㎡, 042-252-9989; 사업: 다문화가족자녀지원(기초학습지원, 진로설계지원, 저소득 다문화가족자녀 교육활동비지원)"}

def _clean_addr(a):
    a = re.sub(r"\(.*?\)", " ", a)                 # 괄호(법정동, 건물명)
    a = a.split(",")[0]                            # 쉼표 뒤 층/호
    a = re.sub(r"\d+층|\d+호|지하\d*층?", " ", a)
    a = re.sub(r"(로|길)\s+(\d+번길)", r"\1\2", a)  # '월드컵대로 300번길' -> '월드컵대로300번길'
    a = re.sub(r"(번길|로|길)(\d+(?:-\d+)?)\s*$", r"\1 \2", a.strip())
    m = re.match(r"^(.*?(?:로|길))\s*(\d+(?:-\d+)?)", a.strip())
    return (m.group(1).strip() + " " + m.group(2)) if m else re.sub(r"\s+", " ", a).strip()

def s06_geocode():
    import requests, pandas as pd, geopandas as gpd
    from shapely.geometry import Point
    cache_p = WORK / "geocode_cache.json"
    cache = jload(cache_p) if cache_p.exists() else {}
    dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg")
    yu = dong.union_all()
    lat = pd.read_csv(RES / "childcenter_latest_2026-06-30.csv")
    items = [dict(시설명=FAMILY_CENTER["시설명"], 도로명주소=FAMILY_CENTER["도로명주소"], 행정동=FAMILY_CENTER["행정동"], 법정동="관평동", 우편번호="34014", 유형="A_다문화가족자녀교육지원기관")]
    items += [dict(시설명=r.시설명, 도로명주소=r.도로명주소, 행정동=r.행정동, 법정동=r.법정동, 우편번호=r.우편번호, 유형="B_지역아동센터") for r in lat.itertuples()]
    last = [0.0]
    def q(params):
        k = json.dumps(params, ensure_ascii=False, sort_keys=True)
        if k in cache:
            return cache[k]
        for att in range(4):
            wait = 1.2 - (time.time() - last[0])
            if wait > 0: time.sleep(wait)
            try:
                r = requests.get("https://nominatim.openstreetmap.org/search", params={**params, "format": "jsonv2", "countrycodes": "kr", "addressdetails": 1, "limit": 5},
                                 headers={"User-Agent": UA, "Accept-Language": "ko"}, timeout=30)
                last[0] = time.time()
                if r.status_code == 200:
                    cache[k] = r.json(); jdump(cache, cache_p); return cache[k]
                log.warning(f"nominatim {r.status_code}"); time.sleep(5 * (att + 1))
            except Exception as e:
                log.warning(f"nominatim error {e}"); time.sleep(5 * (att + 1))
        raise RuntimeError("Nominatim 응답 실패")
    out = []
    for it in items:
        road = _clean_addr(it["도로명주소"])
        hn = road.split(" ")[-1]
        bd = it.get("법정동") or ""
        pc = str(it.get("우편번호") or "").split(".")[0]
        tries = [{"q": f"대전광역시 유성구 {road}"}, {"q": f"{road}, 유성구, 대전광역시"},
                 {"street": road, "city": "대전광역시", "county": "유성구"}, {"q": f"{road} 대전"}]
        if bd:
            tries.insert(1, {"q": f"대전광역시 유성구 {bd} {road}"})
        pool = []
        for t in tries:
            for c in q(t):
                pt = gpd.GeoSeries([Point(float(c["lon"]), float(c["lat"]))], crs=4326).to_crs(5179).iloc[0]
                if not yu.contains(pt):
                    continue
                ad = c.get("address", {})
                exact = str(ad.get("house_number", "")) == hn
                dn = dong[dong.contains(pt)].ADM_NM.tolist(); dn = dn[0] if dn else ""
                bb = [float(v) for v in c.get("boundingbox", [c["lat"], c["lat"], c["lon"], c["lon"]])]
                bbp = gpd.GeoSeries([Point(bb[2], bb[0]), Point(bb[3], bb[1])], crs=4326).to_crs(5179)
                unc = 0.5 * bbp.iloc[0].distance(bbp.iloc[1])
                cpc = str(ad.get("postcode", ""))
                pcd = abs(int(cpc) - int(pc)) if cpc.isdigit() and pc.isdigit() else 99999
                prec = "건물/주소점(번지 일치)" if exact else ("도로 수준" if c.get("category") == "highway" or c.get("addresstype") in ("road",) or c.get("type") in ("residential", "secondary", "tertiary", "primary", "living_street", "unclassified", "service", "trunk") else "주소점(번지 불일치)")
                score = (exact, dn == it["행정동"], pcd == 0, -pcd, -unc)
                pool.append((score, dict(c, _pt=pt, _prec=prec, _q=json.dumps(t, ensure_ascii=False), _dn=dn, _unc=unc, _pcd=pcd)))
            if any(sc[0] for sc, _ in pool):
                break
        rec = dict(it, 정제주소=road, lon=None, lat=None, x=None, y=None, 정밀도="실패(좌표 미부여)", 위치불확실성_m=None, 우편번호일치=None,
                   지오코딩질의="", 지오코딩결과="", 좌표행정동="", 행정동일치=None)
        if pool:
            c = max(pool, key=lambda z: z[0])[1]; pt = c["_pt"]
            rec.update(lon=float(c["lon"]), lat=float(c["lat"]), x=pt.x, y=pt.y, 정밀도=c["_prec"], 지오코딩질의=c["_q"], 지오코딩결과=c.get("display_name", ""),
                       좌표행정동=c["_dn"], 행정동일치=c["_dn"] == it["행정동"], 위치불확실성_m=round(c["_unc"]) if c["_prec"] == "도로 수준" else 0,
                       우편번호일치=c["_pcd"] == 0)
        out.append(rec)
        log.info(f"geocode {it['시설명']}: {rec['정밀도']} {rec['좌표행정동']} (명시 {it['행정동']}) ±{rec['위치불확실성_m']}m 우편번호일치={rec['우편번호일치']}")
    df = pd.DataFrame(out)
    # 분석 사용 규칙: 번지 일치 & 행정동 일치 → 사용 / 그 외는 사용(주의표시) 또는 제외
    def use(r):
        if r.정밀도.startswith("실패"): return "제외(좌표 없음)"
        if r.정밀도 == "도로 수준": return "제외(도로 수준 좌표)" if not r.행정동일치 else "사용(주의: 도로 수준)"
        if not r.행정동일치: return "사용(주의: 좌표 행정동 ≠ 명시 행정동)" if r.정밀도.startswith("건물") else "제외(번지·행정동 불일치)"
        return "사용"
    df["분석사용"] = df.apply(use, axis=1)
    df.to_csv(RES / "facilities_geocoded.csv", index=False, encoding="utf-8-sig")
    ok = df[df.분석사용.str.startswith("사용")]
    gpd.GeoDataFrame(ok, geometry=gpd.points_from_xy(ok.x, ok.y), crs=5179).to_file(RES / "facilities_geocoded.gpkg", driver="GPKG")
    summ = df.groupby(["유형", "분석사용"]).size().reset_index(name="n").to_dict("records")
    jdump({"source": "OpenStreetMap Nominatim (ODbL)", "queried_at": now(), "summary": summ, "family_center_evidence": FAMILY_CENTER["근거"]}, RES / "s06_geocode_summary.json")
    return "; ".join(f"{s['유형']}/{s['분석사용']}:{s['n']}" for s in summ)

# ================================================================= S07 OSM 학교·도서관·공공시설·건물
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

def _overpass(q, cache_name):
    import requests
    cp = WORK / cache_name
    if cp.exists():
        return jload(cp)
    err = None
    for att in range(6):
        url = OVERPASS[att % len(OVERPASS)]
        try:
            r = requests.post(url, data={"data": q}, headers={"User-Agent": UA}, timeout=300)
            if r.status_code == 200:
                d = r.json(); d["_fetched_at"] = now(); d["_endpoint"] = url; jdump(d, cp); return d
            err = f"{url} {r.status_code}"
        except Exception as e:
            err = f"{url} {e}"
        log.warning(f"overpass retry {att}: {err}"); time.sleep(20 * (att + 1))
    raise RuntimeError(f"Overpass 실패: {err}")

def _classify(t):
    n = (t.get("name") or "").strip(); a = t.get("amenity"); o = t.get("office")
    if not n:
        return None
    if a == "school":
        if any(k in n for k in ["대학", "외국인학교", "방송통신"]): return None
        if "초등학교" in n or t.get("isced:level") == "1": return "초등학교"
        if "중학교" in n and "고등학교" not in n: return "중학교"
        if "중고등학교" in n or "고등학교" in n: return "고등학교"
        return None
    if a == "library":
        if any(k in n for k in ["대학", "과학기술원", "연구원", "연구소", "에트리", "독서실", "스터디", "(N1)", "학원", "KAIST", "카이스트"]): return None
        if "작은도서관" in n: return "작은도서관"
        if "도서관" in n: return "공공도서관"
        return None
    if (a == "townhall" or o == "government") and "행정복지센터" in n:
        return "행정복지센터"
    if a == "community_centre" and any(k in n for k in ["평생학습", "문화센터", "청소년"]):
        return "주민·평생학습시설"
    return None

def s07_osm():
    import geopandas as gpd, pandas as pd
    from shapely.geometry import Point, Polygon
    dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg"); yu = dong.union_all()
    q = ('[out:json][timeout:180];area["name"="유성구"]["admin_level"="6"]->.a;'
         '(nwr["amenity"~"^(school|library|community_centre|townhall)$"](area.a);nwr["office"="government"](area.a););out center tags;')
    d = _overpass(q, "osm_poi_raw.json")
    rows = []
    for e in d["elements"]:
        t = e.get("tags", {}); c = _classify(t)
        lat = e.get("lat", e.get("center", {}).get("lat")); lon = e.get("lon", e.get("center", {}).get("lon"))
        if c is None or lat is None:
            continue
        rows.append(dict(osm=f"{e['type']}/{e['id']}", 시설명=t.get("name").strip(), 유형=c, lon=lon, lat=lat))
    poi = gpd.GeoDataFrame(rows, geometry=[Point(r["lon"], r["lat"]) for r in rows], crs=4326).to_crs(5179)
    poi = poi[poi.within(yu)].copy()
    poi["norm"] = poi.시설명.str.replace(r"\s+", "", regex=True)
    poi = poi.sort_values("osm").drop_duplicates("norm", keep="first")
    poi = gpd.sjoin(poi, dong[["ADM_NM", "geometry"]], predicate="within", how="left").drop(columns="index_right").rename(columns={"ADM_NM": "행정동"})
    poi["x"] = poi.geometry.x; poi["y"] = poi.geometry.y
    poi.to_file(RES / "osm_public_facilities.gpkg", driver="GPKG")
    poi.drop(columns="geometry").to_csv(RES / "osm_public_facilities.csv", index=False, encoding="utf-8-sig")
    # 건물(수요 공간 가중용 민감도)
    nb = 0; nb_used = 0; berr = ""
    try:
        qb = '[out:json][timeout:300];area["name"="유성구"]["admin_level"="6"]->.a;(way["building"](area.a););out geom tags;'
        b = _overpass(qb, "osm_buildings_raw.json")
        excl = {"industrial", "warehouse", "commercial", "retail", "office", "university", "school", "college", "church", "hospital", "government", "public",
                "garage", "garages", "roof", "service", "shed", "greenhouse", "construction", "kindergarten", "transportation", "train_station", "farm_auxiliary", "temple", "religious", "sports_hall", "hangar", "civic"}
        polys = []
        for e in b["elements"]:
            nb += 1
            bt = e.get("tags", {}).get("building", "yes")
            if bt in excl or "geometry" not in e or len(e["geometry"]) < 4:
                continue
            try:
                polys.append(dict(btype=bt, geometry=Polygon([(p["lon"], p["lat"]) for p in e["geometry"]])))
            except Exception:
                pass
        bg = gpd.GeoDataFrame(polys, crs=4326).to_crs(5179)
        bg = bg[bg.is_valid & bg.centroid.within(yu)]
        bg["area_m2"] = bg.area; nb_used = len(bg)
        bg.to_file(RES / "osm_buildings_residential_proxy.gpkg", driver="GPKG")
        bcnt = gpd.sjoin(gpd.GeoDataFrame(bg.drop(columns="geometry"), geometry=bg.centroid, crs=5179), dong[["ADM_NM", "geometry"]], predicate="within").groupby("ADM_NM").agg(n=("area_m2", "size"), area=("area_m2", "sum"))
        bcnt.to_csv(RES / "osm_buildings_by_dong.csv", encoding="utf-8-sig")
    except Exception as e:
        berr = str(e); log.warning(f"건물 수집 실패(민감도 D3 생략): {e}")
    summ = {"source": "OpenStreetMap via Overpass API (ODbL)", "osm_base_timestamp": d.get("osm3s", {}).get("timestamp_osm_base"), "fetched_at": d.get("_fetched_at"),
            "counts": poi.유형.value_counts().to_dict(), "buildings_total": nb, "buildings_used": nb_used, "buildings_error": berr,
            "caveat": "OSM은 자원봉사 기반 지도로 누락·오분류 가능. 학교는 학교알리미/표준데이터, 도서관은 공공도서관 현황으로 대조 필요."}
    jdump(summ, RES / "s07_osm_summary.json")
    return f"{summ['counts']}, 건물 {nb_used}/{nb}"

# ================================================================= S08 수요 표면(시나리오)
CELL = 100.0

def s08_demand():
    import geopandas as gpd, numpy as np, pandas as pd
    from shapely.geometry import Point
    dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg")
    minx, miny, maxx, maxy = dong.total_bounds
    xs = np.arange(math.floor(minx / CELL) * CELL + CELL / 2, maxx, CELL); ys = np.arange(math.floor(miny / CELL) * CELL + CELL / 2, maxy, CELL)
    X, Y = np.meshgrid(xs, ys)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(X.ravel(), Y.ravel()), crs=5179)
    cells = gpd.sjoin(pts, dong[["ADM_NM", "mc_children", "geometry"]], predicate="within").drop(columns="index_right").reset_index(drop=True)
    cells["x"] = cells.geometry.x; cells["y"] = cells.geometry.y
    # D2 균등 면적
    n_in = cells.groupby("ADM_NM").size()
    cells["w_area"] = cells.mc_children / cells.ADM_NM.map(n_in)
    # D3 OSM 건물 연면적(바닥면적) 가중
    bp = RES / "osm_buildings_residential_proxy.gpkg"
    d3 = False; d3_fallback = []
    if bp.exists():
        bg = gpd.read_file(bp)
        bc = gpd.GeoDataFrame(bg[["area_m2"]], geometry=bg.centroid, crs=5179)
        ix = np.floor((bc.geometry.x - (xs[0] - CELL / 2)) / CELL).astype(int); iy = np.floor((bc.geometry.y - (ys[0] - CELL / 2)) / CELL).astype(int)
        key = pd.Series(bc.area_m2.values, index=list(zip(iy, ix))).groupby(level=0).sum()
        cix = np.floor((cells.x - (xs[0] - CELL / 2)) / CELL).astype(int); ciy = np.floor((cells.y - (ys[0] - CELL / 2)) / CELL).astype(int)
        cells["bld_m2"] = [key.get((a, b), 0.0) for a, b in zip(ciy, cix)]
        tot = cells.groupby("ADM_NM").bld_m2.transform("sum")
        cells["w_bld"] = np.where(tot > 0, cells.mc_children * cells.bld_m2 / tot.replace(0, np.nan), cells.w_area)
        d3_fallback = sorted(cells.loc[tot == 0, "ADM_NM"].unique().tolist())
        d3 = True
    cells.drop(columns="geometry").to_parquet(WORK / "demand_cells.parquet") if _has_parquet() else cells.drop(columns="geometry").to_csv(WORK / "demand_cells.csv", index=False)
    # D1 대표점
    rp = dong.copy(); rp["geometry"] = dong.representative_point(); rp["x"] = rp.geometry.x; rp["y"] = rp.geometry.y
    rp[["ADM_NM", "mc_children", "x", "y"]].to_csv(RES / "demand_points_D1_representative.csv", index=False, encoding="utf-8-sig")
    chk = {"n_cells": len(cells), "cell_m": CELL, "sum_D2": float(cells.w_area.sum()), "sum_D3": float(cells.w_bld.sum()) if d3 else None,
           "D3_available": d3, "D3_dongs_fallback_uniform": d3_fallback, "total_children": float(dong.mc_children.sum())}
    jdump(chk, RES / "s08_demand_summary.json")
    return f"격자 {len(cells)}개(100m), D2 합 {chk['sum_D2']:.0f}, D3 {'가능' if d3 else '불가'}"

def _has_parquet():
    try:
        import pyarrow  # noqa
        return True
    except Exception:
        return False

def load_cells():
    import pandas as pd
    return pd.read_parquet(WORK / "demand_cells.parquet") if (WORK / "demand_cells.parquet").exists() else pd.read_csv(WORK / "demand_cells.csv")

# ================================================================= S09/S10 접근성 + MCLP
RADII = [1000, 1500, 2000, 3000, 5000]
MAIN_R = 2000

def _scenarios():
    import pandas as pd
    cells = load_cells()
    sc = {"D2_면적균등": (cells.x.values, cells.y.values, cells.w_area.values, cells.ADM_NM.values)}
    if "w_bld" in cells:
        sc["D3_건물가중"] = (cells.x.values, cells.y.values, cells.w_bld.values, cells.ADM_NM.values)
    d1 = pd.read_csv(RES / "demand_points_D1_representative.csv")
    sc["D1_대표점"] = (d1.x.values, d1.y.values, d1.mc_children.values.astype(float), d1.ADM_NM.values)
    return sc

def _supply():
    import pandas as pd, geopandas as gpd
    fac = pd.read_csv(RES / "facilities_geocoded.csv")
    fac = fac[fac.분석사용.str.startswith("사용")]
    A = fac[fac.유형.str.startswith("A_")]
    cc = fac[fac.유형 == "B_지역아동센터"]
    osm = pd.read_csv(RES / "osm_public_facilities.csv") if (RES / "osm_public_facilities.csv").exists() else pd.DataFrame(columns=["시설명", "유형", "x", "y", "행정동", "lon", "lat"])
    cand = pd.concat([
        cc.assign(후보유형="지역아동센터", 출처="유성구 지역아동센터 현황(2026-06-30) + Nominatim 지오코딩")[["시설명", "후보유형", "x", "y", "lon", "lat", "행정동", "출처"]],
        osm[osm.유형.isin(["공공도서관", "작은도서관", "초등학교", "중학교", "행정복지센터", "주민·평생학습시설"])].rename(columns={"유형": "후보유형"}).assign(출처="OpenStreetMap")[["시설명", "후보유형", "x", "y", "lon", "lat", "행정동", "출처"]],
    ], ignore_index=True)
    cand = cand.dropna(subset=["x", "y"]).reset_index(drop=True)
    cand.insert(0, "cand_id", [f"C{i:03d}" for i in range(len(cand))])
    return A, cc, cand

def s09_access():
    import numpy as np, pandas as pd
    A, cc, cand = _supply()
    if len(A) == 0:
        raise RuntimeError("기존 교육지원기관(A) 좌표 없음")
    out = []; dong_rows = []
    for sn, (x, y, w, dn) in _scenarios().items():
        dA = np.min(np.hypot(x[:, None] - A.x.values[None], y[:, None] - A.y.values[None]), axis=1)
        dB = np.min(np.hypot(x[:, None] - cc.x.values[None], y[:, None] - cc.y.values[None]), axis=1) if len(cc) else np.full(len(x), np.nan)
        W = w.sum()
        for r in RADII:
            out.append(dict(scenario=sn, radius_m=r, covered_children=float(w[dA <= r].sum()), coverage_rate=float(w[dA <= r].sum() / W),
                            covered_if_all_childcenters_run_program=float(w[np.minimum(dA, dB) <= r].sum()), coverage_rate_if_all_cc=float(w[np.minimum(dA, dB) <= r].sum() / W)))
        df = pd.DataFrame(dict(dong=dn, w=w, dA=dA, dB=dB))
        for d, g in df.groupby("dong"):
            ww = g.w.sum()
            dong_rows.append(dict(scenario=sn, 행정동=d, mc_children=ww, wmean_dist_to_A_km=float((g.w * g.dA).sum() / ww / 1000) if ww else np.nan,
                                  wmean_dist_to_nearest_childcenter_km=float((g.w * g.dB).sum() / ww / 1000) if ww else np.nan,
                                  **{f"cov_A_{r}m": float(g.w[g.dA <= r].sum() / ww) if ww else np.nan for r in RADII}))
        if sn.startswith("D2"):
            np.save(WORK / "dist_A_D2.npy", dA)
    pd.DataFrame(out).to_csv(RES / "accessibility_coverage_existing.csv", index=False, encoding="utf-8-sig")
    dd = pd.DataFrame(dong_rows); dd.to_csv(RES / "accessibility_by_dong.csv", index=False, encoding="utf-8-sig")
    m = pd.DataFrame(out).query("scenario=='D2_면적균등' and radius_m==@MAIN_R").iloc[0]
    return f"[D2, {MAIN_R}m] 기존 가족센터 포괄 {m.covered_children:.0f}명({m.coverage_rate:.1%}); 지역아동센터 전부 활용 시 {m.coverage_rate_if_all_cc:.1%}"

def _cover_matrix(x, y, cx, cy, r):
    import numpy as np
    return (np.hypot(x[None, :] - cx[:, None], y[None, :] - cy[:, None]) <= r).astype(np.float64)

def _best_k(Acov, w, k):
    """정확 열거(k<=3): 포함-배제 + 행렬곱. Acov: (n_cand, n_dem) 0/1, w: 기존 미포괄 수요 가중치"""
    import numpy as np, itertools
    n = Acov.shape[0]
    g = Acov @ w
    if k == 1:
        i = int(np.argmax(g)); return [i], float(g[i])
    P = (Acov * w) @ Acov.T                                   # pairwise intersection
    if k == 2:
        U = g[:, None] + g[None, :] - P; np.fill_diagonal(U, -1); iu = np.triu_indices(n, 1)
        j = int(np.argmax(U[iu])); return [int(iu[0][j]), int(iu[1][j])], float(U[iu][j])
    best = (-1, None)
    for i in range(n - 2):
        Ti = (Acov * (w * Acov[i])) @ Acov.T                  # triple intersection with i
        U = g[i] + g[:, None] + g[None, :] - P[i][:, None] - P[i][None, :] - P + Ti
        mask = np.zeros_like(U, dtype=bool); mask[i + 1:, i + 1:] = np.triu(np.ones((n - i - 1, n - i - 1), dtype=bool), 1)
        if mask.any():
            v = np.where(mask, U, -1); j = int(np.argmax(v))
            if v.flat[j] > best[0]:
                best = (float(v.flat[j]), [i, j // n, j % n])
    return best[1], best[0]

def _greedy(Acov, w, k):
    import numpy as np
    w = w.copy(); sel = []; tot = 0.0
    for _ in range(k):
        g = Acov @ w; i = int(np.argmax(g)); sel.append(i); tot += g[i]; w = w * (1 - Acov[i])
    return sel, tot

def s10_mclp():
    import numpy as np, pandas as pd
    A, cc, cand = _supply()
    cand.to_csv(RES / "candidate_sites.csv", index=False, encoding="utf-8-sig")
    t0 = time.time()
    rows = []; ranks = {}; kres = []; naive = []
    for sn, (x, y, w, dn) in _scenarios().items():
        W = w.sum()
        dA = np.min(np.hypot(x[:, None] - A.x.values[None], y[:, None] - A.y.values[None]), axis=1)
        for r in RADII:
            base = float(w[dA <= r].sum())
            wu = w * (dA > r)                                   # 기존 가족센터가 포괄하지 못한 수요
            Cv = _cover_matrix(x, y, cand.x.values, cand.y.values, r)
            gain = Cv @ wu
            order = np.argsort(-gain)
            rk = np.empty(len(gain), int); rk[order] = np.arange(1, len(gain) + 1)
            for i in range(len(cand)):
                rows.append(dict(scenario=sn, radius_m=r, cand_id=cand.cand_id[i], new_children_covered=float(gain[i]), rank=int(rk[i]),
                                 coverage_before=base / W, coverage_after=(base + gain[i]) / W))
            # 단순 비교안: (a) 자녀 수 최대 행정동, (b) 미포괄 자녀 최대 행정동 → 해당 동 수요 무게중심에 가장 가까운 후보
            for label, crit in [("자녀 수 최대 행정동", w), ("미포괄 자녀 최대 행정동", wu)]:
                s = pd.Series(crit).groupby(dn).sum(); d_top = s.idxmax(); m = dn == d_top
                cxm, cym = np.average(x[m], weights=w[m]), np.average(y[m], weights=w[m])
                inside = cand.index[cand.행정동 == d_top].tolist() or list(range(len(cand)))
                j = min(inside, key=lambda i: math.hypot(cand.x[i] - cxm, cand.y[i] - cym))
                naive.append(dict(scenario=sn, radius_m=r, 방식=label, 선택행정동=d_top, cand_id=cand.cand_id[j], 시설명=cand.시설명[j],
                                  new_children_covered=float(gain[j]), mclp_best_new=float(gain[order[0]]), mclp_best=cand.시설명[order[0]],
                                  ratio_to_mclp=float(gain[j] / gain[order[0]]) if gain[order[0]] > 0 else np.nan))
            for k in (1, 2, 3):
                sel, val = _best_k(Cv, wu, k); gsel, gval = _greedy(Cv, wu, k)
                kres.append(dict(scenario=sn, radius_m=r, k=k, exact_sites=" + ".join(cand.시설명[i] for i in sel), exact_new=val, exact_coverage_after=(base + val) / W,
                                 greedy_sites=" + ".join(cand.시설명[i] for i in gsel), greedy_new=gval, greedy_coverage_after=(base + gval) / W, coverage_before=base / W))
    R = pd.DataFrame(rows).merge(cand, on="cand_id")
    R.to_csv(RES / "mclp_all_scenarios_long.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(kres).to_csv(RES / "mclp_k_sites.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(naive).to_csv(RES / "naive_vs_mclp.csv", index=False, encoding="utf-8-sig")
    # 강건성: 시나리오×반경 조합에서 1위/상위5 횟수
    rob = R.groupby("cand_id").agg(top1_count=("rank", lambda s: int((s == 1).sum())), top5_count=("rank", lambda s: int((s <= 5).sum())),
                                    median_rank=("rank", "median"), n_settings=("rank", "size")).reset_index()
    main = R[(R.scenario == "D2_면적균등") & (R.radius_m == MAIN_R)][["cand_id", "new_children_covered", "rank", "coverage_before", "coverage_after"]].rename(
        columns={"new_children_covered": f"main_new_children_D2_{MAIN_R}m", "rank": f"main_rank_D2_{MAIN_R}m"})
    wide = R.pivot_table(index="cand_id", columns=["scenario", "radius_m"], values="new_children_covered")
    wide.columns = [f"new_{a}_{b}m" for a, b in wide.columns]
    comp = cand.merge(main, on="cand_id").merge(rob, on="cand_id").merge(wide.reset_index(), on="cand_id")
    comp["실행가능성"] = "미확인(시설 협의·공간·운영인력 확인 필요)"
    comp = comp.sort_values([f"main_rank_D2_{MAIN_R}m"]).reset_index(drop=True)
    comp.to_csv(AN / "candidate_comparison.csv", index=False, encoding="utf-8-sig")
    comp.to_csv(RES / "candidate_comparison.csv", index=False, encoding="utf-8-sig")
    # 유형별 최적
    bytype = R[(R.scenario == "D2_면적균등") & (R.radius_m == MAIN_R)].sort_values("rank").groupby("후보유형").head(1)[["후보유형", "시설명", "행정동", "new_children_covered", "rank"]]
    bytype.to_csv(RES / "best_candidate_by_type.csv", index=False, encoding="utf-8-sig")
    jdump({"n_candidates": len(cand), "elapsed_s": round(time.time() - t0, 1), "compute": "CPU(NumPy) — 후보 수백 개×격자 2만 개 규모라 GPU 이점 없음"}, RES / "s10_mclp_summary.json")
    top = comp.iloc[0]
    return f"후보 {len(cand)}개; [D2,{MAIN_R}m] 1위 {top.시설명}({top.행정동}) +{top[f'main_new_children_D2_{MAIN_R}m']:.0f}명; {time.time()-t0:.0f}s"

# ================================================================= S11 그림
def _font():
    import matplotlib
    from matplotlib import font_manager as fm
    for f in (WORK / "fonts").glob("*.ttf"):
        fm.fontManager.addfont(str(f))
    matplotlib.rcParams["font.family"] = "NanumGothic"; matplotlib.rcParams["axes.unicode_minus"] = False

def s11_figures():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt, geopandas as gpd, pandas as pd, numpy as np
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    _font()
    dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg")
    sgg = gpd.read_file(RES / "daejeon_sigungu_2025Q2.gpkg")
    A, cc, cand = _supply()
    osm = pd.read_csv(RES / "osm_public_facilities.csv") if (RES / "osm_public_facilities.csv").exists() else pd.DataFrame()
    comp = pd.read_csv(AN / "candidate_comparison.csv")
    xmin, ymin, xmax, ymax = dong.total_bounds; pad = 1500
    SRC = "자료: 행정안전부 「2025 지방자치단체 외국인주민 현황」(2025.11.1. 기준) · 국가데이터처 SGIS 행정동 경계(2025.6.30.)"
    def base(ax):
        sgg[sgg.SGG_NM != "유성구"].plot(ax=ax, color="#f2f2f2", edgecolor="#bbbbbb", lw=0.6, zorder=1)
        for _, r in sgg[sgg.SGG_NM != "유성구"].iterrows():
            p = r.geometry.representative_point()
            if xmin - pad < p.x < xmax + pad and ymin - pad < p.y < ymax + pad:
                ax.text(p.x, p.y, r.SGG_NM, fontsize=9, color="#999", ha="center", zorder=1)
        ax.set_xlim(xmin - pad, xmax + pad); ax.set_ylim(ymin - pad, ymax + pad); ax.set_axis_off(); ax.set_aspect("equal")
    def labels(ax, col=None, fmt="{}", color="#222"):
        for _, r in dong.iterrows():
            p = r.geometry.representative_point()
            t = r.ADM_NM if col is None else f"{r.ADM_NM}\n{fmt.format(r[col])}"
            ax.annotate(t, (p.x, p.y), ha="center", va="center", fontsize=8, color=color, zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.65))
    def scalebar(ax):
        x0, y0 = xmin + 300, ymin - 1000
        ax.plot([x0, x0 + 2000], [y0, y0], color="k", lw=2); ax.text(x0 + 1000, y0 + 250, "2 km", ha="center", fontsize=8)
        ax.annotate("N", xy=(xmax + 600, ymax + 200), xytext=(xmax + 600, ymax - 900), ha="center", fontsize=10, arrowprops=dict(arrowstyle="-|>", color="k"))
    # ---- A. 수요 지도 (2패널)
    fig, axs = plt.subplots(1, 2, figsize=(15, 8.2))
    for ax, col, ttl, cmap, fmt in [(axs[0], "mc_children", "다문화가구 자녀 수(명)", "OrRd", "{:.0f}명"),
                                     (axs[1], "mc_children_per_1000_age0_19", "참고: 0~19세 인구 1,000명당 다문화가구 자녀 수", "PuRd", "{:.1f}")]:
        base(ax)
        bins = [70, 100, 130, 150, 260] if col == "mc_children" else [15, 20, 30, 45, 60]
        dong.plot(column=col, cmap=cmap, scheme="UserDefined", classification_kwds=dict(bins=bins), legend=True, ax=ax, edgecolor="white", lw=0.8, zorder=2,
                  legend_kwds=dict(loc="lower right", fontsize=8, title=None, fmt="{:.0f}"))
        labels(ax, col, fmt); scalebar(ax); ax.set_title(ttl, fontsize=13)
    fig.suptitle("유성구 행정동별 다문화가정 아동 교육지원 잠재 수요", fontsize=16, fontweight="bold")
    fig.text(0.01, 0.01, SRC + "\n※ 자녀 = 다문화가구원 중 미성년 자녀(2025.11.1.). 0~19세 인구는 SGIS 2024년 통계로 기준시점이 달라 오른쪽 지도는 참고지표.", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95)); fig.savefig(FIG / "demand_map.png", dpi=200); plt.close(fig)
    # ---- B. 시설 지도
    fig, ax = plt.subplots(figsize=(11, 10)); base(ax)
    dong.plot(ax=ax, color="#f4f1ea", edgecolor="#888", lw=0.8, zorder=2); labels(ax, color="#555")
    sty = {"초등학교": ("^", "#6baed6", 22), "중학교": ("v", "#2171b5", 22), "공공도서관": ("s", "#41ab5d", 40), "작은도서관": ("s", "#a1d99b", 18),
           "행정복지센터": ("D", "#9e9ac8", 24)}
    hand = []
    if len(osm):
        for t, (mk, c, s) in sty.items():
            o = osm[osm.유형 == t]
            if len(o):
                ax.scatter(o.x, o.y, marker=mk, c=c, s=s, edgecolors="white", linewidths=0.4, zorder=4)
                hand.append(Line2D([], [], marker=mk, color=c, ls="", ms=7, label=f"{t} ({len(o)}) · B/C 일반 인프라(OSM)"))
    ax.scatter(cc.x, cc.y, marker="o", c="#fd8d3c", s=60, edgecolors="k", linewidths=0.5, zorder=5)
    hand.append(Line2D([], [], marker="o", color="#fd8d3c", mec="k", ls="", ms=8, label=f"지역아동센터 ({len(cc)}) · B 일반 돌봄 인프라"))
    ax.scatter(A.x, A.y, marker="*", c="#d7301f", s=480, edgecolors="k", linewidths=0.8, zorder=7)
    for _, r in A.iterrows():
        ax.annotate(r.시설명, (r.x, r.y), xytext=(8, 8), textcoords="offset points", fontsize=10, fontweight="bold", color="#b30000", zorder=8)
    hand.insert(0, Line2D([], [], marker="*", color="#d7301f", mec="k", ls="", ms=16, label="A 다문화가족 자녀 교육지원 기관(확인됨)"))
    ax.legend(handles=hand, loc="lower right", fontsize=8.5, frameon=True)
    scalebar(ax)
    ax.set_title("유성구 교육지원·돌봄 시설 현황\n(A: 실제 다문화 자녀 교육지원 확인 / B: 일반 교육·돌봄 인프라, 다문화 프로그램 운영 여부 미확인)", fontsize=13)
    fig.text(0.01, 0.01, "자료: 대전광역시 누리집 가족센터 현황(2026.11.3. 확인), 유성구 지역아동센터 현황(2026.6.30.), OpenStreetMap(© OSM contributors, ODbL, 2026.11.3. 추출)\n"
             "좌표: 지역아동센터·가족센터는 도로명주소를 Nominatim으로 변환(번지 일치 검증), 학교·도서관 등은 OSM 위치. 공식 목록과 대조 필요.", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(FIG / "facility_map.png", dpi=200); plt.close(fig)
    # ---- C. 접근성 지도 (현재 vs 추천 거점 추가)
    cells = load_cells()
    best = comp.iloc[0]
    dA = np.min(np.hypot(cells.x.values[:, None] - A.x.values[None], cells.y.values[:, None] - A.y.values[None]), axis=1)
    dN = np.minimum(dA, np.hypot(cells.x.values - best.x, cells.y.values - best.y))
    fig, axs = plt.subplots(1, 2, figsize=(16, 8.4))
    acc = pd.read_csv(RES / "accessibility_coverage_existing.csv").query("scenario=='D2_면적균등' and radius_m==@MAIN_R").iloc[0]
    for ax, d, ttl in [(axs[0], dA, f"현재: 가장 가까운 교육지원 거점(대전광역시 가족센터)까지 직선거리\n{MAIN_R/1000:.0f}km 이내 잠재 수요 포괄률 {acc.coverage_rate:.1%}"),
                       (axs[1], dN, f"남서부 권역(상대동 일대)에 거점 1곳 추가 시 — 예: {best.시설명}\n{MAIN_R/1000:.0f}km 이내 포괄률 {best.coverage_after:.1%} (+{best[f'main_new_children_D2_{MAIN_R}m']:.0f}명)")]:
        base(ax)
        sc = ax.scatter(cells.x, cells.y, c=np.clip(d / 1000, 0, 12), cmap="RdYlGn_r", s=1.1, marker="s", vmin=0, vmax=12, zorder=2, linewidths=0)
        dong.boundary.plot(ax=ax, color="#333", lw=0.7, zorder=3)
        labels(ax, "mc_children", "{:.0f}명")
        for _, r in A.iterrows():
            ax.add_patch(plt.Circle((r.x, r.y), MAIN_R, fill=False, ls="--", ec="#b30000", lw=1.3, zorder=5))
        ax.scatter(A.x, A.y, marker="*", c="#d7301f", s=380, edgecolors="k", zorder=7)
        if d is dN:
            ax.add_patch(plt.Circle((best.x, best.y), MAIN_R, fill=False, ls="--", ec="#08519c", lw=1.6, zorder=5))
            ax.scatter([best.x], [best.y], marker="P", c="#2171b5", s=300, edgecolors="k", zorder=7)
        scalebar(ax); ax.set_title(ttl, fontsize=12)
    cb = fig.colorbar(sc, ax=axs, shrink=0.6, pad=0.01); cb.set_label("직선거리(km, 12km 이상은 12로 표시)")
    fig.suptitle("교육지원 거점 접근성(직선거리 예비분석 — 도보·대중교통 이동시간 아님)", fontsize=15, fontweight="bold")
    fig.text(0.01, 0.01, SRC + f"\n격자 100m, 행정동 자녀 수를 동 면적에 균등 배분(D2). 점선 원 = 반경 {MAIN_R/1000:.0f}km. 후보지의 실제 프로그램 개설 가능성은 미확인.", fontsize=8, color="#555")
    fig.savefig(FIG / "accessibility_map.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    # ---- D. 후보 비교 막대 + 민감도
    top = comp.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 6.5))
    col = {"지역아동센터": "#fd8d3c", "초등학교": "#6baed6", "중학교": "#2171b5", "공공도서관": "#41ab5d", "작은도서관": "#a1d99b", "행정복지센터": "#9e9ac8", "주민·평생학습시설": "#bcbddc"}
    ax.barh([f"{r.시설명} ({r.행정동})" for r in top.itertuples()], top[f"main_new_children_D2_{MAIN_R}m"], color=[col.get(t, "#999") for t in top.후보유형])
    for i, v in enumerate(top[f"main_new_children_D2_{MAIN_R}m"]):
        ax.text(v + 2, i, f"+{v:.0f}명", va="center", fontsize=9)
    ax.set_xlabel(f"신규 거점 추가 시 새로 반경 {MAIN_R/1000:.0f}km 이내에 들어오는 다문화가구 자녀 수(명, D2)")
    ax.legend(handles=[Patch(color=c, label=t) for t, c in col.items() if t in set(top.후보유형)], loc="lower right", fontsize=9)
    ax.set_title("신규 교육지원 거점 후보 상위 12곳 — 기존 가족센터 미포괄 수요 추가 포괄량", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "candidate_top12_bar.png", dpi=200); plt.close(fig)
    L = pd.read_csv(RES / "mclp_all_scenarios_long.csv")
    topids = comp.head(10).cand_id.tolist()
    piv = L[L.cand_id.isin(topids)].pivot_table(index="cand_id", columns=["scenario", "radius_m"], values="rank").reindex(topids)
    fig, ax = plt.subplots(figsize=(13, 5.5))
    im = ax.imshow(piv.values, cmap="viridis_r", vmin=1, vmax=20, aspect="auto")
    ax.set_yticks(range(len(topids))); ax.set_yticklabels([comp.set_index("cand_id").loc[i, "시설명"] for i in topids], fontsize=9)
    ax.set_xticks(range(piv.shape[1])); ax.set_xticklabels([f"{a.split('_')[0]}\n{b/1000:g}km" for a, b in piv.columns], fontsize=8)
    for (i, j), v in np.ndenumerate(piv.values):
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7, color="white" if v < 8 else "black")
    fig.colorbar(im, ax=ax, label="순위(1=최고)")
    ax.set_title("민감도: 수요 배분 방식(D1 대표점 / D2 면적균등 / D3 OSM 건물가중) × 반경별 후보 순위", fontsize=12)
    fig.tight_layout(); fig.savefig(FIG / "sensitivity_rank_heatmap.png", dpi=200); plt.close(fig)
    # ---- E. 지역아동센터 시계열
    s5 = jload(RES / "s05_childcenter_summary.json")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ks = list(s5["counts"].keys()); vs = list(s5["counts"].values())
    ax.plot(ks, vs, marker="o", color="#fd8d3c"); [ax.text(i, v + 0.15, str(v), ha="center", fontsize=9) for i, v in enumerate(vs)]
    ax.set_ylim(min(vs) - 3, max(vs) + 2); ax.set_ylabel("개소"); ax.set_title("유성구 지역아동센터 수 추이(기관 공개 현황표 기준)"); ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(fontsize=8, rotation=30); fig.tight_layout(); fig.savefig(FIG / "childcenter_trend.png", dpi=200); plt.close(fig)
    for f in ["demand_map.png", "facility_map.png", "accessibility_map.png"]:
        shutil.copy2(FIG / f, AN / f)
    return "그림 6종 생성"

# ================================================================= S12 검증
def s12_validate():
    import pandas as pd, geopandas as gpd
    C = []
    def chk(name, ok, detail=""):
        C.append(dict(check=name, result="PASS" if ok else "FAIL", detail=str(detail)))
    s3 = jload(RES / "s03_foreign_summary.json"); s4 = jload(RES / "s04_sgis_summary.json"); s8 = jload(RES / "s08_demand_summary.json")
    chk("다문화 자녀 행정동 합 = 유성구 합계", s3["sheet11"]["checks"]["dong_sum_equals_gu"], s3["sheet11"]["checks"])
    chk("자녀 소계 블라인드(*) 없음", s3["sheet11"]["checks"]["blind_cells_in_child_subtotal"] == 0, s3["sheet11"]["checks"]["blind_cells_in_child_subtotal"])
    chk("경계-통계 행정동 이름 13/13 일치", not s4["join_check"]["boundary_only"] and not s4["join_check"]["stats_only"] and s4["join_check"]["n_boundary"] == 13, s4["join_check"])
    chk("격자 수요 합 = 총 자녀 수(D2)", abs(s8["sum_D2"] - s8["total_children"]) < 1e-6, s8)
    if s8.get("D3_available"):
        chk("격자 수요 합 = 총 자녀 수(D3)", abs(s8["sum_D3"] - s8["total_children"]) < 1e-6, s8["sum_D3"])
    fac = pd.read_csv(RES / "facilities_geocoded.csv")
    chk("가족센터 좌표 확보·관평동 내 위치", bool(fac[fac.유형.str.startswith("A_")].행정동일치.fillna(False).all()), fac[fac.유형.str.startswith("A_")][["정밀도", "좌표행정동"]].to_dict("records"))
    cc = fac[fac.유형 == "B_지역아동센터"]
    chk("지역아동센터 지오코딩 행정동 일치율 ≥ 80%", cc.행정동일치.fillna(False).mean() >= 0.8, f"{cc.행정동일치.fillna(False).sum()}/{len(cc)}")
    cand = pd.read_csv(RES / "candidate_sites.csv")
    dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg"); yu = dong.union_all()
    inside = gpd.GeoSeries(gpd.points_from_xy(cand.x, cand.y), crs=5179).within(yu)
    chk("모든 후보지가 유성구 내부", bool(inside.all()), f"{int(inside.sum())}/{len(cand)}")
    k = pd.read_csv(RES / "mclp_k_sites.csv")
    chk("정확해 ≥ 탐욕해 (모든 설정)", bool((k.exact_new >= k.greedy_new - 1e-6).all()), f"{len(k)} 설정")
    k1 = k[k.k == 1]; L = pd.read_csv(RES / "mclp_all_scenarios_long.csv")
    mx = L.groupby(["scenario", "radius_m"]).new_children_covered.max().reset_index()
    mm = k1.merge(mx, on=["scenario", "radius_m"])
    chk("k=1 정확해 = 후보별 최대 추가포괄", bool(((mm.exact_new - mm.new_children_covered).abs() < 1e-6).all()))
    chk("포괄률 단조성(k=1≤2≤3)", bool(k.pivot_table(index=["scenario", "radius_m"], columns="k", values="exact_new").diff(axis=1).iloc[:, 1:].ge(-1e-9).all().all()))
    pd.DataFrame(C).to_csv(RES / "validation_checks.csv", index=False, encoding="utf-8-sig")
    nf = sum(c["result"] == "FAIL" for c in C)
    return f"{len(C)}개 검증 중 FAIL {nf}"

# ================================================================= S13 보고서
def s13_reports():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import reports  # 같은 폴더의 reports.py
    return reports.build_all(AN, RES, FIG, REP, MAIN_R)

STEPS = {
    "s01": ("파일 메타데이터·기준일 조사", s01_inventory, False),
    "s02": ("파일명 표준화(SHA-256 검증)", s02_rename, False),
    "s03": ("외국인주민·다문화가구 통계 추출(유성구)", s03_foreign, False),
    "s04": ("SGIS 행정동 경계·인구 결합", s04_sgis, False),
    "s05": ("지역아동센터 시계열 정리", s05_childcenters, False),
    "s06": ("가족센터·지역아동센터 지오코딩", s06_geocode, True),
    "s07": ("OSM 학교·도서관·공공시설·건물 수집", s07_osm, True),
    "s08": ("수요 표면(시나리오 D1/D2/D3)", s08_demand, False),
    "s09": ("기존 거점 접근성", s09_access, False),
    "s10": ("신규 거점 MCLP·민감도·단순비교", s10_mclp, False),
    "s11": ("지도·그림 생성", s11_figures, False),
    "s12": ("결과 검증", s12_validate, False),
    "s13": ("보고서·제안서 생성", s13_reports, False),
}
DEPS = {"s04": ["s03"], "s06": ["s04", "s05"], "s07": ["s04"], "s08": ["s04"], "s09": ["s06", "s08"], "s10": ["s06", "s08"],
        "s11": ["s09", "s10"], "s12": ["s10"], "s13": ["s12"]}

def run(steps, force=False):
    st = load_status(); st["overall"] = "running"; st["pid"] = os.getpid(); st["host"] = os.uname().nodename
    st["gpu"] = "사용 안 함(CPU 연산이 더 적합한 소규모 공간분석)"; save_status(st)
    for k in steps:
        desc, fn, net = STEPS[k]
        s = st["steps"].get(k, {})
        if s.get("state") == "완료" and not force:
            log.info(f"[{k}] 이미 완료 - 건너뜀"); continue
        bad = [d for d in DEPS.get(k, []) if st["steps"].get(d, {}).get("state") != "완료"]
        if bad:
            st["steps"][k] = dict(state="건너뜀", note=f"선행 단계 미완료: {bad}", end=now()); save_status(st); log.warning(f"[{k}] 건너뜀: {bad}"); continue
        tries = 3 if net else 2
        for att in range(1, tries + 1):
            st["steps"][k] = dict(state="실행중", start=now(), attempts=att); save_status(st); log.info(f"[{k}] {desc} 시작 (시도 {att})")
            try:
                note = fn()
                st["steps"][k] = dict(state="완료", start=st["steps"][k]["start"], end=now(), attempts=att, note=note); save_status(st)
                log.info(f"[{k}] 완료: {note}"); break
            except Exception as e:
                tb = traceback.format_exc(); log.error(f"[{k}] 실패: {e}\n{tb}")
                (LOG / f"error_{k}.log").write_text(f"{now()}\n{tb}", encoding="utf-8")
                st["steps"][k] = dict(state="실패" if att == tries else "재시도대기", start=st["steps"][k]["start"], end=now(), attempts=att, error=f"{type(e).__name__}: {e}")
                save_status(st)
                if att < tries:
                    time.sleep(30 * att)
    ok = all(st["steps"].get(k, {}).get("state") == "완료" for k in STEPS)
    st["overall"] = "완료" if ok else "부분완료(실패/건너뜀 단계 있음)"; st["finished"] = now(); save_status(st)
    log.info(f"파이프라인 종료: {st['overall']}")
    return ok

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--step", nargs="*"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    steps = list(STEPS) if a.all or not a.step else a.step
    sys.exit(0 if run(steps, a.force) else 1)
