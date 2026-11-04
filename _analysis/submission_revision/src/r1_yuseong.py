#!/usr/bin/env python3
"""
제출 전 수정(1) — 유성구 기존 교육지원 장소 재검증 + 후보지 좌표 보정 + 접근성·MCLP 재계산

원칙
- 기존 결과(_analysis/ 의 results·figures·보고서)는 읽기만 한다. 모든 출력은 submission_revision/ 아래.
- 기존 분석의 수요 격자(work/demand_cells.parquet)와 D1 대표점, MCLP 알고리즘(정확 열거)을 그대로 쓴다.
- 기존 교육지원 장소 시나리오(S0/S1/S2)를 모두 계산하고 유리한 것을 고르지 않는다.
"""
import json, math, re, sys, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd

BIG = Path(__file__).resolve().parents[3]
AN = BIG / "_analysis"; RES = AN / "results"; WORK = AN / "work"
OUT = AN / "submission_revision"; OY = OUT / "yuseong"; FIG = OUT / "figures"
for d in (OY, FIG):
    d.mkdir(parents=True, exist_ok=True)
REF_DATE = pd.Timestamp("2026-11-03")
RADII = [1000, 1500, 2000, 3000, 5000]; MAIN_R = 2000
SW = {"진잠동", "학하동", "상대동", "원신흥동", "온천1동", "온천2동"}     # 기존 분석의 '남서부' 정의(변경 없음)
LOG = []
def log(m):
    print(m); LOG.append(m)

def to5179(lon, lat):
    g = gpd.GeoSeries(gpd.points_from_xy(np.atleast_1d(lon), np.atleast_1d(lat)), crs=4326).to_crs(5179)
    return g.x.values, g.y.values

def norm(s):
    return re.sub(r"[\s()·\-]", "", str(s))

dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg").to_crs(5179)
def dong_of(x, y):
    p = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs=5179)
    j = gpd.sjoin(p, dong[["ADM_NM", "geometry"]], predicate="within", how="left")
    j = j[~j.index.duplicated()]
    return j.ADM_NM.values

