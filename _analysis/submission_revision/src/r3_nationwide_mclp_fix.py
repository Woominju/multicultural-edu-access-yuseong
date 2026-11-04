#!/usr/bin/env python3
"""
제출 전 수정(3) — 전국 대표지역 MCLP 재계산(후보명 nan 버그 수정 + 기존 거점 가정 2종)

버그: 기존 nw_pipeline.n7_access 는 4종 시설을 concat 한 뒤 첫 번째 열(cand.columns[0]='센터명')을 이름으로 썼다
      → 학교·도서관·공공시설 후보는 이름이 NaN. 여기서는 유형별 이름 열을 명시한다.
기존 거점 가정
  B0 = 기존 결과와 동일: 지역 내 '확정(A)' 프로그램 장소 없음 → 기존 포괄 0
  B1 = 해당 시군구 가족센터가 직접 게시한 프로그램의 주 운영장소(5건 이상)를 기존 거점으로 둠(교육 공급 확인 아님, 참고)
수요 격자·반경·후보 집합은 기존 N7 과 동일(config.json).
"""
import json, os, re, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, pyogrio, requests

BIG = Path(__file__).resolve().parents[3]; AN = BIG / "_analysis"; NW = AN / "nationwide"; RUN = NW / "runs" / os.environ.get("NW_RUN_ID", "run_20261103_174512")
OUT = AN / "submission_revision" / "nationwide"
CFG = json.loads((NW / "config" / "config.json").read_text(encoding="utf-8")); mc = CFG["mclp"]
SGIS = AN / "work" / "sgis"
REP = ["21|강서구", "38|창녕군", "38|하동군", "38|합천군"]
NAME = {"childcenter_nat": lambda g: g["센터명"], "school": lambda g: g["학교명"], "library": lambda g: g["도서관명"],
        "open_facility": lambda g: g["개방시설명"].astype(str) + " (" + g["개방장소명"].astype(str) + ")"}

fp = pd.read_csv(OUT / "family_program_reclassified.csv", dtype=str, low_memory=False)
fp = fp[fp._dup == "False"]
cache_p = OUT / "geocode_cache_b1.json"
cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
def geocode(addr):
    if addr not in cache:
        r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": addr, "format": "jsonv2", "countrycodes": "kr", "limit": 1, "addressdetails": 1},
                         headers={"User-Agent": "yuseong-edu-access-analysis/1.0 (public-data idea contest script)"}, timeout=30)
        cache[addr] = r.json() if r.status_code == 200 else []
        cache_p.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"); time.sleep(1.2)
    return cache[addr]

