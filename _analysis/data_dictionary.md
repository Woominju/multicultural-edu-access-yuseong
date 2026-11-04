# 데이터 사전 (data_dictionary.md)

- 작성: 2026-11-03 17:19 KST

## 1. 원본 자료

### 1-1. 전국_지방자치단체외국인주민현황_통계표_수정본_기준2025-11-01.xlsx (행정안전부)
- 30개 시트. 분석에 쓴 시트:
  - `11. 다문화가구 현황(읍⋅면⋅동)`: 구분, 합계, 한국인배우자, 결혼이민자 및 귀화자 등(소계/결혼이민자/귀화자 등), **자녀(소계/귀화·인지 및 외국국적/국내출생)**, 기타동거인(소계/내국인/외국인). 시도→시군구→읍면동 순서로 행이 나열되어 있어 '대전광역시' 구간 안의 '유성구' 다음 13행을 추출했다.
  - `1-3. 유형 및 지역별(읍면동)`: 외국인주민 합계, 한국국적미보유(외국인근로자·결혼이민자·유학생·외국국적동포·기타), 한국국적취득자, 외국인주민자녀(출생).
  - `9-2. 연령별(시⋅군⋅구)`: 외국인주민 자녀 0~18세 1세 단위(시군구 단위만 있고 읍면동 단위는 없음).
- '*' = 5명 미만 비공개(블라인드). 유성구 행정동의 **자녀 소계에는 '*'가 없다**(세부 항목에만 있음).
- 정의: 자녀 = 미성년자(PDF '외국인주민 자녀 *미성년자만 집계'). '다문화가구원 자녀'(11번 시트, 유성구 1,500명)와 '외국인주민 자녀'(8-2·9-2번 시트, 유성구 1,544명)는 집계 범위가 서로 다르다.

### 1-2. 전국_SGIS행정구역통계및경계_경계기준2025-06-30_통계기준연도2024.zip (국가데이터처 SGIS)
- `bnd_dong_00_2025_2Q.shp`: BASE_DATE, ADM_CD(8자리 행정동 코드, 유성구=25040xxx), ADM_NM. 좌표계 Korea 2000 / Unified CS(EPSG:5179, m).
- 통계 CSV(cp949): 기준연도, 행정구역코드, 통계항목, 통계값. 항목 코드는 `3. 코드집/2. 제공용 코드(statistics_code).xlsx`에 정의되어 있다(to_in_001 총인구, in_age_001~004 0~4/5~9/10~14/15~19세, to_ga_001 총가구).
- 행정동 코드는 **행정동** 기준이다(법정동 아님). 다문화 통계의 읍면동도 행정동 명칭이며 13/13 이름이 일치한다.

### 1-3. 유성구_지역아동센터_현황_기준*.xlsx (대전광역시 유성구, 10개 시점)
- 컬럼: 연번, 구분(아동이용시설), 시설명, 운영주체(2024.12.31.부터), 시설장, 전화번호, 도로명주소, 우편번호, 법정동, 행정동.
- **정원·현원·위도·경도는 없다.** 시설장 성명·전화번호는 분석 결과물에 옮기지 않았다.

## 2. 생성 자료(results/)

| 파일 | 내용 | 주요 컬럼 |
|---|---|---|
| yuseong_dong_2025Q2.gpkg / .geojson | 유성구 13개 행정동 경계 + 수요·인구 결합 | ADM_CD, ADM_NM, area_km2, mc_children(다문화가구 자녀), mc_children_domestic_born, mc_household_members, foreign_residents_total, pop_total_2024, age0_19_2024, mc_children_per_1000_age0_19 |
| yuseong_dong_demand_table.csv | 위 표의 속성(형상 제외) | 동일 |
| yuseong_dong_multicultural_household_2025-11-01.csv | 11번 시트 유성구 행정동 원자료 | 원 시트 컬럼 그대로('*' 보존) |
| yuseong_foreign_resident_children_by_age_2025-11-01.csv | 유성구 외국인주민 자녀 0~18세 | 계/남/여 × 귀화인지외국국적/국내출생 |
| childcenter_all_snapshots_long.csv | 지역아동센터 10개 시점 통합(긴 형식) | snapshot, 시설명, 운영주체, 도로명주소, 법정동, 행정동 |
| childcenter_presence_matrix.csv / childcenter_change_events.csv | 시점별 존재 여부, 변동(주소 변경 등) | |
| facilities_geocoded.csv / .gpkg | 가족센터·지역아동센터 좌표 | 정밀도, 위치불확실성_m, 우편번호일치, 좌표행정동, 행정동일치, 분석사용 |
| osm_public_facilities.csv / .gpkg | OSM 학교·도서관·행정복지센터 등 | osm, 시설명, 유형, 행정동, x, y |
| candidate_sites.csv | 신규 거점 후보지 | cand_id, 시설명, 후보유형, 행정동, 출처 |
| accessibility_coverage_existing.csv / accessibility_by_dong.csv | 기존 거점 접근성 | scenario, radius_m, coverage_rate … |
| mclp_all_scenarios_long.csv / mclp_k_sites.csv / naive_vs_mclp.csv | MCLP 결과 | |
| ../candidate_comparison.csv | 후보지 비교표(제출용) | main_new_children_D2_2000m, top1_count, top5_count, median_rank, new_<시나리오>_<반경> |
| validation_checks.csv | 자동 검증 결과 | check, result, detail |

## 3. 좌표계·거리
- 모든 거리 계산은 EPSG:5179(m) 평면 **직선거리**다. 도로망 거리·이동시간이 아니다.