# ============================================================== 1. 기존 교육지원 장소(가족센터 프로그램 원자료)
fp = pd.read_csv(BIG / "한국건강가정진흥원_가족센터 프로그램 데이터_20260914.csv", dtype=str)
fp["row_no"] = fp.index + 2                                   # 원자료 CSV 줄 번호(헤더=1)
per = fp["행사기간"].str.extract(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")
fp["start"] = pd.to_datetime(per[0], errors="coerce"); fp["end"] = pd.to_datetime(per[1], errors="coerce")
yv = fp[fp["진행장소"].str.contains("유성구", na=False)].copy()
active = yv[(yv.start <= REF_DATE) & (yv.end >= REF_DATE)].copy()
log(f"[1] 진행장소가 유성구인 프로그램 {len(yv)}건, 2026-11-03이 행사기간에 포함되는 것 {len(active)}건")
active.to_csv(OY / "yuseong_programs_active_20261103_raw.csv", index=False, encoding="utf-8-sig")

# 학습 지원(아동 직접) 판정 — 4건 모두 원문을 직접 읽고 확인(아래 표 근거 열)
edu = active[active["프로그램이름"].str.contains("기초학습|이중언어 학습|한국어|진로", na=False) &
             active["참여대상"].str.contains("자녀|아동|초등", na=False)].copy()
log(f"    그중 아동 대상 학습지원 {len(edu)}건: " + "; ".join(edu["프로그램이름"]))
others = active.drop(edu.index)
if len(others):
    log("    제외(학습지원 아님): " + "; ".join(others["프로그램이름"] + " / " + others["참여대상"]))

sc_school = pd.read_csv(BIG / "전국초중등학교위치표준데이터.csv", encoding="cp949", dtype=str)
sc_y = sc_school[sc_school["소재지도로명주소"].str.contains("대전광역시 유성구", na=False)].copy()

def school_coord(road):
    m = sc_y[sc_y["소재지도로명주소"].str.replace(" ", "") == road.replace(" ", "")]
    if len(m) != 1:
        raise RuntimeError(f"학교 좌표 매칭 실패: {road}")
    r = m.iloc[0]
    return float(r["경도"]), float(r["위도"]), f"전국초중등학교위치표준데이터({r['학교명']}, 기준 {r['데이터기준일자']})", "공식 좌표"

SITES = {   # 진행장소 도로명주소 → 좌표
    "테크노6로 40-17": (127.3943545, 36.4265513, "기존 분석 지오코딩(Nominatim, 번지 일치)", "건물/주소점"),
    "농대로 46": school_coord("대전광역시 유성구 농대로 46"),
    "엑스포로466번길 42": school_coord("대전광역시 유성구 엑스포로466번길 42"),
    # Nominatim 2026-11-03 질의 '대전광역시 유성구 유성대로719번안길 5' → 도로(유성대로719번안길, 장대동, 온천2동)까지만 일치
    "유성대로719번안길 5": (127.3328241, 36.3594071, "Nominatim(OSM) 2026-11-03 — 번지 미일치, 도로 수준", "도로 수준(오차 수백 m 가능)"),
}
rows = []
for _, r in edu.iterrows():
    road = re.search(r"유성구\s+(.+?)\s*\(", r["진행장소"]).group(1).strip()
    lon, lat, src, prec = SITES[road]
    x, y = to5179(lon, lat)
    scope = "구 단위 모집 문구 + 지역 돌봄시설" if "온돌방" in r["진행장소"] else ("구 단위 모집 문구 + 학교 안 운영(재학생 한정 가능성)" if "초등학교" in r["진행장소"] else "가족센터 본관")
    rows.append(dict(
        원자료줄=r.row_no, 프로그램이름=r["프로그램이름"], 행사기간=r["행사기간"], 참여대상=r["참여대상"], 정원=r["정원"],
        진행장소=r["진행장소"], 도로명주소=road, lon=lon, lat=lat, x=float(x[0]), y=float(y[0]), 좌표출처=src, 좌표정밀도=prec,
        좌표행정동=dong_of(x, y)[0], 이용범위=scope,
        증거수준="원자료(2026.9.14. 게시본)에 행사기간이 2026-11-03을 포함하는 일정으로 등록 — 11/3 실제 운영·잔여 정원·외부 아동 참여 가능 여부는 미확인"))
ex = pd.DataFrame(rows)
# 장소 단위로 묶기(같은 장소의 다른 프로그램은 1개 장소)
ex["site"] = ex["도로명주소"].map({"테크노6로 40-17": "E0_대전광역시가족센터(관평동)", "유성대로719번안길 5": "E1_마을돌봄 온돌방(장대동)",
                                "농대로 46": "E2_어은초등학교(어은동)", "엑스포로466번길 42": "E3_전민초등학교(전민동)"})
assert ex.site.notna().all()
ex.sort_values("site").to_csv(OY / "existing_sites_revised.csv", index=False, encoding="utf-8-sig")
sites = ex.groupby("site").agg(x=("x", "first"), y=("y", "first"), 행정동=("좌표행정동", "first"), 정원합=("정원", lambda s: int(sum(int(re.sub(r"\D", "", v) or 0) for v in s))),
                               프로그램수=("프로그램이름", "size"), 좌표정밀도=("좌표정밀도", "first")).reset_index()
log("[1] 장소 단위:\n" + sites.to_string(index=False))

SCEN = {
    "S0_가족센터만(기존)": ["E0_대전광역시가족센터(관평동)"],
    "S1_가족센터+온돌방": ["E0_대전광역시가족센터(관평동)", "E1_마을돌봄 온돌방(장대동)"],
    "S2_등록장소 전체(학교 포함)": ["E0_대전광역시가족센터(관평동)", "E1_마을돌봄 온돌방(장대동)", "E2_어은초등학교(어은동)", "E3_전민초등학교(전민동)"],
}

# ============================================================== 2. 후보지 좌표 보정(공식 표준데이터 우선)
cand0 = pd.read_csv(RES / "candidate_sites.csv")
cc = pd.read_csv(BIG / "전국지역아동센터표준데이터.csv", encoding="cp949", dtype=str)
cc_y = cc[cc["시군구명"].str.contains("유성", na=False)].copy()
lib = pd.read_csv(BIG / "전국도서관표준데이터_1.csv", encoding="cp949", dtype=str)
lib_y = lib[lib["시군구명"].str.contains("유성", na=False) & lib["시도명"].str.contains("대전", na=False)].copy()
fac0 = pd.read_csv(RES / "facilities_geocoded.csv")
# 공식 자료 안에서도 서로 다른 주소가 같은 좌표를 공유하면 공식 좌표를 의심
cc_y["coord"] = cc_y["위도"] + "," + cc_y["경도"]
dupc = cc_y[cc_y.duplicated("coord", keep=False)]
log(f"[2] 공식 지역아동센터 유성구 {len(cc_y)}곳, 서로 다른 주소가 같은 좌표: {dupc['센터명'].tolist()}")

def school_key(n):
    n = norm(n); n = re.sub(r"^대전", "", n); return n
sc_y["k"] = sc_y["학교명"].map(school_key)
lib_y["k"] = lib_y["도서관명"].map(lambda s: re.sub(r"^(대전광역시|대전|유성구립|유성)", "", norm(s)))

aud = []
cand = cand0.copy()
for i, r in cand.iterrows():
    t = r.후보유형; new = None; note = ""
    if t == "지역아동센터":
        m = cc_y[cc_y["센터명"].map(norm) == norm(r.시설명)]
        old_addr = fac0.loc[fac0.시설명 == r.시설명, "도로명주소"].iloc[0]
        old_prec = fac0.loc[fac0.시설명 == r.시설명, "정밀도"].iloc[0]
        if len(m) == 1:
            o = m.iloc[0]
            addr_same = norm(re.sub(r",.*|\(.*", "", old_addr)).replace("번길", "번길") == norm(o["소재지도로명주소"].replace("대전광역시 유성구", ""))
            if o["센터명"] in dupc["센터명"].values and "봉산로" in o["소재지도로명주소"]:
                note = "공식 좌표가 샬롬지역아동센터(노은서로 231)와 동일 — 주소(봉산로 17, 송강동)와 불일치하여 공식 좌표 미사용, 기존 지오코딩 유지"
            else:
                new = (float(o["경도"]), float(o["위도"]), f"전국지역아동센터표준데이터(기준 {o['데이터기준일자']})")
                note = "" if addr_same else f"주소 불일치: 유성구 현황(2026-06-30) '{old_addr}' vs 공식 '{o['소재지도로명주소']}' — 공식 좌표 사용(이전·표기 차이 확인 필요)"
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도=old_prec, 공식주소=o["소재지도로명주소"], 비고=note))
        else:
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도=old_prec, 공식주소="", 비고="공식 자료 매칭 실패 — 기존 좌표 유지"))
    elif t in ("초등학교", "중학교"):
        m = sc_y[sc_y.k == school_key(r.시설명)]
        if len(m) == 1:
            o = m.iloc[0]; new = (float(o["경도"]), float(o["위도"]), f"전국초중등학교위치표준데이터(기준 {o['데이터기준일자']})")
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도="OSM", 공식주소=o["소재지도로명주소"], 비고=""))
        else:
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도="OSM", 공식주소="", 비고=f"공식 자료 매칭 {len(m)}건 — OSM 좌표 유지"))
    elif t in ("공공도서관", "작은도서관"):
        k = re.sub(r"^(대전광역시|대전|유성구립|유성)", "", norm(r.시설명))
        m = lib_y[lib_y.k == k]
        shared = len(m) == 1 and (lib_y[(lib_y["위도"] == m.iloc[0]["위도"]) & (lib_y["경도"] == m.iloc[0]["경도"])]["도서관명"].nunique() > 1)
        if shared:
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도="OSM", 공식주소=m.iloc[0]["소재지도로명주소"],
                            비고="공식 좌표·주소가 다른 도서관(아가랑도서관, 반석로 78)과 동일 — 공식 자료 오류로 판단, OSM 좌표 유지"))
        elif len(m) == 1 and pd.notna(m.iloc[0]["위도"]):
            o = m.iloc[0]; new = (float(o["경도"]), float(o["위도"]), f"전국도서관표준데이터(기준 {o['데이터기준일자']})")
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도="OSM", 공식주소=o["소재지도로명주소"], 비고=""))
        else:
            aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도="OSM", 공식주소="", 비고=f"공식 자료 매칭 {len(m)}건(2021·2026 두 회차; 2026회차는 노은·원신흥도서관 주소가 서로 뒤바뀌어 있음) — OSM 좌표 유지" if len(m) == 2 else f"공식 자료 매칭 {len(m)}건 — OSM 좌표 유지"))
    else:
        aud.append(dict(cand_id=r.cand_id, 시설명=r.시설명, 후보유형=t, 기존정밀도="OSM", 공식주소="", 비고="공식 표준데이터 없음 — OSM 좌표 유지"))
    a = aud[-1]; a["old_lon"], a["old_lat"] = r.lon, r.lat
    if new:
        x, y = to5179(new[0], new[1])
        a.update(new_lon=new[0], new_lat=new[1], 새좌표출처=new[2], 이동거리_m=round(float(math.hypot(x[0] - r.x, y[0] - r.y)), 1))
        cand.loc[i, ["lon", "lat", "x", "y"]] = [new[0], new[1], float(x[0]), float(y[0])]
        cand.loc[i, "출처"] = new[2]
    else:
        a.update(new_lon=r.lon, new_lat=r.lat, 새좌표출처="변경 없음", 이동거리_m=0.0)
