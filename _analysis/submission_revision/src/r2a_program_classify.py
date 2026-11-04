#!/usr/bin/env python3
"""
제출 전 수정(2a) — 전국 가족센터 프로그램 재분류(운영상태·대상·교육유형·운영장소) + 수작업 검증 표본 추출
입력: 원자료 CSV(읽기 전용) + 기존 N4 결과(supply_family_program.csv: edu_class, key)  → 출력: submission_revision/nationwide/
"""
import re
from pathlib import Path
import numpy as np, pandas as pd

BIG = Path(__file__).resolve().parents[3]; NW = BIG / "_analysis" / "nationwide"
OUT = BIG / "_analysis" / "submission_revision" / "nationwide"; OUT.mkdir(parents=True, exist_ok=True)
REF = pd.Timestamp("2026-11-03"); SNAP = pd.Timestamp("2026-09-14")

raw = pd.read_csv(BIG / "한국건강가정진흥원_가족센터 프로그램 데이터_20260914.csv", dtype=str)
p = pd.read_csv(NW / "data_processed" / "supply_family_program.csv", dtype=str)
assert len(raw) == len(p) and (raw["프로그램이름"].fillna("") == p["프로그램이름"].fillna("")).all() and (raw["진행장소"].fillna("") == p["진행장소"].fillna("")).all()
d = raw.copy()
d["row_no"] = d.index + 2
for c in ["edu_class", "key", "key_method", "_dup"]:
    d[c] = p[c].values
d["_dup"] = d["_dup"] == "True"

# ---- 운영 상태(2026-11-03 기준)
per = d["행사기간"].str.extract(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")
d["start"] = pd.to_datetime(per[0], errors="coerce"); d["end"] = pd.to_datetime(per[1], errors="coerce")
d["status_1103"] = np.select([d.start.isna(), d.end < REF, d.start > REF], ["기간불명", "종료", "예정"], "진행중")

# ---- 대상(아동 직접 / 부모·가족 / 부모 대상)
T = (d["참여대상"].fillna("") + " " + d["프로그램이름"].fillna("")).str.replace(r"\s+", " ", regex=True)
tg = d["참여대상"].fillna("")
CH = r"아동|어린이|초등|중학|중등|고등|청소년|학생|학령|유아|영유아|학년|만\s?\d+\s?세|\d+\s?세|\d+\s?~\s?\d+\s?세|자녀|(초|중|고)\s?\d"
PA = r"부모|보호자|어머니|아버지|엄마|아빠|결혼이민자|이주여성|이민자|여성|부부|가정|가족"
PARENT_OF = r"자녀(를|가)?\s?(둔|있는|양육)|자녀\s?양육|양육\s?중인|부모\s?\d+\s?명|학부모"
CHILD_STRONG = r"자녀\s*\(|초등학생|중학생|고등학생|청소년|아동|만\s?\d+\s?[~-]\s?\d+\s?세|\d+\s?[~-]\s?\d+\s?세|초등\s?(저|고)?학년|학령기"
def target_type(t, n):
    s = t if t.strip() else n
    # '다문화가족 자녀'의 '가족'은 보호자 표기가 아니므로 집단명(…가족/가정)을 먼저 지운다
    s = re.sub(r"(다문화|다문하|외국인|북한\s?이탈|복한\s?이탈|난민|재외동포|베트남|중국|이주배경)\s?(가족|가정)", r"\1", s)
    if re.search(PARENT_OF, s):
        return "부모·보호자 대상"
    ch = re.search(CH, s) is not None; pa = re.search(PA, s) is not None
    if ch and pa:
        return "성인·아동 혼합(부모 동반·결혼이민자 포함)"
    if ch:
        return "아동 직접"
    if pa:
        return "부모·보호자 대상"
    return "불명"
d["target_type"] = [target_type(t, n) for t, n in zip(tg, d["프로그램이름"].fillna(""))]

# ---- 교육 유형(이름+내용; 여러 개면 우선순위 순 첫 번째)
txt = (d["프로그램이름"].fillna("") + " " + d["행사내용"].fillna("")).str.replace(r"\s+", "", regex=True)
TYPES = [("교육비지원(현금성)", r"교육활동비|교육비지원|장학금"),
         ("기초학습", r"기초학습|기초학력|학습지원|숙제|수학|국어|학습멘토|공부방|방과후학습"),
         ("이중언어", r"이중언어|모국어|베트남어|중국어|러시아어|몽골어|필리핀어|캄보디아어|태국어|우즈벡"),
         ("한국어", r"한국어|한글|토픽|TOPIK|언어발달|언어교실|말하기"),
         ("진로", r"진로|진학|직업체험|꿈찾기|커리어|입시"),
         ("독서·기타학습", r"독서|책|코딩|과학|영어|미술교육|교실|교육|학습|공부"),]
def edu_type(s):
    for nm, pat in TYPES:
        if re.search(pat, s):
            return nm
    return "비교육(체험·상담·교류 등)"
d["edu_type"] = txt.map(edu_type)

# ---- 실제 운영장소(도로명주소 정규화: '시도 시군구 도로명 번호' 까지)
def venue(v):
    v = str(v or "")
    m = re.search(r"^(.*?(로|길)\s*\d+(-\d+)?)", v)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
d["venue"] = d["진행장소"].map(venue)

core_edu = d.edu_type.isin(["기초학습", "이중언어", "한국어", "진로"])
d["strict_child_edu"] = d.edu_class.str.startswith("A_") & (d.target_type == "아동 직접") & core_edu
d.to_csv(OUT / "family_program_reclassified.csv", index=False, encoding="utf-8-sig")

A = d[d.edu_class.str.startswith("A_") & ~d._dup]
summary = {
    "A_확정(중복 제외)": len(A),
    "A × 운영상태": A.status_1103.value_counts().to_dict(),
    "A × 대상": A.target_type.value_counts().to_dict(),
    "A × 교육유형": A.edu_type.value_counts().to_dict(),
    "A 중 아동직접·핵심교육(기초학습·이중언어·한국어·진로)": int(A.strict_child_edu.sum()),
    "그중 2026-11-03 진행중/예정": int((A.strict_child_edu & A.status_1103.isin(["진행중", "예정"])).sum()),
    "A 고유 운영장소 수": int(A[A.venue != ""].groupby("key").venue.nunique().sum()),
    "A 운영장소 주소 추출 실패": int((A.venue == "").sum()),
    "원자료 행사 시작월 분포(전체)": d.start.dt.month.value_counts().sort_index().to_dict(),
}
import json
(OUT / "program_reclassification_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))

# ---- 수작업 검증 표본(층화 무작위, seed 20261103)
rng = np.random.default_rng(20261103)
U = d[~d._dup]
parts = []
for cls, n in [("A_확정(다문화·아동·교육)", 50), ("B_불확실", 30), ("C_비교육·비대상", 20)]:
    g = U[U.edu_class == cls]
    parts.append(g.loc[rng.choice(g.index.values, n, replace=False)])
S = pd.concat(parts)[["row_no", "edu_class", "target_type", "edu_type", "status_1103", "프로그램이름", "참여대상", "행사내용", "진행장소"]]
S["검토_다문화아동교육여부"] = ""; S["검토_대상"] = ""; S["검토_메모"] = ""
S.to_csv(OUT / "manual_validation_sample_blank.csv", index=False, encoding="utf-8-sig")
print(f"표본 {len(S)}건 저장")
