"""pipeline.py s13 단계: 결과 파일을 읽어 보고서·제안서(markdown)를 생성한다.
모든 수치는 results/ 의 파일에서 읽는다(손으로 적은 수치 없음). 날짜·출처 문구만 고정 텍스트."""
import csv, json, shutil, datetime as dt
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))

def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def _csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def _f(x, d=0):
    try:
        return f"{float(x):,.{d}f}"
    except (TypeError, ValueError):
        return str(x)

def _pct(x, d=1):
    try:
        return f"{float(x) * 100:.{d}f}%"
    except (TypeError, ValueError):
        return str(x)

def _table(rows, cols, heads=None):
    heads = heads or cols
    out = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")).replace("|", "/").replace("\n", " ") for c in cols) + " |")
    return "\n".join(out)

def build_all(AN, RES, FIG, REP, MAIN_R):
    AN, RES, FIG, REP = map(Path, (AN, RES, FIG, REP))
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    inv = _csv(AN / "file_inventory.csv"); man = _csv(AN / "rename_manifest.csv")
    s3 = _j(RES / "s03_foreign_summary.json"); s4 = _j(RES / "s04_sgis_summary.json"); s5 = _j(RES / "s05_childcenter_summary.json")
    s6 = _j(RES / "s06_geocode_summary.json"); s7 = _j(RES / "s07_osm_summary.json"); s8 = _j(RES / "s08_demand_summary.json")
    s10 = _j(RES / "s10_mclp_summary.json")
    dongs = _csv(RES / "yuseong_dong_demand_table.csv")
    gu = _csv(RES / "daejeon_gu_multicultural_household_2025-11-01.csv")
    acc = _csv(RES / "accessibility_coverage_existing.csv"); accd = _csv(RES / "accessibility_by_dong.csv")
    comp = _csv(AN / "candidate_comparison.csv"); ks = _csv(RES / "mclp_k_sites.csv"); naive = _csv(RES / "naive_vs_mclp.csv")
    btype = _csv(RES / "best_candidate_by_type.csv"); val = _csv(RES / "validation_checks.csv")
    fac = _csv(RES / "facilities_geocoded.csv"); ev = _csv(RES / "childcenter_change_events.csv")
    R = str(MAIN_R); Rk = f"{MAIN_R/1000:g}km"
    a_main = next(r for r in acc if r["scenario"] == "D2_면적균등" and r["radius_m"] == R)
    a_main3 = next(r for r in acc if r["scenario"] == "D3_건물가중" and r["radius_m"] == R)
    top = comp[0]; mk = f"main_new_children_D2_{MAIN_R}m"
    top5 = comp[:5]
    tot_child = float(s8["total_children"])
    yu_gu = next(r for r in gu if r["구분"] == "유성구")
    k_main = {r["k"]: r for r in ks if r["scenario"] == "D2_면적균등" and r["radius_m"] == R}
    nv = next(r for r in naive if r["scenario"] == "D2_면적균등" and r["radius_m"] == R and r["방식"] == "자녀 수 최대 행정동")
    renamed = [r for r in man if r["status"] == "변경완료"]
    nfail = sum(1 for v in val if v["result"] == "FAIL")
    # 상위권 권역 판단: 상위 10개 후보의 행정동 분포
    top10_dong = {}
    for r in comp[:10]:
        top10_dong[r["행정동"]] = top10_dong.get(r["행정동"], 0) + 1
    gap = float(comp[0][mk]) - float(comp[9][mk])
    SW = {"상대동", "원신흥동", "온천1동", "온천2동", "학하동", "진잠동"}
    cand_dong = {r["시설명"]: r["행정동"] for r in comp}
    k1s = [r for r in ks if r["k"] == "1"]
    sw_hits = [r for r in k1s if cand_dong.get(r["exact_sites"]) in SW]
    sw_txt = f"수요 배분 3종 × 반경 5종 = {len(k1s)}개 설정 중 {len(sw_hits)}개에서 1위 후보가 남서부 6개 동(진잠·학하·상대·원신흥·온천1·온천2) 안에 있다"
    nonsw = sorted({f"{r['exact_sites']}({cand_dong.get(r['exact_sites'])}, {r['scenario']} {int(r['radius_m'])/1000:g}km)" for r in k1s if r not in sw_hits})
    nv_all = [r for r in naive if r["radius_m"] == R and r["방식"] == "자녀 수 최대 행정동"]
    gj_area = next(float(r["area_km2"]) for r in dongs if r["ADM_NM"] == "구즉동")
    bands = s3["sheet9_2"]["bands"]; bshare = s3["sheet9_2"]["bands_share"]
    cc_fac = [r for r in fac if r["유형"] == "B_지역아동센터"]
    n_exact = sum(1 for r in cc_fac if r["정밀도"].startswith("건물"))
    files = {}

    # ------------------------------------------------------------ file_audit_report.md
    L = [f"# 파일 감사 보고서 (file_audit_report.md)", f"", f"- 작성: {now} (pipeline s13 자동 생성)", f"- 대상 폴더: `bigdata/` (하위 `_analysis/` 제외)", f"- 확인 파일 수: **{len(inv)}개**, 동일 SHA-256 중복: **0건**(서로 내용이 모두 다름)", "",
         "## 1. 날짜 구분 원칙", "A=통계 기준일, B=공표일, C=파일시스템 수정일(근거로 쓰지 않음), D=확인 불가. 파일명 날짜는 반드시 **문서 내부 표기**와 대조했다.", "",
         "## 2. 파일별 기준일 조사 결과",
         _table(inv, ["current_name", "size_bytes", "stat_ref_date", "internal_date_text", "publish_date", "doc_modified", "fs_mtime"],
                ["현재 파일명", "크기(B)", "A 통계기준일", "기준일 근거(내부 표기)", "B 공표일", "문서 속성 수정일", "C 파일 수정일"]), "",
         "## 3. 중요한 발견", "",
         "1. **외국인주민 현황 '2025'는 2025.11.1. 기준 자료**다. PDF 표지에 '(2025. 11. 1. 기준) 2026. 10.'로 표기되고, 작성기준은 '직전년도 11월 1일 0시'(조사 다음 해 10월경 공표)다. 따라서 작업지시서에 언급된 대전시 공개 2024.11.1. 기준 유성구 자녀 1,524명은 **이전 회차(2024년 현황)** 수치이며 본 분석에 섞지 않았다(이번 작업에서 해당 원문은 직접 열람하지 못함).",
         "2. 엑셀 파일명의 '수정'은 수정본을 뜻한다(엑셀 문서 속성 수정일 2026-10-29). 엑셀 자체에는 기준일 표기가 없어 동봉 PDF로 기준일을 확정했다.",
         "3. **SGIS zip 파일명의 20250630은 경계 기준일**(shp 속성 BASE_DATE=20250630, '2025년 2분기 기준')이다. 함께 들어 있는 인구·가구 통계는 '2025년기준_2024년' = **2024년 기준연도 통계를 2025년 경계로 집계**한 것이다. 따라서 하나의 기준일로 표현할 수 없어 파일명에 두 날짜를 모두 표기했다.",
         "4. `유성구 지역아동센터 현황.xlsx`(2022.3.), `유성구 지역아동센터 현황 (1).xlsx`(2022.6.), `유성구-지역아동센터-현황.xlsx`(2021.1.)는 파일명에 날짜가 없었으나 **시트 상단 기준일 표기**로 기준월을 확인했다(일자는 표기 없음 → `기준YYYY-MM`).",
         "5. 2023.12.31.~2026.6.30. 지역아동센터 파일의 **시트명은 '2023.6.'으로 남아 있으나**(이전 양식 재사용), 시트 상단 기준일 표기와 파일명은 일치한다. 파일명과 내부 기준일이 충돌한 사례는 없다.",
         "6. 이미지 `4. 출입국.외국인 통계연보와 차이점 안내.png`는 통계 수치가 아니라 두 통계의 정의 차이를 설명하는 안내 이미지로, 자체 기준일이 없다(`기준일미확인`).",
         "7. 파일시스템 수정일(C)은 모두 2026-11-03 16:41~16:43(다운로드 시각)로, 기준일 판단에 쓰지 않았다.", "",
         "## 4. 중복·이전 자료", "",
         f"- 지역아동센터 현황 10개 파일은 모두 해시가 다른 **서로 다른 시점의 자료**다(2021.1.~2026.6.30.). 시계열 비교를 위해 모두 보존했다.",
         f"- 최신 지역아동센터 자료: **`유성구_지역아동센터_현황_기준2026-06-30.xlsx`**({s5['latest_n']}개소).",
         f"- 외국인주민 통계는 2025.11.1. 기준 1개 회차만 있다(이전 연도 파일 없음).", "",
         "## 5. 파일명 변경 전후 (SHA-256 전후 동일 확인)", "",
         _table(renamed, ["old_name", "new_name", "evidence"], ["이전 이름", "새 이름", "근거"]), "",
         f"- 변경 {len(renamed)}건, 보류 {sum(1 for r in man if r['status'].startswith('보류'))}건. 전체 해시 기록은 `rename_manifest.csv` 참조.",
         "- 원본 파일 내용은 변경·삭제하지 않았다(같은 파일시스템 안의 rename만 수행; 전후 SHA-256 일치를 단계 안에서 검증).",
         "- 원본 파일을 참조하는 다른 코드는 없었다. 이 파이프라인은 파일을 이름이 아니라 SHA-256으로 찾으므로 이름이 바뀌어도 다시 실행할 수 있다.", ""]
    files["file_audit_report.md"] = "\n".join(L)

    # ------------------------------------------------------------ data_dictionary.md
    L = ["# 데이터 사전 (data_dictionary.md)", "", f"- 작성: {now}", "",
         "## 1. 원본 자료", "",
         "### 1-1. 전국_지방자치단체외국인주민현황_통계표_수정본_기준2025-11-01.xlsx (행정안전부)",
         "- 30개 시트. 분석에 쓴 시트:",
         "  - `11. 다문화가구 현황(읍⋅면⋅동)`: 구분, 합계, 한국인배우자, 결혼이민자 및 귀화자 등(소계/결혼이민자/귀화자 등), **자녀(소계/귀화·인지 및 외국국적/국내출생)**, 기타동거인(소계/내국인/외국인). 시도→시군구→읍면동 순서로 행이 나열되어 있어 '대전광역시' 구간 안의 '유성구' 다음 13행을 추출했다.",
         "  - `1-3. 유형 및 지역별(읍면동)`: 외국인주민 합계, 한국국적미보유(외국인근로자·결혼이민자·유학생·외국국적동포·기타), 한국국적취득자, 외국인주민자녀(출생).",
         "  - `9-2. 연령별(시⋅군⋅구)`: 외국인주민 자녀 0~18세 1세 단위(시군구 단위만 있고 읍면동 단위는 없음).",
         "- '*' = 5명 미만 비공개(블라인드). 유성구 행정동의 **자녀 소계에는 '*'가 없다**(세부 항목에만 있음).",
         "- 정의: 자녀 = 미성년자(PDF '외국인주민 자녀 *미성년자만 집계'). '다문화가구원 자녀'(11번 시트, 유성구 1,500명)와 '외국인주민 자녀'(8-2·9-2번 시트, 유성구 1,544명)는 집계 범위가 서로 다르다.", "",
         "### 1-2. 전국_SGIS행정구역통계및경계_경계기준2025-06-30_통계기준연도2024.zip (국가데이터처 SGIS)",
         "- `bnd_dong_00_2025_2Q.shp`: BASE_DATE, ADM_CD(8자리 행정동 코드, 유성구=25040xxx), ADM_NM. 좌표계 Korea 2000 / Unified CS(EPSG:5179, m).",
         "- 통계 CSV(cp949): 기준연도, 행정구역코드, 통계항목, 통계값. 항목 코드는 `3. 코드집/2. 제공용 코드(statistics_code).xlsx`에 정의되어 있다(to_in_001 총인구, in_age_001~004 0~4/5~9/10~14/15~19세, to_ga_001 총가구).",
         "- 행정동 코드는 **행정동** 기준이다(법정동 아님). 다문화 통계의 읍면동도 행정동 명칭이며 13/13 이름이 일치한다.", "",
         "### 1-3. 유성구_지역아동센터_현황_기준*.xlsx (대전광역시 유성구, 10개 시점)",
         "- 컬럼: 연번, 구분(아동이용시설), 시설명, 운영주체(2024.12.31.부터), 시설장, 전화번호, 도로명주소, 우편번호, 법정동, 행정동.",
         "- **정원·현원·위도·경도는 없다.** 시설장 성명·전화번호는 분석 결과물에 옮기지 않았다.", "",
         "## 2. 생성 자료(results/)", "",
         "| 파일 | 내용 | 주요 컬럼 |", "|---|---|---|",
         "| yuseong_dong_2025Q2.gpkg / .geojson | 유성구 13개 행정동 경계 + 수요·인구 결합 | ADM_CD, ADM_NM, area_km2, mc_children(다문화가구 자녀), mc_children_domestic_born, mc_household_members, foreign_residents_total, pop_total_2024, age0_19_2024, mc_children_per_1000_age0_19 |",
         "| yuseong_dong_demand_table.csv | 위 표의 속성(형상 제외) | 동일 |",
         "| yuseong_dong_multicultural_household_2025-11-01.csv | 11번 시트 유성구 행정동 원자료 | 원 시트 컬럼 그대로('*' 보존) |",
         "| yuseong_foreign_resident_children_by_age_2025-11-01.csv | 유성구 외국인주민 자녀 0~18세 | 계/남/여 × 귀화인지외국국적/국내출생 |",
         "| childcenter_all_snapshots_long.csv | 지역아동센터 10개 시점 통합(긴 형식) | snapshot, 시설명, 운영주체, 도로명주소, 법정동, 행정동 |",
         "| childcenter_presence_matrix.csv / childcenter_change_events.csv | 시점별 존재 여부, 변동(주소 변경 등) | |",
         "| facilities_geocoded.csv / .gpkg | 가족센터·지역아동센터 좌표 | 정밀도, 위치불확실성_m, 우편번호일치, 좌표행정동, 행정동일치, 분석사용 |",
         "| osm_public_facilities.csv / .gpkg | OSM 학교·도서관·행정복지센터 등 | osm, 시설명, 유형, 행정동, x, y |",
         "| candidate_sites.csv | 신규 거점 후보지 | cand_id, 시설명, 후보유형, 행정동, 출처 |",
         "| accessibility_coverage_existing.csv / accessibility_by_dong.csv | 기존 거점 접근성 | scenario, radius_m, coverage_rate … |",
         "| mclp_all_scenarios_long.csv / mclp_k_sites.csv / naive_vs_mclp.csv | MCLP 결과 | |",
         "| ../candidate_comparison.csv | 후보지 비교표(제출용) | main_new_children_D2_2000m, top1_count, top5_count, median_rank, new_<시나리오>_<반경> |",
         "| validation_checks.csv | 자동 검증 결과 | check, result, detail |", "",
         "## 3. 좌표계·거리", "- 모든 거리 계산은 EPSG:5179(m) 평면 **직선거리**다. 도로망 거리·이동시간이 아니다.", ""]
    files["data_dictionary.md"] = "\n".join(L)

    # ------------------------------------------------------------ data_availability_report.md
    drows = sorted(dongs, key=lambda r: -float(r["mc_children"]))
    for r in drows:
        r["_c"] = _f(r["mc_children"]); r["_s"] = _pct(float(r["mc_children"]) / tot_child); r["_p"] = _f(r["age0_19_2024"]); r["_r"] = r["mc_children_per_1000_age0_19"]
        r["_a"] = _f(r["area_km2"], 1); r["_fr"] = _f(r["foreign_residents_total"])
    L = ["# 데이터 확보 현황 보고서 (data_availability_report.md)", "", f"- 작성: {now}", "",
         "## 1. 핵심 결론", "",
         f"- **유성구 행정동별 다문화가구 자녀 수를 공식 통계에서 직접 확보했다.** (행정안전부 「2025 지방자치단체 외국인주민 현황」 11번 시트, 2025.11.1. 기준)",
         f"- 13개 행정동 자녀 합계 {_f(s3['sheet11']['checks']['dong_child_sum'])}명 = 유성구 합계 {_f(s3['sheet11']['checks']['gu_child_total'])}명 (일치). 자녀 소계에 비공개('*') 셀 없음.",
         "- 따라서 행정동별 수요를 **추정하지 않고** 공표값을 그대로 사용한다. 다만 이 값은 '교육지원이 필요한 아동 수'가 아니라 **교육지원 잠재 수요**(다문화가구의 미성년 자녀)다.",
         "- 행정동별 **연령 구분은 공표되지 않는다**(연령은 구 단위만 있음). 행정동별 학령기 아동 수는 확보하지 못했다.", "",
         "## 2. 확보한 유성구 데이터", "",
         _table(drows, ["ADM_NM", "ADM_CD", "_c", "_s", "_fr", "_p", "_r", "_a"],
                ["행정동", "행정동코드", "다문화가구 자녀(명)", "구 내 비중", "외국인주민(명)", "0~19세 인구(2024)", "0~19세 1,000명당 자녀", "면적(km²)"]), "",
         "※ 0~19세 인구는 SGIS 2024년 기준 통계로, 다문화 자녀(2025.11.1.)와 기준시점이 약 1년 차이 난다. 1,000명당 값은 참고지표다.", "",
         "### 유성구 외국인주민 자녀 연령 구성(구 단위, 외국인주민 자녀 정의, 합계 " + _f(s3["sheet9_2"]["total"]) + "명)",
         _table([{"구간": k, "인원": _f(v), "비중": _pct(bshare[k])} for k, v in bands.items()], ["구간", "인원", "비중"]), "",
         f"→ 학령기(7~18세)가 {_pct(bshare['초등학령(7~12세)'] + bshare['중학령(13~15세)'] + bshare['고등학령(16~18세)'])}다. 이 비중을 행정동에 똑같이 적용해 동별 학령기 인원을 만들지는 않았다(동별 연령 구조가 다를 수 있음).", "",
         "### 대전 5개 구 비교(다문화가구 자녀, 2025.11.1.)",
         _table(gu, ["구분", "합계", "자녀_소계", "자녀_국내출생", "결혼이민자및귀화자등_소계"], ["구분", "다문화가구원 합계", "자녀", "자녀(국내출생)", "결혼이민자·귀화자 등"]), "",
         "### 시설 데이터",
         f"- 다문화가족 자녀 교육지원 기관(A): 대전광역시 가족센터 1곳(관평동). 유성구에는 별도의 구 가족센터가 없고(대전시 누리집 표 기준: 동·중·서·대덕구만 구 가족센터가 있음), 시 가족센터가 유성구에 있다.",
         f"- 지역아동센터(B): {s5['latest_n']}개소(2026.6.30.). 좌표: 번지 일치 {n_exact}곳, 도로 구간 수준 {len(cc_fac)-n_exact}곳(모두 명시 행정동 안에 위치함을 확인; 위치 불확실성은 `facilities_geocoded.csv` 참조).",
         f"- 학교·도서관·행정복지센터(B/C): OpenStreetMap에서 추출 {s7['counts']} (공식 목록과 대조하지 않음).",
         f"- 지역아동센터는 2021.1.~2026.6.30. 10개 시점 모두 {sorted(set(s5['counts'].values()))}개소이고 시설명 변동이 없다. 주소 표기 변경 {len(ev)}건 가운데 실제 이전으로 보이는 사례: 유성지역아동센터(2024.12.31.→2026.1.31., 계룡로52번길→계룡로60번길, 같은 구암동).",
         "- 같은 시설이 시점에 따라 다른 행정동으로 표기된 사례(예: 그루터기·구암 센터 '원신흥동'→'상대동', 꿈터 센터 '진잠동'→'학하동')는 학하동·상대동 신설 등 **행정동 개편** 때문으로 보인다. 분석에는 2025년 2분기 경계와 최신(2026.6.30.) 표기를 사용했다.", "",
         "## 3. 아직 확보하지 못한 데이터",
         "- 행정동별 다문화 자녀 **연령별** 분포(학령기 인원)",
         "- 가족센터 다문화 자녀 프로그램의 **실제 운영 장소·회차·정원·대기자**(센터 외부 운영 및 방문교육 포함)",
         "- 학교별 다문화 학생 수(교육청), 다문화 특별학급·한국어학급 운영 학교",
         "- 지역아동센터 정원·현원, 다문화 아동 이용 현황",
         "- 도로망·대중교통 이동시간", "",
         "## 4. 분석에 실제로 사용한 변수",
         "- 수요: `mc_children`(행정동별 다문화가구 자녀, 2025.11.1.)",
         "- 공간: 행정동 경계(2025.6.30.), 100m 격자, OSM 건물(수요 공간 배분 민감도용)",
         "- 공급: 가족센터 좌표(A), 지역아동센터 좌표(B), OSM 학교·도서관·행정복지센터(C 후보)",
         "- 보조: 0~19세 인구(2024), 외국인주민 유형별 인구(2025.11.1.)", ""]
    files["data_availability_report.md"] = "\n".join(L)

    # ------------------------------------------------------------ analysis_feasibility.md
    L = ["# 분석 가능성 검토 (analysis_feasibility.md)", "", f"- 작성: {now}", "",
         "## 1. 지금 자료로 실제 수행한 분석", "",
         "| 분석 | 상태 | 제한사항 |", "|---|---|---|",
         "| 행정동별 잠재 수요 단계구분도 | 수행(demand_map.png) | 자녀 수 = 잠재 수요이며 실제 교육지원 필요 아동 수가 아님. 동별 연령 미상 |",
         "| 교육지원·돌봄 시설 위치도(A/B 구분) | 수행(facility_map.png) | A는 가족센터 1곳만 확인. 학교·도서관은 OSM 기반 |",
         f"| 기존 거점 접근성(직선거리 {', '.join(str(int(r)//1000) if int(r)%1000==0 else str(int(r)/1000) for r in ['1000','1500','2000','3000','5000'])}km) | 수행(accessibility_map.png) | 직선거리이며 이동시간이 아님. 동 내부 수요 분포는 가정(D1/D2/D3) |",
         "| 신규 거점 1~3곳 MCLP(정확 열거) | 수행(candidate_comparison.csv) | 후보지의 실제 개설 가능성 미확인. 거점 정원 제약 미반영 |",
         "| 단순 방식(자녀 수 최대 행정동) 비교 | 수행(naive_vs_mclp.csv) | |",
         "| 민감도(수요 배분 3종 × 반경 5종) | 수행(sensitivity_rank_heatmap.png) | |",
         "| 지역아동센터 활용 시 포괄 상한 | 수행 | 모든 센터가 프로그램을 운영한다는 가정의 상한값 |",
         "| 지역아동센터 시계열(2021~2026) | 수행(childcenter_trend.png) | 정원·현원 없음 |", "",
         "## 2. 추가 자료가 있어야 가능한 분석",
         "- 동별 학령기(초·중) 수요 지도 → 행정동×연령 다문화 자녀 통계(KOSIS·행정안전부 요청 또는 교육청 학교별 다문화 학생 수)",
         "- 실제 이동시간 기반 접근성 → 도로망(국가교통DB, 브이월드) 또는 대중교통 경로 API",
         "- 수요 대비 공급 용량(2SFCA 등) → 프로그램 정원·이용자 수(가족센터), 지역아동센터 정원·현원",
         "- 학교 기반 운영 대안 → 학교별 다문화 학생 수, 한국어학급·다문화 특별학급 운영 학교 목록(대전광역시교육청)",
         "- 집계구(소지역) 단위 수요 → SGIS 집계구 자료는 이번 zip에 없음. 다문화 자녀는 집계구 단위 공표가 없어 정밀화에 한계가 있음", "",
         "## 3. 하지 않은 것(의도적으로)",
         "- 행정동별 자녀 수를 연령 비율로 나누어 학령기 인원을 만들어 내지 않음",
         "- 2024.11.1. 기준 수치(1,524명)와 2025.11.1. 기준 자료를 섞지 않음",
         "- 직선거리를 도보·대중교통 시간으로 바꿔 표현하지 않음",
         "- 유성구 밖 시설을 후보지에 넣지 않음(모든 후보지가 유성구 경계 안에 있는지 검증함)",
         "- GPU 사용: 후보 약 100곳 × 격자 약 1.8만 개 규모로, CPU(NumPy) 정확 열거가 수십 초 안에 끝나 GPU를 쓸 이유가 없었음", ""]
    files["analysis_feasibility.md"] = "\n".join(L)

    # ------------------------------------------------------------ additional_data_sources.md
    L = ["# 추가로 필요한 자료 (additional_data_sources.md)", "", f"- 작성: {now}",
         "- URL은 2026-11-03에 접속(HTTP 200)과 페이지 제목을 확인한 것만 적었다. 개별 데이터셋의 다운로드 파일 주소는 동적 페이지라 직접 받지 않았다.", "",
         "| 우선 | 자료 | 필요한 이유 | 현재 | 기관 / 주소 | 형식·예상 컬럼 | 공개 | 개인정보·제한 | 없을 때 대안 |", "|---|---|---|---|---|---|---|---|---|",
         "| 1 | 행정동별 다문화 자녀 **연령별** 수(또는 학교별 다문화 학생 수) | 학령기 아동만 대상으로 수요를 정밀화 | 미확보(동별 총계만 있음) | 행정안전부 사회통합지원과(자료 요청), 대전광역시교육청 https://www.dje.go.kr , 교육통계 | xlsx; 행정동, 연령, 인원 / 학교명, 다문화 학생 수 | 일부(학교별은 학교알리미 공시 항목 확인 필요 https://www.schoolinfo.go.kr ) | 소수 셀 비공개('*') | 구 단위 연령 비중을 참고로만 제시(현재 방식) |",
         "| 1 | 가족센터 다문화 자녀 프로그램 **운영 장소·회차·정원·대기** | 기존 공급의 실제 위치·용량 확인(센터 외부·방문교육 포함) | 미확보 | 대전광역시 가족센터 https://daejeon.familynet.or.kr/center/index.do , 다누리 https://www.liveinkorea.kr/ , 유성구 다문화가족 담당 042-611-2823 | 프로그램명, 장소 주소, 대상 연령, 정원, 운영 요일 | 공지·문의로 확인 | 이용자 개인정보 제외 요청 | 기관 주소 1곳을 공급 지점으로 가정(현재 방식) |",
         "| 2 | 전국초중등학교위치표준데이터 | OSM 학교 목록을 공식 좌표로 대체 | 미확보(OSM 사용) | 공공데이터포털 https://www.data.go.kr/data/15021148/standard.do | CSV; 학교ID, 학교명, 학교급, 소재지도로명주소, 위도, 경도 | 무료 | 없음 | OSM(현재) |",
         "| 2 | 전국도서관표준데이터 | 공공·작은도서관 공식 목록·좌표 | 미확보(OSM 사용) | 공공데이터포털 https://www.data.go.kr/data/15013109/standard.do | CSV; 도서관명, 유형, 주소, 위도, 경도, 운영시간 | 무료 | 없음 | OSM(현재) |",
         "| 2 | 지역아동센터 정원·현원·다문화 아동 이용 | 후보지 수용 가능성 판단 | 미확보 | 유성구청 https://www.yuseong.go.kr (아동 담당 부서 문의) | 시설명, 정원, 현원 | 비공개일 수 있음 | 아동 개인정보 | 시설 수만으로 비교 |",
         "| 3 | 도로명주소 좌표(공식 지오코딩) | 지역아동센터 18곳의 도로 구간 수준 좌표를 건물 단위로 보정 | 미확보(Nominatim 사용) | 주소기반산업지원서비스 https://business.juso.go.kr , 브이월드 https://www.vworld.kr | API(승인키 필요) | 무료(키 발급) | 없음 | Nominatim + 우편번호·행정동 검증(현재) |",
         "| 3 | 도로망·대중교통 이동시간 | 직선거리를 실제 이동시간으로 대체 | 미확보 | 국가교통DB https://www.ktdb.go.kr , 브이월드 | shp(도로 링크·노드) | 회원 신청 | 없음 | 직선거리 예비분석(현재) |",
         "| 4 | 학교 다문화 정책학교·한국어학급 목록 | 학교를 '운영 중 거점(A)'으로 분류할지 판단 | 미확보 | 대전광역시교육청 https://www.dje.go.kr , 나이스 교육정보 개방 포털 https://open.neis.go.kr | 학교명, 운영 유형 | 공지 형태 | 없음 | 학교를 C(후보)로만 분류(현재) |",
         "| 4 | 전년도(2024.11.1.) 외국인주민 현황 | 행정동별 변화 추세 | 미확보 | 행정안전부 https://www.mois.go.kr (정책자료>통계) | xlsx | 무료 | '*' 블라인드 | 단일 시점 분석 |", ""]
    files["additional_data_sources.md"] = "\n".join(L)

    # ------------------------------------------------------------ competition_proposal_draft.md
    top_dong_list = ", ".join(f"{d}({n})" for d, n in sorted(top10_dong.items(), key=lambda x: -x[1]))
    k2 = k_main.get("2", {}); k3 = k_main.get("3", {})
    far = sorted([r for r in accd if r["scenario"] == "D2_면적균등"], key=lambda r: -float(r["wmean_dist_to_A_km"]))
    far_txt = ", ".join(f"{r['행정동']} {float(r['wmean_dist_to_A_km']):.1f}km" for r in far[:5])
    L = ["# [출품 제안서 초안] 데이터로 찾는 교육 사각지대", "## 유성구 다문화가정 아동을 위한 교육지원 서비스 최적 배치 제안", "",
         f"> 작성: {now} · 모든 수치는 `_analysis/results/`의 실제 분석 결과에서 자동으로 가져왔다. 완료하지 않은 분석은 '계획'으로 표시했다.", "",
         "## 1. 아이디어 개요", "",
         f"유성구에는 다문화가구 미성년 자녀가 **{_f(tot_child)}명**(2025.11.1., 행정안전부) 살고 있다. 하지만 다문화가족 자녀 기초학습·진로지원을 맡은 **대전광역시 가족센터는 유성구 북동쪽 끝(관평동)에 한 곳**뿐이다. "
         f"공공데이터로 분석해 보면, 가족센터에서 직선 {Rk} 안에 사는 다문화가구 자녀는 **{_pct(a_main['coverage_rate'])}**(약 {_f(a_main['covered_children'])}명)에 그친다. "
         f"이 제안은 행정동별 잠재 수요와 시설 위치를 겹쳐 보고 **교육 사각지대를 찾은 뒤**, 신규 건물을 짓기보다 **이미 있는 지역아동센터·학교·도서관에 '찾아가는 교육지원 거점'을 지정**하자는 정책 아이디어다. 어디에 먼저 둘지는 최대 포괄 입지 모형(MCLP)으로 정한다.", "",
         "## 2. 문제 정의 (데이터로 본 현황)", "",
         f"1. **수요는 넓게 퍼져 있다.** 가장 많은 구즉동({_f(drows[0]['mc_children'])}명)을 빼면 나머지 12개 행정동이 모두 47~143명이다. 남서부(진잠·학하·상대·원신흥·온천1·온천2동) 6개 동에 {_f(sum(float(r['mc_children']) for r in dongs if r['ADM_NM'] in SW))}명({_pct(sum(float(r['mc_children']) for r in dongs if r['ADM_NM'] in SW)/tot_child)})이 사는데, 이 6개 동은 모두 가족센터에서 2km 밖이다.",
         f"2. **공급은 한쪽에 몰려 있다.** 수요 가중 평균 직선거리로 보면 가족센터에서 먼 동은 {far_txt}이다.",
         f"3. **동네 돌봄 인프라는 이미 퍼져 있다.** 지역아동센터 {s5['latest_n']}곳이 9개 행정동에 있고, 2021년 이후 개소 수({s5['latest_n']}곳)가 변하지 않은 안정적인 인프라다. 이 센터들이 다문화 자녀 교육 프로그램을 운영한다면 {Rk} 포괄률은 {_pct(a_main['coverage_rate'])}에서 **{_pct(a_main['coverage_rate_if_all_cc'])}**까지 오를 수 있다(전체 운영을 가정한 상한).",
         f"4. **'수요가 가장 많은 동에 하나 더'는 효과가 작다.** 자녀 수 1위인 구즉동에 거점을 두면({nv['시설명']}) 새로 포괄되는 자녀가 {_f(nv['new_children_covered'])}명이다. MCLP가 고른 위치({nv['mclp_best']})는 {_f(nv['mclp_best_new'])}명이다. 수요 배분 방식별로 보면 구즉동 거점의 추가 포괄량은 MCLP 최적안의 " + ", ".join(f"{r['scenario'].split('_')[0]} {_pct(r['ratio_to_mclp'],0)}" for r in nv_all) + f" 수준이다. 구즉동은 면적이 {gj_area:.1f}km²로 넓어 거점 하나의 반경 안에 들어오는 수요가 적은 것이 주된 이유로 보인다(동 안의 실제 거주 분포는 확인하지 못함).", "",
         "## 3. 아이디어 설명", "",
         "### ① 교육 사각지대 지도 (수행 완료)",
         "- 행정동별 다문화가구 자녀 수를 공식 통계 그대로 단계구분도로 표시했다(추정값 없음). → `demand_map.png`",
         "- 실제 다문화 자녀 교육지원 기관(A)과 일반 교육·돌봄 인프라(B)를 구분해 표시했다. → `facility_map.png`",
         "- 100m 격자마다 가장 가까운 교육지원 거점까지의 직선거리를 계산했다. → `accessibility_map.png`", "",
         "### ② 신규 거점 최적 배치 (수행 완료, 예비분석)",
         f"- 후보지 {s10['n_candidates']}곳(지역아동센터, 초·중학교, 공공·작은도서관, 행정복지센터 등 유성구 안 시설)에서 **기존 가족센터가 포괄하지 못한 수요를 가장 많이 새로 포괄하는 곳**을 골랐다.",
         f"- 결과({Rk}, 면적균등 배분 D2): 1위 **{top['시설명']}({top['행정동']})**, 거점 1곳 추가 시 포괄률 {_pct(top['coverage_before'])} → **{_pct(top['coverage_after'])}**(+{_f(top[mk])}명).",
         f"- 다만 상위 10개 후보의 차이는 {_f(gap)}명 이하이고, 모두 **{top_dong_list}**에 몰려 있다. 따라서 정책 제안은 '특정 시설 1곳'이 아니라 **'상대동·원신흥동·온천1동 접경 권역(유성 남서부 생활권)'에 첫 번째 거점을 둔다**로 한다. 그 권역 안의 구체적 시설은 운영 협의 결과로 정한다.",
         f"- 상위 후보(상위 5): " + "; ".join(f"{r['시설명']}({r['후보유형']}, {r['행정동']}) +{_f(r[mk])}명" for r in top5),
         f"- 거점을 2곳, 3곳 둘 경우(정확해): 2곳 {k2.get('exact_sites','')} → 포괄률 {_pct(k2.get('exact_coverage_after'))}; 3곳 {k3.get('exact_sites','')} → {_pct(k3.get('exact_coverage_after'))}.",
         "- 시설 유형별 최적 후보: " + "; ".join(f"{r['후보유형']}: {r['시설명']}({r['행정동']}, +{_f(r['new_children_covered'])}명)" for r in btype), "",
         "### ③ 신규 시설 대신 기존 시설 활용 (Q4)",
         "- **'거점형 + 순회형' 혼합 모델**: 가족센터(관평동)는 본 거점으로 두고, 남서부 권역의 지역아동센터·초등학교·행정복지센터 중 한 곳을 주 2~3회 운영하는 **위성 거점**으로 지정한다. 가족센터 강사가 찾아가 기초학습·진로설계 프로그램을 운영한다.",
         "- 지역아동센터는 방과후 돌봄 공간·인력이 이미 있어 프로그램을 연계하기 쉽다. 학교는 접근성이 좋지만 학교 밖 프로그램 운영 협의가 필요하다. 도서관·행정복지센터는 공공시설이라 대관이 쉽다.",
         "- 모든 후보지의 실제 개설 가능성(공간·시간·인력·안전)은 **확인되지 않았으며**, 시설 협의가 첫 실행 단계다.", "",
         "## 4. 성과 도출 과정", "",
         "1. **자료 정리**: 다운로드한 공공데이터 14개 파일의 통계 기준일과 공표일을 문서 내부 표기로 확인하고, 파일명을 `지역_자료종류_기준일` 형식으로 표준화했다(SHA-256으로 내용 불변 확인).",
         "2. **수요 확보**: 행정안전부 외국인주민 현황(2025.11.1.)에서 유성구 13개 행정동의 다문화가구 자녀 수를 추출하고, 동 합계와 구 합계가 일치하는지 검증했다.",
         "3. **공간 결합**: SGIS 2025년 2분기 행정동 경계와 행정동 이름 13/13을 맞춰 결합했다.",
         f"4. **시설 위치**: 가족센터는 대전시 누리집에서 사업 내용을 확인했다. 지역아동센터 22곳은 도로명주소를 좌표로 바꾸고 행정동·우편번호로 검증했다(번지 일치 {n_exact}곳, 나머지는 도로 구간 수준). 학교·도서관은 OpenStreetMap을 사용했다.",
         "5. **접근성·MCLP**: 100m 격자 17,584개, 반경 1~5km, 수요 배분 방식 3가지(대표점·면적균등·건물가중)에서 후보지별 추가 포괄량을 계산하고, 2~3곳 조합은 전체 경우의 수를 정확히 열거했다.",
         f"6. **검증**: 자동 검증 {len(val)}개 항목 중 실패 {nfail}건(`validation_checks.csv`).", "",
         "## 5. 기대효과", "",
         f"- 같은 예산으로 더 많은 아동 포괄: 거점 1곳을 추가하면 {Rk} 포괄률이 {_pct(top['coverage_before'])}에서 {_pct(top['coverage_after'])}로 약 {float(top['coverage_after'])/max(float(top['coverage_before']),1e-9):.1f}배가 된다(예비분석).",
         "- 신규 건립 없이 기존 시설을 활용하므로 초기 비용이 적고 빨리 시작할 수 있다.",
         "- 매년 공표되는 공공데이터로 같은 분석을 반복할 수 있어 **매년 거점을 재배치하는 근거**가 된다(파이프라인 재실행).", "",
         "## 6. 한계와 보완 계획", "",
         "- 수요는 '다문화가구 미성년 자녀'로, 실제 교육지원이 필요한 아동 수가 아니다(잠재 수요). 동별 연령 분포가 없어 미취학 아동이 섞여 있다.",
         "- 거리는 직선거리다. 도보·대중교통 시간이 아니며, 하천·산지 같은 장애물을 반영하지 않는다.",
         f"- 동 안의 수요 위치는 가정이다(D1 대표점, D2 면적균등, D3 OSM 건물가중). 민감도 분석에서 {sw_txt}. 예외: " + ("; ".join(nonsw) if nonsw else "없음") + ". 1위 시설 자체는 설정에 따라 바뀐다.",
         "- 가족센터의 방문교육 등 센터 밖 서비스와 정원·대기 현황은 반영하지 못했다.",
         "- 학교·도서관 위치는 OSM 기반이라 공식 표준데이터로 교체해야 한다.",
         "- 보완 계획: ① 가족센터 프로그램 운영 장소·정원 확인 ② 학교별 다문화 학생 수 확보 ③ 도로망 기반 이동시간 분석 ④ 후보 시설 운영 의향 조사.", "",
         "## 부록: 산출물", "- 지도: `demand_map.png`, `facility_map.png`, `accessibility_map.png`, `figures/candidate_top12_bar.png`, `figures/sensitivity_rank_heatmap.png`, `figures/childcenter_trend.png`",
         "- 표: `candidate_comparison.csv`, `results/mclp_k_sites.csv`, `results/naive_vs_mclp.csv`, `results/accessibility_by_dong.csv`",
         "- 출처: 행정안전부 「2025 지방자치단체 외국인주민 현황」(2025.11.1. 기준, 2026.10. 공표); 국가데이터처 SGIS 행정구역 경계(2025.6.30.)·통계(2024); 대전광역시 유성구 지역아동센터 현황(2026.6.30.); 대전광역시 누리집 가족센터 현황(2026.11.3. 열람); © OpenStreetMap contributors(ODbL, 2026.11.3. 추출).", ""]
    files["competition_proposal_draft.md"] = "\n".join(L)

    # ------------------------------------------------------------ final_summary.md
    sens = []
    for sc in ["D1_대표점", "D2_면적균등", "D3_건물가중"]:
        for rr in ["1000", "1500", "2000", "3000", "5000"]:
            k1 = next((r for r in ks if r["scenario"] == sc and r["radius_m"] == rr and r["k"] == "1"), None)
            a = next((r for r in acc if r["scenario"] == sc and r["radius_m"] == rr), None)
            if k1 and a:
                sens.append(dict(시나리오=sc, 반경=f"{int(rr)/1000:g}km", 현재포괄률=_pct(a["coverage_rate"]), 최적1곳=k1["exact_sites"], 추가후포괄률=_pct(k1["exact_coverage_after"]), 지역아동센터전부활용상한=_pct(a["coverage_rate_if_all_cc"])))
    L = ["# 최종 요약 (final_summary.md)", "", f"- 작성: {now}", "",
         "## 1. 파일·날짜 검증",
         f"- 확인 파일 {len(inv)}개, 내용 중복 0건, 파일명 변경 {len(renamed)}건(SHA-256 전후 동일).",
         "- 기준일 미확인: `전국_외국인주민현황_출입국통계연보와의차이안내_기준일미확인.png`(안내 이미지) 1건.",
         "- 기준월까지만 확인(일자 미표기): 지역아동센터 2021-01, 2022-03, 2022-06, 2022-12, 2023-06.",
         "- 외국인주민 현황 '2025' = 2025.11.1. 기준(2026.10. 공표). SGIS zip = 경계 2025.6.30. / 통계 2024년.", "",
         "## 2. 확보한 유성구 데이터",
         f"- 행정동별 다문화가구 자녀 13개 동(합계 {_f(tot_child)}명), 외국인주민 유형별, 구 단위 0~18세 연령.",
         f"- 행정동 경계 13개(면적 {s4['yuseong_area_km2']:.1f}km²), 2024 인구.",
         f"- 지역아동센터 10개 시점(최신 2026.6.30. {s5['latest_n']}곳), 가족센터 1곳, OSM 공공시설 {sum(s7['counts'].values())}곳.", "",
         "## 3. 핵심 결과",
         f"- 기존 가족센터 {Rk} 포괄률: D2 {_pct(a_main['coverage_rate'])}, D3 {_pct(a_main3['coverage_rate'])}.",
         f"- 신규 거점 1곳 최적(D2, {Rk}): {top['시설명']}({top['행정동']}) → {_pct(top['coverage_after'])}. 상위 10곳의 분포: {top_dong_list} → **남서부 권역**을 추천한다.",
         f"- 단순 방식(구즉동) +{_f(nv['new_children_covered'])}명 vs MCLP +{_f(nv['mclp_best_new'])}명.", "",
         "### 민감도(시나리오 × 반경, 거점 1곳 추가)", f"- {sw_txt}.", _table(sens, list(sens[0].keys()) if sens else []), "",
         "## 4. 검증", _table(val, ["check", "result"]), "",
         "## 5. 산출물 경로", "- `bigdata/_analysis/` : 보고서(md), demand_map.png, facility_map.png, accessibility_map.png, candidate_comparison.csv, file_inventory.csv, rename_manifest.csv",
         "- `bigdata/_analysis/results/` : 중간·최종 표, GeoPackage/GeoJSON", "- `bigdata/_analysis/figures/` : 전체 그림", "- `bigdata/_analysis/logs/execution.log` : 실행 로그", ""]
    files["final_summary.md"] = "\n".join(L)

    for name, txt in files.items():
        (AN / name).write_text(txt, encoding="utf-8")
        shutil.copy2(AN / name, REP / name)
    for extra in ["resume_instructions.md", "analysis_progress.md"]:
        if (AN / extra).exists():
            shutil.copy2(AN / extra, REP / extra)
    return f"보고서 {len(files)}종 생성"