cand["행정동"] = dong_of(cand.x.values, cand.y.values)
A = pd.DataFrame(aud)
A["보정후행정동"] = cand["행정동"].values
A.to_csv(OY / "candidate_coordinate_audit.csv", index=False, encoding="utf-8-sig")
outside = cand[cand.행정동.isna()]
if len(outside):
    log(f"[2] 보정 후 유성구 경계 밖 후보 {len(outside)}개 제외: {outside.시설명.tolist()}")
cand = cand[cand.행정동.notna()].reset_index(drop=True)
dd = cand[cand.duplicated(["x", "y"], keep=False)]
log(f"[2] 좌표 보정: {int((A.새좌표출처 != '변경 없음').sum())}/{len(A)}개 공식 좌표로 교체, 이동거리 중앙값 {A.loc[A.이동거리_m > 0, '이동거리_m'].median():.0f} m, 최대 {A.이동거리_m.max():.0f} m")
log(f"[2] 보정 후 좌표가 같은 후보: {dd.시설명.tolist()}")
cand.to_csv(OY / "candidate_sites_revised.csv", index=False, encoding="utf-8-sig")

# ============================================================== 3. 수요(기존 그대로)
cells = pd.read_parquet(WORK / "demand_cells.parquet")
d1 = pd.read_csv(RES / "demand_points_D1_representative.csv")
DEM = {"D2_면적균등": (cells.x.values, cells.y.values, cells.w_area.values),
       "D3_건물가중": (cells.x.values, cells.y.values, cells.w_bld.values),
       "D1_대표점": (d1.x.values, d1.y.values, d1.mc_children.values.astype(float))}

