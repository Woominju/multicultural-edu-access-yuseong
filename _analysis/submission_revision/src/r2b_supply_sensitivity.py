#!/usr/bin/env python3
"""
제출 전 수정(2b) — 전국 시군구 공급 지표 민감도 + 취약지역 순위 안정성 + 수정 지도
입력: r2a 결과(family_program_reclassified.csv), 기존 N5 비교표(수요), basic_units.gpkg   → 출력: submission_revision/nationwide/, figures/
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

BIG = Path(__file__).resolve().parents[3]; AN = BIG / "_analysis"; NW = AN / "nationwide"
OUT = AN / "submission_revision" / "nationwide"; FIG = AN / "submission_revision" / "figures"
MIN_CH = 300; BOTTOM = 20
REP = ["21|강서구", "38|창녕군", "38|하동군", "38|합천군"]

d = pd.read_csv(OUT / "family_program_reclassified.csv", dtype=str, low_memory=False)
d["_dup"] = d["_dup"] == "True"; d["strict_child_edu"] = d["strict_child_edu"] == "True"
d = d[~d._dup & d.key.notna()]
cur = d.status_1103.isin(["진행중", "예정"])
isA = d.edu_class.str.startswith("A_"); isB = d.edu_class.str.startswith("B_")

comp = pd.read_csv(NW / "results" / "sigungu_demand_supply_comparison.csv")
g = comp[["key", "sido_nm", "base_nm", "mc_children", "mc_children_per_1000_age0_19", "prog_A_confirmed"]].copy()
def cnt(mask, col="key"):
    return d[mask].groupby("key").size()
M = {
    "M0_기존(A 전체)": cnt(isA),
    "M1_A·11/3 진행중·예정": cnt(isA & cur),
    "M2_A·아동직접·핵심교육": cnt(d.strict_child_edu),
    "M3_M2·11/3 진행중·예정": cnt(d.strict_child_edu & cur),
    "M4_M2 고유 운영장소": d[d.strict_child_edu & (d.venue.fillna("") != "")].groupby("key").venue.nunique(),
    "M5_A+B(상한)": cnt(isA | isB),
}
for k, s in M.items():
    g[k] = g.key.map(s).fillna(0).astype(int)
g["R_등록 프로그램 전체(분류 무관)"] = g.key.map(cnt(pd.Series(True, index=d.index))).fillna(0).astype(int)
g["R_게시 센터 수"] = g.key.map(d.groupby("key")["센터정보"].nunique()).fillna(0).astype(int)
assert (g["M0_기존(A 전체)"] == g.prog_A_confirmed).all(), "M0 재현 실패"

E = g[g.mc_children >= MIN_CH].copy()
rows = []; ranks = {}
for k in M:
    E[k + "_per1000"] = E[k] / E.mc_children * 1000
    # 낮을수록 취약 — 동률은 평균 순위
    E[k + "_rank"] = E[k + "_per1000"].rank(method="average")
    ranks[k] = E.set_index("key")[k + "_rank"]
base_bottom = set(E.nsmallest(BOTTOM, "M0_기존(A 전체)_per1000", keep="all").key)
for k in M:
    bottom = set(E.nsmallest(BOTTOM, k + "_per1000", keep="all").key)
    rows.append(dict(지표=k, 대상시군구=len(E), 값0인시군구=int((E[k] == 0).sum()),
                     중앙값_per1000=round(float(E[k + "_per1000"].median()), 2),
                     Spearman_vs_M0=round(float(ranks[k].corr(ranks["M0_기존(A 전체)"], method="spearman")), 3),
                     하위20_M0와겹침=len(bottom & base_bottom), 하위20_동률포함수=len(bottom),
                     **{f"순위_{r.split('|')[1]}": f"{ranks[k].get(r):.0f}" for r in REP},
                     **{f"값_{r.split('|')[1]}": int(E.set_index("key").loc[r, k]) for r in REP}))
S = pd.DataFrame(rows)
S.to_csv(OUT / "supply_metric_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
E.sort_values("M3_M2·11/3 진행중·예정_per1000").to_csv(OUT / "sigungu_supply_metrics_revised.csv", index=False, encoding="utf-8-sig")
print(S.to_string(index=False))

# 모든 지표에서 하위 20에 드는 시군구(강건한 '관측 공급 부족' 후보)
inall = None
for k in M:
    b = set(E.nsmallest(BOTTOM, k + "_per1000", keep="all").key)
    inall = b if inall is None else inall & b
robust = E[E.key.isin(inall)][["key", "sido_nm", "base_nm", "mc_children"] + list(M) + ["R_등록 프로그램 전체(분류 무관)", "R_게시 센터 수"]]
robust.to_csv(OUT / "robust_low_supply_candidates.csv", index=False, encoding="utf-8-sig")
print("\n모든 지표(6종)에서 하위 20(동률 포함)에 드는 시군구:", len(robust)); print(robust.to_string(index=False))

# 대표 4지역의 원자료 프로그램 현황(분류 무관)
rep_detail = d[d.key.isin(REP)][["key", "row_no", "센터정보", "프로그램이름", "참여대상", "행사기간", "edu_class", "target_type", "edu_type", "status_1103", "진행장소"]]
rep_detail.sort_values(["key", "edu_class"]).to_csv(OUT / "representative4_program_rows.csv", index=False, encoding="utf-8-sig")
zero_any = g[g["R_등록 프로그램 전체(분류 무관)"] == 0]
summ = {
    "대상": f"다문화가구 자녀 {MIN_CH}명 이상 시군구 {len(E)}곳",
    "등록 프로그램이 하나도 없는 시군구(전체 229곳 중)": zero_any[["sido_nm", "base_nm", "mc_children"]].values.tolist(),
    "대표 4지역 원자료 행 수(분류 무관)": d[d.key.isin(REP)].groupby("key").size().to_dict(),
    "대표 4지역 게시 센터": d[d.key.isin(REP)].groupby("key")["센터정보"].unique().map(list).to_dict(),
    "모든 지표 하위20 공통": robust.key.tolist(),
}
(OUT / "supply_sensitivity_notes.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summ, ensure_ascii=False, indent=1))

# ---------------- 수정 지도: M3(아동 직접·핵심교육·11/3 진행중/예정) per 1,000, 0건은 회색 별도 범주
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, geopandas as gpd
from matplotlib import font_manager as fm
from matplotlib.patches import Patch
for f in (AN / "work" / "fonts").glob("*.ttf"):
    fm.fontManager.addfont(str(f))
matplotlib.rcParams["font.family"] = "NanumGothic"; matplotlib.rcParams["axes.unicode_minus"] = False
bu = gpd.read_file(NW / "data_processed" / "basic_units.gpkg")
G = bu.merge(g, on="key", how="left").merge(E[["key"] + [k + "_per1000" for k in M]], on="key", how="left")
BL = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
fig, axs = plt.subplots(1, 2, figsize=(15, 9.5))
for ax, k, ttl in [(axs[0], "M0_기존(A 전체)", "기존 지표: 키워드 분류 A(2026년 전체 회차)"),
                   (axs[1], "M3_M2·11/3 진행중·예정", "수정 지표: 아동 직접·핵심 교육, 2026-11-03 진행중·예정")]:
    v = G[k + "_per1000"]
    G[G.mc_children < MIN_CH].plot(ax=ax, color="#f4f3ef", edgecolor="white", lw=0.25)
    G[(G.mc_children >= MIN_CH) & (v == 0)].plot(ax=ax, color="#b9b8b1", edgecolor="white", lw=0.25, hatch="////")
    pos = G[(G.mc_children >= MIN_CH) & (v > 0)].copy()
    qs = np.quantile(pos[k + "_per1000"], [0.2, 0.4, 0.6, 0.8])
    pos["bin"] = np.digitize(pos[k + "_per1000"], qs)
    for b in range(5):
        pos[pos.bin == b].plot(ax=ax, color=BL[b], edgecolor="white", lw=0.25)
    edges = [pos[k + "_per1000"].min()] + list(qs) + [pos[k + "_per1000"].max()]
    h = [Patch(fc="#b9b8b1", hatch="////", ec="white", label=f"등록 0건 ({int(((G.mc_children >= MIN_CH) & (v == 0)).sum())}곳) — 실제 0건 아님")] + \
        [Patch(fc=BL[b], label=f"{edges[b]:.1f} – {edges[b+1]:.1f}") for b in range(5)] + [Patch(fc="#f4f3ef", ec="#cccccc", label=f"자녀 {MIN_CH}명 미만(제외)")]
    ax.legend(handles=h, loc="lower right", fontsize=8.5, frameon=False, title="자녀 1,000명당 프로그램 수", title_fontsize=9)
    ax.set_title(ttl, fontsize=12); ax.set_axis_off()
fig.suptitle("다문화가구 자녀 1,000명당 '가족센터 프로그램 데이터에 등록된' 교육 프로그램 수 — 지표 정의에 따라 하위 지역이 달라진다", fontsize=13)
fig.text(0.5, 0.02, "자료: 한국건강가정진흥원 가족센터 프로그램 데이터(2026.9.14. 게시본), 행정안전부 외국인주민 현황(2025.11.1.) · 프로그램 수는 정원·회차·실제 운영을 반영하지 않음",
         ha="center", fontsize=9, color="#6b6a64")
plt.tight_layout(rect=(0, 0.04, 1, 0.95)); fig.savefig(FIG / "national_supply_metric_M0_vs_M3_map.png", dpi=140); plt.close(fig)

# 순위 비교 산점도(M0 vs M3), 대표 4지역 표시
fig, ax = plt.subplots(figsize=(7.5, 7))
ax.scatter(E["M0_기존(A 전체)_rank"], E["M3_M2·11/3 진행중·예정_rank"], s=14, color="#2a78d6", alpha=0.55, lw=0)
for r in REP + ["25|유성구"]:
    e = E.set_index("key").loc[r]
    ax.scatter([e["M0_기존(A 전체)_rank"]], [e["M3_M2·11/3 진행중·예정_rank"]], s=60, color="#eb6834", ec="white", lw=1.5, zorder=3)
    ax.annotate(r.split("|")[1], (e["M0_기존(A 전체)_rank"], e["M3_M2·11/3 진행중·예정_rank"]), xytext=(6, 4), textcoords="offset points", fontsize=9.5, color="#1f1f1e")
ax.plot([0, len(E)], [0, len(E)], color="#c3c2b7", lw=1, ls="--")
ax.set_xlabel("기존 지표(M0) 순위 — 낮을수록 공급 부족 가능"); ax.set_ylabel("수정 지표(M3) 순위")
rho = ranks["M3_M2·11/3 진행중·예정"].corr(ranks["M0_기존(A 전체)"], method="spearman")
ax.set_title(f"시군구 공급 순위: 기존 vs 수정 지표 (자녀 300명 이상 {len(E)}곳, Spearman ρ={rho:.2f})", fontsize=11)
ax.spines[["top", "right"]].set_visible(False); ax.grid(color="#e6e5e0", lw=0.7); ax.set_axisbelow(True)
plt.tight_layout(); fig.savefig(FIG / "national_rank_M0_vs_M3_scatter.png", dpi=150); plt.close(fig)
print("figures saved")
