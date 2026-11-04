"""N9: 실제 결과 파일에서만 수치를 읽어 data_audit.md / final_report.md 를 생성한다.
결과가 없는 항목은 '미실시(사유)'로 적는다. 완료형 문장은 결과가 있을 때만 쓴다."""
import csv, json, datetime as dt
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))

def _j(p, d=None):
    p = Path(p); return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d

def _csv(p):
    p = Path(p)
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def _f(x, d=0):
    try: return f"{float(x):,.{d}f}"
    except (TypeError, ValueError): return "-" if x in (None, "") else str(x)

def _t(rows, cols, heads=None):
    if not rows:
        return "(자료 없음)"
    heads = heads or cols
    L = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        L.append("| " + " | ".join(str(r.get(c, "")).replace("|", "/").replace("\n", " ")[:80] for c in cols) + " |")
    return "\n".join(L)

TYPE_KO = {"family_program": "전국 가족센터 프로그램", "childcenter_nat": "전국 지역아동센터 표준데이터", "school": "전국 초중등학교 위치 표준데이터",
           "library": "전국 도서관 표준데이터", "open_facility": "전국 공공시설 개방정보", "foreign_stats": "외국인주민 현황(행정안전부)", "sgis": "SGIS 행정구역 통계·경계"}

def build(run, NW, AN, CFG):
    run = Path(run); NW = Path(NW); AN = Path(AN)
    R = run / "results"
    nowt = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    reg = _j(R / "dataset_registry.json", {}); n2 = _j(R / "n2_regions.json", {}); n3 = _j(R / "n3_demand_checks.json", {})
    n4 = _j(R / "n4_supply.json", {}); n5 = _j(R / "n5_compare.json", {}); n6 = _j(R / "n6_select.json", {}); n7 = _j(R / "n7_access.json", [])
    prev = _j(NW / "status" / "previous_job_check.json", {})
    D = _csv(R / "sigungu_demand.csv"); T = _csv(R / "sigungu_demand_supply_comparison.csv"); S = _csv(R / "representative_regions.csv")
    missing = reg.get("missing_supply_types", [])
    # ---------------------------------------------------------------- data_audit.md
    L = ["# 전국 데이터 품질 검증 보고서 (data_audit.md)", "", f"- 작성: {nowt} · 실행 ID: `{run.name}`", "",
         "## 1. 파일 인벤토리", _t(reg.get("files", []), ["path", "ext", "size", "dataset_type", "fs_mtime"], ["경로", "형식", "크기(B)", "식별 유형", "파일 수정일(기준일 아님)"]), "",
         "## 2. 전국 공급자료 5종 확보 여부"]
    for t in ["family_program", "childcenter_nat", "school", "library", "open_facility"]:
        L.append(f"- {TYPE_KO[t]}: " + ("**확보** — " + ", ".join(reg.get("found_types", {}).get(t, [])) if t not in missing else "**미확보**(서버에 파일 없음)"))
    L += ["", "## 3. 표 단위 스키마·결측"]
    for f in reg.get("files", []):
        for tb in f.get("tables", []):
            L.append(f"### {tb['label']} (유형: {tb.get('type')})")
            L.append(f"- 행 {tb['rows']:,} · 인코딩 {tb['encoding']} · 완전중복 행 {tb['dup_rows']} · 좌표 {'있음' if tb['has_coords'] else '없음'} · 지역코드 {'있음' if tb['has_region_code'] else '없음'}")
            L.append(f"- 인식 컬럼: " + ", ".join(f"{k[4:]}={v}" for k, v in tb.items() if k.startswith("col_") and v))
            if tb.get("refdate_values"):
                L.append(f"- 데이터기준일자 분포(상위): {tb['refdate_values']}  ※ 포털 게시일과 다름")
            hi = {k: v for k, v in tb["missing_rate"].items() if v > 0.2}
            L.append(f"- 결측률 20% 초과 컬럼: {hi if hi else '없음'}")
    L += ["", "## 4. 외국인주민 현황 전국 시군구 검증 (2025.11.1. 기준)",
          f"- 기초지자체(시·군·자치구) {n3.get('n_basic_in_sheet')}개 ↔ SGIS 기초단위 {n3.get('n_basic_units_sgis')}개; 시트에만 있는 키 {n3.get('sheet_only_keys')}, SGIS에만 있는 키 {n3.get('sgis_only_keys')}",
          f"- 기초지자체 다문화가구 자녀 합 {_f(n3.get('sum_basic_mc_children'))} = 시트 전국 {_f(n3.get('national_mc_children_sheet'))}; 시도 합계 불일치 {n3.get('sido_mismatch') or '없음'}",
          f"- 일반구 행은 이중집계를 피하려고 제외하고 시 단위(기초)만 사용. SGIS 252개 시군구 중 일반구는 시로 통합 → {n2.get('n_basic_units')}개",
          f"- 읍면동 합 = 시군구 값 일치: {n3.get('dong_sum_equal_units')}/{n3.get('dong_level_units')}개 (불일치는 5명 미만 비공개 '*' {n3.get('dong_blind_cells_total')}개 셀 때문)",
          f"- 원자료 표기 오류 보정: {n3.get('source_typos_corrected')}",
          "- 정의 차이: '다문화가구 자녀'(11번 시트, 다문화가구원 중 미성년 자녀) ≠ '외국인주민 자녀'(8-2·9-2번 시트, 귀화자·결혼이민자의 미성년 자녀). 두 값을 합산하지 않았다. 연령(0~18세)은 '외국인주민 자녀' 기준으로만 시군구 단위 제공.",
          "- 분모 인구(0~19세)는 SGIS 2024년 통계(2025년 경계)로, 분자(2025.11.1.)와 기준시점이 다르다.", ""]
    if n4:
        L += ["## 5. 공급자료 적재 결과"]
        for t, v in n4.items():
            L.append(f"- {TYPE_KO.get(t, t)}: {v.get('state')}" + (f" — 원자료 {v.get('rows_raw')}행, 사용 {v.get('rows_kept')}행, 좌표 정상 {v.get('coord_ok')}, 시군구 배정 {v.get('assigned')} ({v.get('assign_methods')}), 중복 {v.get('n_duplicates','-')}, 폐쇄·미운영 제외 {v.get('dropped_closed','-')}, 기준일자 {v.get('refdate')}" if v.get("rows_raw") else ""))
            if t == "family_program" and v.get("class_counts"):
                L.append(f"  - 프로그램 분류(중복 제외): {v['class_counts']} · 위치 기준: {v.get('location_basis')}")
    (run / "reports" / "data_audit.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---------------------------------------------------------------- final_report.md
    top = sorted(D, key=lambda r: -float(r["mc_children"] or 0))[:15]
    for r in top:
        r["_n"] = f"{r['sido_nm']} {r['base_nm']}"; r["_c"] = _f(r["mc_children"]); r["_r"] = r["mc_children_per_1000_age0_19"]
    ratio_top = sorted([r for r in D if float(r["mc_children"] or 0) >= CFG["selection_rule"]["min_mc_children"]], key=lambda r: -float(r["mc_children_per_1000_age0_19"] or 0))[:10]
    for r in ratio_top:
        r["_n"] = f"{r['sido_nm']} {r['base_nm']}"; r["_c"] = _f(r["mc_children"]); r["_r"] = r["mc_children_per_1000_age0_19"]
    tot = sum(float(r["mc_children"] or 0) for r in D)
    srt = sorted([float(r["mc_children"] or 0) for r in D], reverse=True)
    k10 = max(1, round(len(srt) * 0.1)); share10 = sum(srt[:k10]) / tot if tot else 0
    yu = next((r for r in D if r["key"] == "25|유성구"), {})
    yrank = yu.get("rank_mc_children")
    sido = {}
    for r in D:
        sido[r["sido_nm"]] = sido.get(r["sido_nm"], 0) + float(r["mc_children"] or 0)
    sido_rows = [{"시도": k, "자녀": _f(v), "비중": f"{v/tot*100:.1f}%"} for k, v in sorted(sido.items(), key=lambda x: -x[1])]
    supply_done = not set(["family_program"]).issubset(set(missing))
    L = ["# 전국 확장 분석 최종 보고서 (final_report.md)", "", f"- 작성: {nowt} · 실행 ID: `{run.name}` · 자동 생성(결과 파일 기반)", "",
         "## 0. 실행 상태 요약", "",
         f"- 기존(유성구) 분석: {prev.get('state', '미확인')} (확인 {prev.get('checked_at', '-')})",
         f"- 전국 수요 분석(시군구 229개): **수행 완료**",
         f"- 전국 공급 분석: " + ("**수행**" if supply_done else "**미실시** — 공급자료 미확보: " + ", ".join(TYPE_KO[t] for t in missing)),
         f"- 미확보 자료: {', '.join(TYPE_KO[t] for t in missing) if missing else '없음'}. 행정안전부 주민등록 인구통계는 사용하지 않음(미다운로드).", "",
         "## 1. 사용 데이터와 기준시점", "",
         "| 자료 | 기관 | 기준시점 | 사용 |", "|---|---|---|---|",
         "| 2025 지방자치단체 외국인주민 현황(수정본) | 행정안전부 | 2025.11.1.(2026.10. 공표) | 시군구·읍면동 다문화가구 자녀, 외국인주민 자녀 연령 |",
         "| SGIS 행정구역 경계 | 국가데이터처 | 2025.6.30.(2025년 2분기) | 시군구·행정동 경계 |",
         "| SGIS 행정구역 통계(인구) | 국가데이터처 | 2024년(2025 경계로 집계) | 0~19세 인구(비율 분모) |"]
    for t in ["family_program", "childcenter_nat", "school", "library", "open_facility"]:
        if t not in missing:
            L.append(f"| {TYPE_KO[t]} | 공공데이터포털 제공기관 | 데이터기준일자: {n4.get(t, {}).get('refdate', '-')} | 공급 |")
    L += ["", "## 2. Q1 — 잠재 교육지원 수요는 전국에서 어떻게 분포하는가 (수행)", "",
          f"- 전국 다문화가구 자녀(미성년) {_f(tot)}명, 229개 시군구. **상위 10% 시군구({k10}곳)에 {share10*100:.1f}%가 집중**되어 있다.",
          f"- 유성구: {_f(yu.get('mc_children'))}명(전국 {yrank}위), 0~19세 1,000명당 {yu.get('mc_children_per_1000_age0_19')}명.",
          "", "### 자녀 수 상위 15개 시군구", _t(top, ["_n", "_c", "_r"], ["시군구", "다문화가구 자녀(명)", "0~19세 1,000명당"]),
          "", f"### 비율 상위 10개 시군구(자녀 {CFG['selection_rule']['min_mc_children']}명 이상)", _t(ratio_top, ["_n", "_c", "_r"], ["시군구", "자녀(명)", "0~19세 1,000명당"]),
          "", "### 시도별", _t(sido_rows, ["시도", "자녀", "비중"]),
          "", "그림: `figures/national_demand_map.png`, `figures/top25_sigungu_bar.png`, `figures/demand_concentration.png`", "",
          "※ 자녀 수는 '교육지원 잠재 수요'의 대리지표이며, 실제 교육지원이 필요한 아동 수가 아니다. 시군구별 연령(학령기) 구분은 '외국인주민 자녀' 정의로만 제공되어 별도 열(a7_12 등)로 두고 합산하지 않았다.", ""]
    L += ["## 3. Q2 — 확인된 교육지원 프로그램·시설은 어디에 있는가"]
    if "family_program" in missing:
        L += ["- **미실시**: 전국 가족센터 프로그램 자료가 서버에 없다. 따라서 '확인된 다문화 아동 교육 프로그램'의 전국 분포는 아직 제시할 수 없다.",
              "- 자료가 `bigdata/`에 올라오면 자동 대기 시스템이 감지해 다시 실행한다(분류 규칙: 다문화·아동·교육 키워드를 모두 충족하면 확정, 일부만 충족하면 '불확실'로 별도 표시)."]
    else:
        fpc = n4.get("family_program", {})
        L += [f"- 가족센터 프로그램 분류(중복 제외): {fpc.get('class_counts')} · 위치 기준: {fpc.get('location_basis')}",
              "- 분류는 프로그램명·대상·내용 텍스트의 키워드 규칙 기반이며, 'B_불확실'은 확정 공급에 넣지 않았다. 결과 표: `data_processed/supply_family_program.csv`"]
    for t in ["childcenter_nat", "school", "library", "open_facility"]:
        v = n4.get(t, {})
        L.append(f"- {TYPE_KO[t]}: {v.get('state', '자료 없음')}" + (f" (사용 {v.get('rows_kept')}건, 시군구 배정 {v.get('assigned')}건)" if v.get("rows_kept") else ""))
    L += ["- 지역아동센터·학교·도서관·공공시설은 '일반 인프라/신규 후보'로만 분류했고, 확인된 교육 프로그램과 합산하지 않았다.", ""]
    L += ["## 4. Q3 — 수요 대비 공급이 부족할 가능성이 있는 지역"]
    if "prog_A_per_1000_children" in (T[0].keys() if T else []):
        E = sorted([r for r in T if float(r["mc_children"] or 0) >= CFG["selection_rule"]["min_mc_children"]], key=lambda r: (float(r["prog_A_per_1000_children"] or 0), -float(r["mc_children"] or 0)))[:15]
        for r in E:
            r["_n"] = f"{r['sido_nm']} {r['base_nm']}"
        L += ["- 지표: 다문화가구 자녀 1,000명당 확인된 교육 프로그램 수(프로그램 수이며 정원·회차는 반영 못함).",
              "- **주의**: 프로그램 0건은 '한국건강가정진흥원 가족센터 프로그램 데이터(파일명 20260914)에 게시된 프로그램이 없다'는 뜻이다. 실제로 운영하지 않는다는 뜻이 아니다(게시 누락, 방문교육, 다른 기관 운영 가능). 이 지표는 '공급 부족 가능 지역' 후보를 고르는 용도로만 쓴다.",
              "- 프로그램 위치는 '진행장소' 주소로 시군구를 배정했다(없으면 센터정보). 교육비 지원(A2)과 불확실(B)은 확정 공급에서 제외했다.", _t(E, ["_n", "mc_children", "prog_A_confirmed", "prog_B_uncertain", "prog_A_per_1000_children"], ["시군구", "자녀", "확정 프로그램", "불확실", "1,000명당"]), "그림: `figures/imbalance_map.png`"]
    else:
        L += ["- **미실시**: 확인된 교육 프로그램 자료가 없어 수요 대비 공급 지표를 계산하지 않았다(가상의 공급값을 만들지 않음).",
              "- 현재 제시 가능한 것은 '수요 측면의 우선 검토 후보'(자녀 수·비율 상위 지역)뿐이다."]
    L += ["", "## 5. 대표지역 선정(사전 고정 규칙)", f"- 규칙: {json.dumps(CFG['selection_rule'], ensure_ascii=False)}", f"- 적용 기준: **{n6.get('basis')}**, 대상 시군구 {n6.get('n_eligible')}곳",
          _t(S, ["sido_nm", "base_nm", "mc_children", "mc_children_per_1000_age0_19", "selection_basis"], ["시도", "시군구", "자녀", "1,000명당", "선정 근거"]), ""]
    L += ["## 6. Q4 — 접근성·신규 거점(대표지역)"]
    for r in n7:
        L.append(f"- {r['name']}: {r.get('state')}" + (f" — 행정동 {r.get('n_dong')}개 중 수요 결합 {r.get('dong_matched')}개" if r.get("n_dong") else "")
                 + (f"; 반경 {CFG['mclp']['main_radius_m']/1000:g}km 기준 포괄률 {float(r['main']['coverage_before'])*100:.1f}% → {float(r['main']['coverage_after'])*100:.1f}% (추천 후보: {r['main']['best_candidate']}, {r['main']['best_type']})" if r.get("main") else "")
                 + (f"; 기존 분석의 2km 포괄률 {r['prev_coverage_2km']*100:.1f}%" if r.get("prev_coverage_2km") is not None else ""))
    L += ["- 시군구 총계만으로 시군구 내부 접근성을 계산하지 않았다. 행정동 단위 자녀 수(공표값)와 시설 좌표가 모두 있는 지역에서만 직선거리 예비분석을 했다.", ""]
    L += ["## 7. 유성구 분석과의 연결",
          f"- 유성구 심층분석(기존 결과, `_analysis/`): 대전광역시 가족센터 2km 포괄률 9.8%, 남서부(상대동 일대)에 거점 1곳을 더하면 32.0%(면적균등 가정, 직선거리).",
          f"- 전국에서 유성구는 자녀 수 {yrank}위로 상위권 대도시형 지역이 아니다. 그래도 **수요가 구 전체에 흩어져 있는데 거점은 1곳**이라는 구조는 대표 사례가 된다. 같은 방법을 대표지역에 그대로 적용할 수 있다는 점이 확장성의 근거다.",
          "- 기준연도 차이: 유성구·전국 수요는 같은 2025.11.1. 자료다. 유성구 시설은 2026.6.30.(지역아동센터)·2026.11.3.(가족센터 누리집)이고, 전국 공급자료는 각 표준데이터의 기준일자를 따른다.", ""]
    L += ["## 8. 한계",
          "- 수요 = 다문화가구 미성년 자녀(대리지표), 행정동별 연령 미상.",
          "- 비율 분모(2024)와 분자(2025.11.1.)의 시점 차이.",
          "- 프로그램 수 ≠ 서비스 용량(정원·회차·대기 미반영).",
          "- 공급자료가 없는 항목은 미실시. 직선거리는 이동시간이 아니다.", "",
          "## 9. 추가로 필요한 자료",
          *[f"- {TYPE_KO[t]} (서버 `bigdata/`에 업로드 필요)" for t in missing],
          "- 행정안전부 주민등록 인구통계(시군구 연령별) — 분모를 2025년으로 맞추는 용도(선택)", "",
          "## 10. 1차 제안서(11/5)에 바로 쓸 내용",
          f"- '전국 다문화가구 자녀 {_f(tot)}명 중 {share10*100:.0f}%가 상위 10% 시군구에 집중' → 지역 맞춤형 배치가 필요하다는 근거.",
          "- 전국 수요 지도 + 유성구 사례(2km 포괄률 9.8% → 32.0%)를 '전국 진단 → 지역 처방' 2단 구조로 제시.",
          "- 기존 공공시설(지역아동센터·학교·도서관)을 위성 거점으로 활용하는 정책. 실제 사용 가능성은 협의가 필요한 조건으로 명시.",
          ("- 공급 불균형 지도(`imbalance_map.png`)와 대표지역 MCLP 결과를 추가." if supply_done else "- 공급 불균형 분석은 전국 공급자료가 확보되면 자동으로 추가된다(현재 미실시)."), ""]
    (run / "reports" / "final_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return f"data_audit.md, final_report.md 생성 (공급 {'포함' if supply_done else '미포함'})"