def cover(x, y, cx, cy, r):
    return (np.hypot(x[None, :] - cx[:, None], y[None, :] - cy[:, None]) <= r).astype(np.float64)

def best_k(Acov, w, k):   # 기존 pipeline._best_k 와 동일(정확 열거)
    import itertools
    n = Acov.shape[0]; g = Acov @ w
    if k == 1:
        i = int(np.argmax(g)); return [i], float(g[i])
    P = (Acov * w) @ Acov.T
    if k == 2:
        U = g[:, None] + g[None, :] - P; np.fill_diagonal(U, -1); iu = np.triu_indices(n, 1)
        j = int(np.argmax(U[iu])); return [int(iu[0][j]), int(iu[1][j])], float(U[iu][j])
    best = (-1, None)
    for i in range(n - 2):
        Ti = (Acov * (w * Acov[i])) @ Acov.T
        U = g[i] + g[:, None] + g[None, :] - P[i][:, None] - P[i][None, :] - P + Ti
        mask = np.zeros_like(U, dtype=bool); mask[i + 1:, i + 1:] = np.triu(np.ones((n - i - 1, n - i - 1), dtype=bool), 1)
        v = np.where(mask, U, -1); j = int(np.argmax(v))
        if v.flat[j] > best[0]:
            best = (float(v.flat[j]), [i, j // n, j % n])
    return best[1], best[0]

def run(cset, exist_xy, tag):
    cov_rows, top_rows, k_rows, rank_rows = [], [], [], []
    for dn, (x, y, w) in DEM.items():
        W = w.sum()
        dA = np.min(np.hypot(x[:, None] - exist_xy[:, 0][None], y[:, None] - exist_xy[:, 1][None]), axis=1)
        for r in RADII:
            base = float(w[dA <= r].sum()); wu = w * (dA > r)
            Cv = cover(x, y, cset.x.values, cset.y.values, r); gain = Cv @ wu
            order = np.argsort(-gain, kind="stable")
            cov_rows.append(dict(scenario=tag, demand=dn, radius_m=r, covered=base, coverage=base / W))
            i0 = order[0]
            top_rows.append(dict(scenario=tag, demand=dn, radius_m=r, coverage_before=base / W, best=cset.시설명[i0], best_type=cset.후보유형[i0],
                                 best_dong=cset.행정동[i0], best_in_SW=cset.행정동[i0] in SW, new_children=float(gain[i0]), coverage_after=(base + gain[i0]) / W,
                                 top10_SW_count=int(sum(cset.행정동[j] in SW for j in order[:10])),
                                 gap_1st_10th=float(gain[order[0]] - gain[order[9]])))
            if dn == "D2_면적균등" and r == MAIN_R:
                for rk, j in enumerate(order[:15], 1):
                    rank_rows.append(dict(scenario=tag, rank=rk, 시설명=cset.시설명[j], 후보유형=cset.후보유형[j], 행정동=cset.행정동[j],
                                          lon=cset.lon[j], lat=cset.lat[j], 출처=cset.출처[j], new_children=float(gain[j]), coverage_after=(base + gain[j]) / W))
            for k in (1, 2, 3):
                sel, val = best_k(Cv, wu, k)
                k_rows.append(dict(scenario=tag, demand=dn, radius_m=r, k=k, sites=" + ".join(cset.시설명[i] for i in sel),
                                   dongs=" + ".join(str(cset.행정동[i]) for i in sel), new=val, coverage_before=base / W, coverage_after=(base + val) / W))
    return pd.DataFrame(cov_rows), pd.DataFrame(top_rows), pd.DataFrame(k_rows), pd.DataFrame(rank_rows)

# 재현 검증: 기존 후보 좌표 + 가족센터 단일 → 기존 결과(9.8% → 32.0%)와 같아야 함
cand0["행정동"] = cand0["행정동"]
e0 = sites.set_index("site").loc[["E0_대전광역시가족센터(관평동)"], ["x", "y"]].values
c_, t_, _, _ = run(cand0, e0, "재현")
m = t_.query("demand=='D2_면적균등' and radius_m==@MAIN_R").iloc[0]
prev = pd.read_csv(RES / "mclp_k_sites.csv").query("scenario=='D2_면적균등' and radius_m==@MAIN_R and k==1").iloc[0]
ok = abs(m.coverage_after - prev.exact_coverage_after) < 1e-9 and abs(m.coverage_before - prev.coverage_before) < 1e-9
log(f"[3] 재현 검증(기존 좌표·가족센터 단일): {m.coverage_before:.1%} → {m.coverage_after:.1%} / 기존 {prev.coverage_before:.1%} → {prev.exact_coverage_after:.1%} : {'PASS' if ok else 'FAIL'}")
if not ok:
    sys.exit("재현 실패 — 중단")

allc, allt, allk, allr = [], [], [], []
for tag, ids in SCEN.items():
    xy = sites.set_index("site").loc[ids, ["x", "y"]].values
    c_, t_, k_, r_ = run(cand, xy, tag)
    allc.append(c_); allt.append(t_); allk.append(k_); allr.append(r_)
# 좌표 보정 효과만 분리: 보정 좌표 + S0
c_, t_, k_, r_ = run(cand0.assign(행정동=dong_of(cand0.x.values, cand0.y.values)), e0, "S0(기존 좌표, 참고)")
allt.append(t_)
COV = pd.concat(allc); TOP = pd.concat(allt); K = pd.concat(allk); RK = pd.concat(allr)
COV.to_csv(OY / "coverage_existing_by_scenario.csv", index=False, encoding="utf-8-sig")
TOP.to_csv(OY / "sensitivity_top1_by_scenario.csv", index=False, encoding="utf-8-sig")
K.to_csv(OY / "mclp_k_sites_by_scenario.csv", index=False, encoding="utf-8-sig")
RK.to_csv(OY / "mclp_top15_D2_2km_by_scenario.csv", index=False, encoding="utf-8-sig")

# 요약표
summ = []
for tag in list(SCEN) + ["S0(기존 좌표, 참고)"]:
    t = TOP[TOP.scenario == tag]; mm = t.query("demand=='D2_면적균등' and radius_m==@MAIN_R").iloc[0]
    kk = K[(K.scenario == tag) & (K.demand == "D2_면적균등") & (K.radius_m == MAIN_R)] if tag in SCEN else None
    summ.append(dict(scenario=tag, 기존포괄_D2_2km=round(mm.coverage_before * 100, 1), 최적1곳=mm.best, 최적1곳_행정동=mm.best_dong, 추가포괄_명=round(mm.new_children),
                     추가후포괄=round(mm.coverage_after * 100, 1),
                     k2=(f"{kk[kk.k==2].sites.iloc[0]} → {kk[kk.k==2].coverage_after.iloc[0]:.1%}" if kk is not None else ""),
                     k3=(f"{kk[kk.k==3].sites.iloc[0]} → {kk[kk.k==3].coverage_after.iloc[0]:.1%}" if kk is not None else ""),
                     **{"15설정중_1위가_남서부": f"{int(t.best_in_SW.sum())}/{len(t)}"},
                     상위10중_남서부_D2_2km=int(mm.top10_SW_count), **{"1위와10위차_명": round(mm.gap_1st_10th)}))
S = pd.DataFrame(summ); S.to_csv(OY / "summary_by_scenario.csv", index=False, encoding="utf-8-sig")
log("[4] 시나리오 요약(D2, 2km):\n" + S.to_string(index=False))
log("[4] 기존 포괄률(시나리오 × 수요배분 × 반경):\n" + COV.pivot_table(index=["demand", "radius_m"], columns="scenario", values="coverage").map(lambda v: f"{v:.1%}").to_string())

# ============================================================== 4. 그림
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
for f in (WORK / "fonts").glob("*.ttf"):
    fm.fontManager.addfont(str(f))
matplotlib.rcParams["font.family"] = "NanumGothic"; matplotlib.rcParams["axes.unicode_minus"] = False
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED = "#1f1f1e", "#6b6a64"
fig, axes = plt.subplots(1, 3, figsize=(18, 7.2))
for ax, (tag, ids) in zip(axes, SCEN.items()):
    dong.plot(ax=ax, column="mc_children", cmap="Blues", edgecolor="white", lw=0.8, vmin=0, vmax=dong.mc_children.max() * 1.15)
    xy = sites.set_index("site").loc[ids, ["x", "y"]].values
    for (x0, y0) in xy:
        ax.add_patch(plt.Circle((x0, y0), MAIN_R, fill=False, ec=BLUE, lw=1.6, ls="--"))
    ax.scatter(xy[:, 0], xy[:, 1], s=90, marker="s", c=BLUE, ec="white", lw=2, zorder=5)
    b = TOP[(TOP.scenario == tag) & (TOP.demand == "D2_면적균등") & (TOP.radius_m == MAIN_R)].iloc[0]
    bc = cand[cand.시설명 == b.best].iloc[0]
    ax.add_patch(plt.Circle((bc.x, bc.y), MAIN_R, fill=False, ec=ORANGE, lw=1.6))
    ax.scatter([bc.x], [bc.y], s=220, marker="*", c=ORANGE, ec="white", lw=1.5, zorder=6)
    ax.annotate(f"{b.best}\n({b.best_dong})", (bc.x, bc.y), xytext=(8, -26), textcoords="offset points", fontsize=9, color=INK)
    for _, s in sites[sites.site.isin(ids)].iterrows():
        ax.annotate(s.site.split("_", 1)[1], (s.x, s.y), xytext=(6, 6), textcoords="offset points", fontsize=8.5, color=INK)
    ax.set_title(f"{tag}\n기존 2km 포괄 {b.coverage_before:.1%} → 거점 1곳 추가 {b.coverage_after:.1%}", fontsize=12, color=INK)
    ax.set_axis_off(); ax.set_aspect("equal")
h = [Line2D([], [], marker="s", ls="", color=BLUE, ms=9, label="기존 교육지원 장소(시나리오별)"),
     Line2D([], [], marker="*", ls="", color=ORANGE, ms=14, label="MCLP 최적 신규 거점 1곳(D2, 2km)"),
     Line2D([], [], color=BLUE, ls="--", label="반경 2km(직선)")]
fig.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, 0.035), ncol=3, frameon=False, fontsize=10.5)
fig.text(0.5, 0.005, "색: 행정동별 다문화가구 자녀 수(2025.11.1.) · 직선거리 예비분석 · 기존 장소는 가족센터 프로그램 원자료(2026.9.14.)의 진행장소, 실제 운영·외부 참여 가능 여부 미확인",
         ha="center", fontsize=9, color=MUTED)