dg = pd.read_csv(RUN / "data_processed" / "dong_mc_children_2025-11-01.csv", dtype=str)
umap = pd.read_csv(RUN / "data_processed" / "sheet_unit_to_sgis_code.csv", dtype=str)
dong_attr = pyogrio.read_dataframe(SGIS / "bnd_dong_00_2025_2Q.shp", read_geometry=False)
res_rows, b1_rows, top_rows = [], [], []
for key in REP:
    sido_cd, base = key.split("|")
    codes = umap[(umap.sido_cd == sido_cd) & ((umap.parent == base) | (umap.name == base))].SIGUNGU_CD.dropna().unique().tolist()
    fids = dong_attr.index[dong_attr.ADM_CD.str[:5].isin(codes)].tolist()
    dong = pyogrio.read_dataframe(SGIS / "bnd_dong_00_2025_2Q.shp", fids=fids).to_crs(5179)
    dd = dg[(dg.sido_cd == sido_cd) & (dg.basic == base)].copy(); dd["n"] = pd.to_numeric(dd.mc_children, errors="coerce")
    dong = dong.merge(dd[["dong", "n"]], left_on="ADM_NM", right_on="dong", how="left")
    cell = mc["cell_m"]; minx, miny, maxx, maxy = dong.total_bounds
    X, Y = np.meshgrid(np.arange(minx + cell / 2, maxx, cell), np.arange(miny + cell / 2, maxy, cell))
    cells = gpd.sjoin(gpd.GeoDataFrame(geometry=gpd.points_from_xy(X.ravel(), Y.ravel()), crs=5179), dong[["ADM_NM", "n", "geometry"]], predicate="within")
    cells["w"] = cells.n / cells.groupby("ADM_NM").ADM_NM.transform("size"); cells = cells[cells.w.notna()]
    x, y, w = cells.geometry.x.values, cells.geometry.y.values, cells.w.values
    region = dong.union_all()
    parts = []
    for t in ["childcenter_nat", "school", "library", "open_facility"]:
        g = gpd.read_file(RUN / "data_processed" / f"supply_{t}.gpkg").to_crs(5179); g = g[g.within(region)].copy()
        g["후보명"] = NAME[t](g).values; g["cand_type"] = t
        parts.append(g[["후보명", "cand_type", "소재지도로명주소", "geometry"]])
    cand = pd.concat(parts, ignore_index=True)
    ll = gpd.GeoSeries(cand.geometry, crs=5179).to_crs(4326); cand["lon"] = ll.x.values; cand["lat"] = ll.y.values
    assert cand.후보명.notna().all() and (cand.후보명.astype(str) != "nan").all()
    # ---- B1: 해당 시군구 센터가 게시한 프로그램의 주 운영장소
    own = fp[(fp.key == key) & fp["센터정보"].str.contains(base, na=False)]
    vc = own.venue.value_counts(); main_v = vc[vc >= 5].index.tolist()
    b1 = []
    for v in main_v:
        gc = geocode(v)
        if gc:
            px, py = gpd.GeoSeries(gpd.points_from_xy([float(gc[0]["lon"])], [float(gc[0]["lat"])]), crs=4326).to_crs(5179).iloc[0].coords[0]
            inside = region.contains(gpd.points_from_xy([px], [py])[0])
            b1.append((px, py)) if inside else None
            b1_rows.append(dict(key=key, 운영장소=v, 게시건수=int(vc[v]), lon=gc[0]["lon"], lat=gc[0]["lat"], 지오코딩결과=gc[0]["display_name"],
                                정밀도=gc[0].get("addresstype"), 지역내부=bool(inside)))
        else:
            b1_rows.append(dict(key=key, 운영장소=v, 게시건수=int(vc[v]), 지오코딩결과="실패"))
    for bl, sites in [("B0_기존과 동일(기존 포괄 0)", []), ("B1_가족센터 주 운영장소 포함(참고)", b1)]:
        if bl.startswith("B1") and not sites:
            res_rows.append(dict(key=key, baseline=bl, note="해당 시군구 센터 게시 자료 없음 또는 지오코딩 실패 — 계산 불가")); continue
        S = np.array(sites) if sites else np.empty((0, 2))
        dA = np.min(np.hypot(x[:, None] - S[:, 0][None], y[:, None] - S[:, 1][None]), axis=1) if len(S) else np.full(len(x), np.inf)
        for R in mc["radii_m"]:
            base_cov = float(w[dA <= R].sum()); wu = w * (dA > R)
            cv = (np.hypot(x[None, :] - cand.geometry.x.values[:, None], y[None, :] - cand.geometry.y.values[:, None]) <= R).astype(float)
            gain = cv @ wu; order = np.argsort(-gain, kind="stable"); i = order[0]
            res_rows.append(dict(key=key, baseline=bl, radius_m=R, n_existing_sites=len(S), coverage_before=base_cov / w.sum(),
                                 best_candidate=cand.후보명[i], best_type=cand.cand_type[i], best_address=cand.소재지도로명주소[i],
                                 best_lon=round(cand.lon[i], 6), best_lat=round(cand.lat[i], 6), new_children=float(gain[i]),
                                 coverage_after=(base_cov + gain[i]) / w.sum(), gap_1st_5th=float(gain[order[0]] - gain[order[4]])))
            if R == mc["main_radius_m"]:
                for rk, j in enumerate(order[:5], 1):
                    top_rows.append(dict(key=key, baseline=bl, rank=rk, 후보명=cand.후보명[j], 유형=cand.cand_type[j], 주소=cand.소재지도로명주소[j],
                                         lon=round(cand.lon[j], 6), lat=round(cand.lat[j], 6), new_children=round(float(gain[j]), 1)))
R_ = pd.DataFrame(res_rows); R_.to_csv(OUT / "mclp_representative_fixed.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(top_rows).to_csv(OUT / "mclp_representative_top5_2km.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(b1_rows).to_csv(OUT / "b1_family_center_venues_geocoded.csv", index=False, encoding="utf-8-sig")
# 기존 결과와 수치 일치 확인(B0)
chk = []
for key in REP:
    old = pd.read_csv(RUN / "results" / f"mclp_{key.replace('|', '_')}.csv")
    new = R_[(R_.key == key) & (R_.baseline.str.startswith("B0"))].reset_index(drop=True)
    chk.append(dict(key=key, coverage_after_일치=bool(np.allclose(old.coverage_after.values, new.coverage_after.values)), 기존_best=old.best_candidate.tolist(), 수정_best=new.best_candidate.tolist()))
pd.DataFrame(chk).to_csv(OUT / "mclp_fix_check_vs_original.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 50)
print(pd.DataFrame(chk).to_string(index=False))
print(R_[R_.radius_m == 2000][["key", "baseline", "n_existing_sites", "coverage_before", "best_candidate", "best_type", "new_children", "coverage_after", "gap_1st_5th"]].round(3).to_string(index=False))
print(pd.DataFrame(b1_rows).to_string(index=False))