plt.tight_layout(rect=(0, 0.09, 1, 1))
fig.savefig(FIG / "yuseong_existing_sites_scenarios_map.png", dpi=150); plt.close(fig)

# 포괄률 비교(시나리오 × 반경, D2): 기존 vs 1곳 추가 — 두 계열
fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
for ax, tag in zip(axs, SCEN):
    t = TOP[(TOP.scenario == tag) & (TOP.demand == "D2_면적균등")].sort_values("radius_m")
    xs = np.arange(len(t)); bw = 0.38
    ax.bar(xs - bw / 2 - 0.01, t.coverage_before * 100, bw, color=BLUE, label="기존 장소")
    ax.bar(xs + bw / 2 + 0.01, t.coverage_after * 100, bw, color=ORANGE, label="+ 최적 거점 1곳")
    for xi, (a, b) in enumerate(zip(t.coverage_before * 100, t.coverage_after * 100)):
        ax.text(xi - bw / 2, a + 1, f"{a:.0f}", ha="center", fontsize=8.5, color=INK)
        ax.text(xi + bw / 2, b + 1, f"{b:.0f}", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(xs, [f"{r/1000:g}km" for r in t.radius_m]); ax.set_title(tag, fontsize=11, color=INK)
    ax.spines[["top", "right"]].set_visible(False); ax.grid(axis="y", color="#e6e5e0", lw=0.8); ax.set_axisbelow(True)
axs[0].set_ylabel("다문화가구 자녀 포괄률(%) — D2 면적균등")
axs[0].legend(frameon=False, loc="upper left")
plt.tight_layout(); fig.savefig(FIG / "yuseong_coverage_by_scenario_radius.png", dpi=150); plt.close(fig)

(OUT / "logs" / "r1_yuseong.log").write_text("\n".join(LOG), encoding="utf-8")
print("DONE")
