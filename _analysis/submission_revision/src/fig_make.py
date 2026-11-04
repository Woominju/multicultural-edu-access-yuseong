#!/usr/bin/env python3
"""
공모전 제출용 시각화 패키지 생성기(읽기 전용 입력 → figures_for_submission/ 에만 출력)
- 값은 모두 검증된 CSV(submission_revision/yuseong, nationwide/results, results)에서 읽는다. 하드코딩한 숫자는 assert 로 CSV와 대조한다.
- 전국 공급 순위·전국 대표지역 MCLP는 사용하지 않는다.
"""
import json, re, shutil, textwrap
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D

AN = Path(__file__).resolve().parents[2]; SR = AN / "submission_revision"; RES = AN / "results"; NW = AN / "nationwide"
OUT = SR / "figures_for_submission"
DIRS = {k: OUT / v for k, v in dict(main="01_main_figures", var="02_variants", info="03_infographics", tab="04_tables_as_figures",
                                     pres="05_presentation_versions", thumb="06_thumbnails_contactsheet", edit="07_editable_assets", rep="reports").items()}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)
for f in (AN / "work" / "fonts").glob("*.ttf"):
    fm.fontManager.addfont(str(f))
matplotlib.rcParams.update({"font.family": "NanumGothic", "axes.unicode_minus": False, "svg.fonttype": "none", "pdf.fonttype": 42})

# ------------------------------------------------------------------ 데이터(검증된 CSV)
nat = pd.read_csv(NW / "results" / "sigungu_demand.csv")
bu = gpd.read_file(NW / "data_processed" / "basic_units.gpkg")[["key", "geometry"]]
bu["geometry"] = bu.geometry.simplify(300)
N = bu.merge(nat, on="key", how="left")
assert len(N) == 229 and N.mc_children.notna().all()
SIDO = N.dissolve(by="sido_cd", as_index=False)[["sido_cd", "geometry"]]
TOTAL = int(nat.mc_children.sum()); assert TOTAL == 312457
srt = nat.sort_values("mc_children", ascending=False).reset_index(drop=True)
TOP_N = int(np.ceil(len(nat) * 0.10)); TOP_SHARE = srt.mc_children.head(TOP_N).sum() / TOTAL
assert TOP_N == 23 and abs(TOP_SHARE - 0.3456) < 0.001
DJ = int(nat[nat.sido_nm == "대전광역시"].mc_children.sum())
YU_RANK = int(srt.index[srt.key == "25|유성구"][0]) + 1

dong = gpd.read_file(RES / "yuseong_dong_2025Q2.gpkg")
sgg = gpd.read_file(RES / "daejeon_sigungu_2025Q2.gpkg").to_crs(5179)
SW = ["진잠동", "학하동", "상대동", "원신흥동", "온천1동", "온천2동"]; NE = ["노은1동", "노은2동", "노은3동"]
YU = int(dong.mc_children.sum()); SWN = int(dong[dong.ADM_NM.isin(SW)].mc_children.sum()); NEN = int(dong[dong.ADM_NM.isin(NE)].mc_children.sum())
assert YU == 1500 and SWN == 658

ex = pd.read_csv(SR / "yuseong" / "existing_sites_revised.csv")
SHORT = {"E0_대전광역시가족센터(관평동)": "대전광역시 가족센터", "E1_마을돌봄 온돌방(장대동)": "장대동 마을돌봄 온돌방",
         "E2_어은초등학교(어은동)": "어은초등학교", "E3_전민초등학교(전민동)": "전민초등학교"}
TYPE = {"E0": "가족센터(본관)", "E1": "마을돌봄 공간", "E2": "초등학교", "E3": "초등학교"}
ex["name"] = ex.site.map(SHORT); ex["sid"] = ex.site.str[:2]; ex["cap"] = ex["정원"].str.extract(r"(\d+)").astype(int)
assert ex.cap.sum() == 40 and len(ex) == 4
cand = pd.read_csv(SR / "yuseong" / "candidate_sites_revised.csv")
cov = pd.read_csv(SR / "yuseong" / "coverage_existing_by_scenario.csv")
sens = pd.read_csv(SR / "yuseong" / "sensitivity_top1_by_scenario.csv")
ks = pd.read_csv(SR / "yuseong" / "mclp_k_sites_by_scenario.csv")
top15 = pd.read_csv(SR / "yuseong" / "mclp_top15_D2_2km_by_scenario.csv")
SC = ["S0_가족센터만(기존)", "S1_가족센터+온돌방", "S2_등록장소 전체(학교 포함)"]
SCL = {SC[0]: "S0 가족센터만", SC[1]: "S1 +온돌방", SC[2]: "S2 등록 장소 4곳"}
SCIDS = {SC[0]: ["E0"], SC[1]: ["E0", "E1"], SC[2]: ["E0", "E1", "E2", "E3"]}
def main_row(sc, dem="D2_면적균등", r=2000):
    return sens[(sens.scenario == sc) & (sens.demand == dem) & (sens.radius_m == r)].iloc[0]
M = {sc: main_row(sc) for sc in SC}
for sc, (b, a, n) in zip(SC, [(9.8, 31.9, 331), (25.5, 36.9, 171), (35.1, 46.5, 171)]):
    assert round(M[sc].coverage_before * 100, 1) == b and round(M[sc].coverage_after * 100, 1) == a and round(M[sc].new_children) == n, sc
K = {(sc, k): ks[(ks.scenario == sc) & (ks.demand == "D2_면적균등") & (ks.radius_m == 2000) & (ks.k == k)].iloc[0] for sc in SC for k in (1, 2, 3)}
assert round(K[(SC[0], 2)].coverage_after * 100, 1) == 42.2 and round(K[(SC[2], 2)].coverage_after * 100, 1) == 56.8

SRC_N = "자료: 행정안전부 「2025 지방자치단체 외국인주민 현황」(2025.11.1. 기준) · 국가데이터처 SGIS 경계(2025.6.30.)"
SRC_Y = "자료: 행정안전부 외국인주민 현황(2025.11.1.) · SGIS 행정동 경계(2025.6.30.)"
SRC_S = "자료: 한국건강가정진흥원 가족센터 프로그램 데이터(2026.9.14. 게시본) · 전국초중등학교위치표준데이터 · 행정안전부 외국인주민 현황(2025.11.1.)"
DEF = "수요 = 다문화가구원 중 미성년 자녀(대리지표; 교육지원 필요 인원 아님)"
COVN = "포괄률 = 거점에서 직선 2km 안에 사는 다문화가구 자녀 비율(행정동 내 면적균등 배분 가정) — 실제 이용률 아님"

# ------------------------------------------------------------------ 스타일
BLUE = ["#eef4fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
STY = {
    "report": dict(bg="white", ink="#1f1f1e", muted="#6b6a64", grid="#e6e5e0", seq=BLUE[1:8], hi="#1c5cab", acc="#1c5cab", acc2="#6da7ec", c3="#9ec5f4",
                   site="#0d366b", cand="#eb6834", t=14, b=10.5, hatch=False, card="#f3f7fd"),
    "present": dict(bg="white", ink="#111111", muted="#55544f", grid="#e6e5e0", seq=BLUE[1:8], hi="#eb6834", acc="#eb6834", acc2="#2a78d6", c3="#1baf7a",
                    site="#2a78d6", cand="#eb6834", t=19, b=13, hatch=False, card="#fff3ec"),
    "info": dict(bg="#fbf9f4", ink="#2b2a27", muted="#77756d", grid="#ebe8df", seq=["#e3f1ec", "#bfe3d5", "#8fcfb6", "#5fb898", "#1baf7a", "#14845c", "#0e5f43"],
                 hi="#eb6834", acc="#1baf7a", acc2="#eb6834", c3="#2a78d6", site="#2a78d6", cand="#eb6834", t=16, b=11.5, hatch=False, card="#ffffff"),
    "bw": dict(bg="white", ink="#000000", muted="#444444", grid="#dddddd", seq=["#f2f2f2", "#d9d9d9", "#bdbdbd", "#969696", "#737373", "#525252", "#252525"],
               hi="#000000", acc="#000000", acc2="#7a7a7a", c3="#bdbdbd", site="#000000", cand="#000000", t=14, b=10.5, hatch=True, card="#f5f5f5"),
}
REG = []  # 생성 목록
MAP6 = {"report": ["#dbe9fa", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95", "#0d366b"], "present": ["#dbe9fa", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95", "#0d366b"],
        "info": ["#e3f1ec", "#a9d9c5", "#5fb898", "#1baf7a", "#0e7a52", "#0a4a33"], "bw": ["#f2f2f2", "#cccccc", "#a3a3a3", "#737373", "#454545", "#111111"]}

def save(fig, cat, name, fid, msg, grade, prop, pres, caution, data, editable=False, hi=False):
    p = DIRS[cat] / f"{name}.png"
    fig.savefig(p, dpi=170, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25)
    files = [p]
    if hi:
        q = DIRS[cat] / f"{name}_print300dpi.png"; fig.savefig(q, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25); files.append(q)
    if editable:
        for ext in ("svg", "pdf"):
            q = DIRS["edit"] / f"{name}.{ext}"; fig.savefig(q, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25); files.append(q)
    plt.close(fig)
    REG.append(dict(file=str(p), extra=";".join(str(f) for f in files[1:]), fig_id=fid, category=cat, message=msg, grade=grade,
                    proposal=prop, presentation=pres, caution=caution, data=data))

def head(fig, S, title, sub=None, y=0.975):
    fig.text(0.02, y, title, fontsize=S["t"], weight="bold", color=S["ink"], va="top")
    if sub:
        fig.text(0.02, y - (S["t"] * 1.75 / 72) / fig.get_figheight(), sub, fontsize=S["b"], color=S["muted"], va="top")

def foot(fig, S, *lines):
    for i, l in enumerate(lines):
        fig.text(0.02, 0.012 + ((S["b"] - 2.5) * 1.55 / 72) / fig.get_figheight() * (len(lines) - 1 - i), l, fontsize=S["b"] - 2.5, color=S["muted"], va="bottom")

def clean(ax, S):
    ax.set_facecolor(S["bg"]); ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(S["muted"]); ax.tick_params(colors=S["ink"], labelsize=S["b"] - 1)
    ax.grid(axis="y", color=S["grid"], lw=0.8); ax.set_axisbelow(True)

def classes(v, edges):
    return np.clip(np.digitize(v, edges[1:-1]), 0, len(edges) - 2)

# ================================================================== A1 전국 수요 지도
def fig_A1(sty, mode, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    fig = plt.figure(figsize=(9, 11) if sty != "present" else (16, 9), facecolor=S["bg"])
    ax = fig.add_axes([0.02, 0.07, 0.96, 0.80] if sty != "present" else [0.0, 0.05, 0.6, 0.83]); ax.set_axis_off(); ax.set_facecolor(S["bg"])
    if mode in ("abs", "top"):
        edges = [0, 300, 600, 1000, 2000, 4000, 8000]; labs = ["300명 미만", "300–599", "600–999", "1,000–1,999", "2,000–3,999", "4,000명 이상"]
        if mode == "abs":
            cl = classes(N.mc_children.values, edges); cols = MAP6[sty]
            for i in range(6):
                N[cl == i].plot(ax=ax, color=cols[i], edgecolor="white" if sty != "bw" else "#ffffff", lw=0.2)
            h = [Patch(fc=cols[i], ec="#999999" if i == 0 else cols[i], label=labs[i]) for i in range(6)]
            ttl = "전국 시군구별 다문화가구 자녀 수"
        else:
            top = N.key.isin(srt.key.head(TOP_N))
            N[~top].plot(ax=ax, color=S["seq"][1], edgecolor="white", lw=0.2)
            N[top].plot(ax=ax, color=S["hi"], edgecolor="white", lw=0.3, hatch="////" if S["hatch"] else None)
            h = [Patch(fc=S["hi"], label=f"상위 10% 시군구 {TOP_N}곳 ({TOP_SHARE:.1%})"), Patch(fc=S["seq"][1], label=f"나머지 {229-TOP_N}곳 ({1-TOP_SHARE:.1%})")]
            ttl = f"상위 {TOP_N}개 시군구에 다문화가구 자녀의 {TOP_SHARE:.1%}가 산다"
    else:  # ratio — 분모 0/결측은 '자료 없음'으로 처리(-inf 방지)
        r = np.where(N.age0_19_2024 > 0, N.mc_children / N.age0_19_2024 * 1000, np.nan)
        edges = [0, 30, 45, 60, 80, 110, 200]; labs = ["30 미만", "30–44", "45–59", "60–79", "80–109", "110 이상"]
        cl = classes(np.nan_to_num(r, nan=-1), edges); cols = MAP6[sty]
        for i in range(6):
            N[(cl == i) & ~np.isnan(r)].plot(ax=ax, color=cols[i], edgecolor="white", lw=0.2)
        if np.isnan(r).any():
            N[np.isnan(r)].plot(ax=ax, color="#cccccc", hatch="xx")
        h = [Patch(fc=cols[i], label=labs[i]) for i in range(6)]
        ttl = "0~19세 인구 1,000명당 다문화가구 자녀 수"
    SIDO.boundary.plot(ax=ax, color=S["ink"] if sty == "bw" else "#ffffff", lw=0.9 if sty != "bw" else 0.5)
    yu = N[N.key == "25|유성구"]
    yu.boundary.plot(ax=ax, color="#eb6834" if sty in ("present", "info") else "#000000", lw=2.2)
    c = yu.geometry.centroid.iloc[0]
    ax.annotate(f"대전 유성구\n{YU:,}명 (전국 {YU_RANK}위)", xy=(c.x, c.y), xytext=(c.x - 230000, c.y + 60000), fontsize=S["b"], color=S["ink"],
                    arrowprops=dict(arrowstyle="-", color=S["muted"], lw=0.8), ha="left")
    if sty == "present":
        fig.text(0.62, 0.86, ttl, fontsize=S["t"], weight="bold", color=S["ink"], va="top", wrap=True)
        fig.text(0.62, 0.70, f"{TOTAL:,}명", fontsize=46, weight="bold", color=S["acc"], va="top")
        fig.text(0.62, 0.60, "전국 다문화가구 미성년 자녀\n229개 기초지자체 합계(원표 전국값과 일치)", fontsize=S["b"], color=S["muted"], va="top")
        fig.text(0.62, 0.46, f"상위 10% 시군구({TOP_N}곳)에 {TOP_SHARE:.1%} 집중", fontsize=S["b"] + 3, color=S["ink"], va="top", weight="bold")
        ax.legend(handles=h, loc="lower left", bbox_to_anchor=(1.02, 0.02), frameon=False, fontsize=S["b"] - 1, title="단위: 명" if mode != "ratio" else "명/1,000명", title_fontsize=S["b"] - 1)
        foot(fig, S, SRC_N, DEF)
    else:
        head(fig, S, ttl, f"전국 {TOTAL:,}명 · 229개 기초지자체(일반구는 시로 통합) · 2025.11.1. 기준")
        ax.legend(handles=h, loc="lower right", frameon=False, fontsize=S["b"] - 1.5, title="단위: 명" if mode != "ratio" else "명/0~19세 1,000명", title_fontsize=S["b"] - 1)
        foot(fig, S, SRC_N + (" · 분모: SGIS 2024년 인구" if mode == "ratio" else ""), DEF)
    msg = {"abs": f"전국 {TOTAL:,}명, 수도권·대도시 중심 분포", "top": f"상위 {TOP_N}곳에 {TOP_SHARE:.1%} 집중", "ratio": "비율 기준으로는 농어촌 군 지역이 높음"}[mode]
    save(fig, cat, name, "A1", msg, grade, prop, pres, "비율지도는 분모(2024)·분자(2025.11.1.) 시점 차이" if mode == "ratio" else "",
         "nationwide/results/sigungu_demand.csv; nationwide/data_processed/basic_units.gpkg", editable=editable, hi=editable)

# ================================================================== A2 집중도
def fig_A2(sty, kind, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    if kind == "bar":
        fig, ax = plt.subplots(figsize=(10, 8.5), facecolor=S["bg"]); fig.subplots_adjust(left=0.24, right=0.95, top=0.86, bottom=0.11)
        t = srt.head(TOP_N).iloc[::-1]
        cols = [S["acc2"] if k == "25|유성구" else S["acc"] for k in t.key]
        ax.barh((t.sido_nm.str.replace("특별자치도|특별자치시|광역시|특별시|도$", "", regex=True) + " " + t.base_nm), t.mc_children, color=cols, height=0.7)
        for i, v in enumerate(t.mc_children):
            ax.text(v + 60, i, f"{v:,.0f}", va="center", fontsize=S["b"] - 2, color=S["ink"])
        clean(ax, S); ax.grid(axis="x", color=S["grid"]); ax.grid(axis="y", visible=False); ax.set_xlabel("다문화가구 자녀(명)", color=S["ink"])
        head(fig, S, f"다문화가구 자녀 수 상위 {TOP_N}개 시군구 — 전국의 {TOP_SHARE:.1%}", f"합계 {srt.mc_children.head(TOP_N).sum():,.0f}명 / 전국 {TOTAL:,}명")
        foot(fig, S, SRC_N, DEF); msg = f"상위 {TOP_N}곳 = {TOP_SHARE:.1%}"
    elif kind == "pareto":
        fig, ax = plt.subplots(figsize=(10, 6.2), facecolor=S["bg"]); fig.subplots_adjust(left=0.09, right=0.95, top=0.83, bottom=0.17)
        x = np.arange(1, len(srt) + 1); cum = srt.mc_children.cumsum() / TOTAL * 100
        ax.plot(x, cum, color=S["acc"], lw=2.4); ax.plot([0, 229], [0, 100], color=S["muted"], lw=1, ls="--")
        for n in (10, TOP_N, 50, 115):
            ax.scatter([n], [cum.iloc[n - 1]], s=46, color=S["acc2"] if n == TOP_N else S["acc"], zorder=3, ec="white")
            ax.annotate(f"상위 {n}곳\n{cum.iloc[n-1]:.1f}%", (n, cum.iloc[n - 1]), xytext=(8, -26), textcoords="offset points", fontsize=S["b"] - 1.5, color=S["ink"])
        ax.text(150, 60, "균등 분포라면(대각선)", color=S["muted"], fontsize=S["b"] - 2, rotation=22)
        clean(ax, S); ax.set_xlim(0, 230); ax.set_ylim(0, 102); ax.set_xlabel("시군구(자녀 수 많은 순)", color=S["ink"]); ax.set_ylabel("누적 비중(%)", color=S["ink"])
        head(fig, S, "다문화가구 자녀 누적 분포(파레토 곡선)", f"229개 시군구 중 상위 {TOP_N}곳({TOP_N/229:.0%})에 {TOP_SHARE:.1%}, 상위 50곳에 {cum.iloc[49]:.1f}%")
        foot(fig, S, SRC_N, DEF); msg = "수요가 소수 시군구에 집중 → 지역 맞춤 배치 필요"
    else:  # info
        fig = plt.figure(figsize=(10, 5.6), facecolor=S["bg"])
        head(fig, S, "수요는 고르게 퍼져 있지 않다")
        ax = fig.add_axes([0.05, 0.30, 0.9, 0.18]); ax.set_axis_off()
        ax.barh([0], [TOP_SHARE], color=S["acc2"], height=0.8); ax.barh([0], [1 - TOP_SHARE], left=[TOP_SHARE], color=S["seq"][2], height=0.8)
        ax.text(TOP_SHARE / 2, 0, f"{TOP_SHARE:.1%}", ha="center", va="center", fontsize=26, weight="bold", color="white")
        ax.text(TOP_SHARE + (1 - TOP_SHARE) / 2, 0, f"{1-TOP_SHARE:.1%}", ha="center", va="center", fontsize=22, color=S["ink"]); ax.set_xlim(0, 1)
        fig.text(0.05 + 0.9 * TOP_SHARE / 2, 0.52, f"상위 {TOP_N}개 시군구\n(전체의 10%)", ha="center", fontsize=S["b"] + 1, color=S["ink"], weight="bold")
        fig.text(0.05 + 0.9 * (TOP_SHARE + (1 - TOP_SHARE) / 2), 0.52, f"나머지 {229-TOP_N}개 시군구", ha="center", fontsize=S["b"] + 1, color=S["ink"])
        fig.text(0.05, 0.74, f"전국 다문화가구 자녀 {TOTAL:,}명", fontsize=S["t"] + 4, weight="bold", color=S["acc"])
        foot(fig, S, SRC_N, DEF); msg = f"10% 지역에 {TOP_SHARE:.1%}"
    save(fig, cat, name, "A2", msg, grade, prop, pres, "", "nationwide/results/sigungu_demand.csv", editable=editable, hi=editable)

# ================================================================== A3 전국→유성구 스토리
def fig_A3(sty, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    fig = plt.figure(figsize=(16, 6.4), facecolor=S["bg"])
    head(fig, S, "전국에서 유성구, 그리고 유성구 안의 권역까지", "같은 자료(행정안전부 외국인주민 현황, 2025.11.1.)로 단계별로 좁혀 본 다문화가구 자녀 수")
    steps = [("전국", f"{TOTAL:,}명", "229개 기초지자체"), ("대전광역시", f"{DJ:,}명", f"전국의 {DJ/TOTAL:.1%}"),
             ("대전 유성구", f"{YU:,}명", f"대전의 {YU/DJ:.1%} · 전국 {YU_RANK}위"), ("유성구 남서부 6개 동", f"{SWN:,}명", f"유성구의 {SWN/YU:.1%}")]
    W = 0.215
    for i, (a, b, c) in enumerate(steps):
        x0 = 0.03 + i * 0.24
        axm = fig.add_axes([x0, 0.30, W, 0.42]); axm.set_axis_off()
        if i == 0:
            N.plot(ax=axm, color=S["seq"][1], lw=0); N[N.sido_cd.astype(str) == "25"].plot(ax=axm, color=S["acc2"])
        elif i == 1:
            sgg.plot(ax=axm, color=S["seq"][1], edgecolor="white"); sgg[sgg.SGG_NM == "유성구"].plot(ax=axm, color=S["acc2"])
        elif i == 2:
            dong.plot(ax=axm, column="mc_children", cmap=matplotlib.colors.ListedColormap(S["seq"][1:6]), edgecolor="white", lw=0.6)
        else:
            dong.plot(ax=axm, color=S["seq"][1], edgecolor="white", lw=0.6); dong[dong.ADM_NM.isin(SW)].plot(ax=axm, color=S["acc2"], edgecolor="white", lw=0.6,
                                                                                                         hatch="///" if S["hatch"] else None)
        axm.set_aspect("equal")
        fig.text(x0 + W / 2, 0.86, a, ha="center", fontsize=S["b"] + 2, color=S["ink"], weight="bold")
        fig.text(x0 + W / 2, 0.22, b, ha="center", fontsize=S["t"] + 6, color=S["acc"], weight="bold")
        fig.text(x0 + W / 2, 0.15, c, ha="center", fontsize=S["b"], color=S["muted"])
        if i < 3:
            fig.patches.append(FancyArrowPatch((x0 + W + 0.003, 0.51), (x0 + 0.237, 0.51), transform=fig.transFigure, arrowstyle="-|>", mutation_scale=22, color=S["muted"]))
    foot(fig, S, SRC_N, DEF + " · 남서부 6개 동 = 진잠·학하·상대·원신흥·온천1·온천2동")
    save(fig, cat, name, "A3", "전국 → 대전 → 유성구 → 남서부로 좁혀지는 문제 정의", grade, prop, pres, "", "sigungu_demand.csv; yuseong_dong_2025Q2.gpkg", editable=editable, hi=editable)

# ================================================================== B1 유성구 수요 지도
def yu_base(ax, S, ctx=True):
    if ctx:
        sgg[sgg.SGG_NM != "유성구"].plot(ax=ax, color="#f1f0eb" if S["bg"] == "white" else "#eeebe2", edgecolor="#cfcdc5", lw=0.6)
    ax.set_axis_off(); ax.set_aspect("equal")
    xmin, ymin, xmax, ymax = dong.total_bounds; ax.set_xlim(xmin - 1500, xmax + 1500); ax.set_ylim(ymin - 1000, ymax + 1000)

def dong_labels(ax, S, detail=True, size=None):
    for _, r in dong.iterrows():
        p = r.geometry.representative_point()
        t = f"{r.ADM_NM}\n{int(r.mc_children)}명" if detail else r.ADM_NM
        ax.text(p.x, p.y, t, ha="center", va="center", fontsize=size or S["b"] - 2.5, color=S["ink"],
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7) if detail else None)

def fig_B1(sty, mode, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    pres_ = sty == "present"
    fig = plt.figure(figsize=(16, 9) if pres_ else (9, 11), facecolor=S["bg"])
    ax = fig.add_axes([0.0, 0.05, 0.58, 0.82] if pres_ else [0.02, 0.07, 0.96, 0.80]); yu_base(ax, S)
    edges = [0, 60, 90, 120, 140, 300]; labs = ["60명 미만", "60–89", "90–119", "120–139", "140명 이상"]
    cl = classes(dong.mc_children.values, edges); cols = S["seq"][1:6]
    if mode == "sw":
        dong.plot(ax=ax, color=S["seq"][1], edgecolor="white", lw=1)
        dong[dong.ADM_NM.isin(SW)].plot(ax=ax, color=S["acc2"] if sty != "report" else S["seq"][5], edgecolor="white", lw=1, hatch="///" if S["hatch"] else None)
        dong[dong.ADM_NM.isin(SW)].dissolve().boundary.plot(ax=ax, color=S["ink"], lw=1.8)
        dong_labels(ax, S, True)
        h = [Patch(fc=S["acc2"] if sty != "report" else S["seq"][5], hatch="///" if S["hatch"] else None, label=f"남서부 6개 동 {SWN}명 ({SWN/YU:.1%})"),
             Patch(fc=S["seq"][1], label=f"나머지 7개 동 {YU-SWN}명")]
        ttl = f"유성구 다문화가구 자녀의 {SWN/YU:.1%}({SWN}명)가 남서부 6개 동에"
    else:
        for i in range(5):
            dong[cl == i].plot(ax=ax, color=cols[i], edgecolor="white", lw=1)
        if mode in ("plain", "detail"):
            dong_labels(ax, S, mode == "detail")
        h = [Patch(fc=cols[i], label=labs[i]) for i in range(5)]
        ttl = "유성구 행정동별 다문화가구 자녀 수"
    leg = ax.legend(handles=h, loc="lower left" if pres_ else "upper left", bbox_to_anchor=(1.0, 0.05) if pres_ else None,
                    frameon=False, fontsize=S["b"] - 1, title="단위: 명", title_fontsize=S["b"] - 1)
    if pres_:
        fig.text(0.60, 0.86, ttl, fontsize=S["t"] - 2, weight="bold", color=S["ink"], va="top", wrap=True)
        fig.text(0.60, 0.68, f"{SWN}명", fontsize=50, weight="bold", color=S["acc"], va="top")
        fig.text(0.60, 0.56, f"남서부 6개 동 = 유성구 {YU:,}명의 {SWN/YU:.1%}\n진잠·학하·상대·원신흥·온천1·온천2동", fontsize=S["b"], color=S["muted"], va="top")
        foot(fig, S, SRC_Y, DEF)
    else:
        head(fig, S, ttl, f"13개 행정동 합계 {YU:,}명 = 유성구 합계(공표값, 추정 아님) · 2025.11.1. 기준")
        foot(fig, S, SRC_Y, DEF + " · 행정동별 연령은 공표되지 않음")
    save(fig, cat, name, "B1", f"남서부 6개 동 {SWN}명({SWN/YU:.1%})" if mode == "sw" else "수요가 13개 동에 흩어져 있음",
         grade, prop, pres, "", "results/yuseong_dong_2025Q2.gpkg", editable=editable, hi=editable)

def fig_B2(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig, ax = plt.subplots(figsize=(10, 6.8) if sty != "present" else (16, 9), facecolor=S["bg"]); fig.subplots_adjust(left=0.13, right=0.95, top=0.84, bottom=0.12)
    d = dong.sort_values("mc_children")
    sw = d.ADM_NM.isin(SW)
    ax.barh(d.ADM_NM, d.mc_children, color=[S["acc2"] if s else S["seq"][2] for s in sw], height=0.68, hatch=None)
    if S["hatch"]:
        for bar, s in zip(ax.patches, sw):
            if s: bar.set_hatch("///")
    for i, v in enumerate(d.mc_children):
        ax.text(v + 3, i, f"{int(v)}", va="center", fontsize=S["b"] - 1, color=S["ink"])
    clean(ax, S); ax.grid(axis="x", color=S["grid"]); ax.grid(axis="y", visible=False); ax.set_xlabel("다문화가구 자녀(명)", color=S["ink"])
    ax.legend(handles=[Patch(fc=S["acc2"], hatch="///" if S["hatch"] else None, label=f"남서부 6개 동 (합계 {SWN}명, {SWN/YU:.1%})"),
                       Patch(fc=S["seq"][2], label="그 밖의 동")], loc="lower right", frameon=False, fontsize=S["b"] - 1)
    head(fig, S, "유성구 행정동별 다문화가구 자녀 수", "최다 구즉동(255명)을 빼면 12개 동이 47~143명으로 고르게 분포")
    foot(fig, S, SRC_Y, DEF)
    save(fig, cat, name, "B2", "수요가 특정 동에 몰리지 않고 흩어져 있음", grade, prop, pres, "", "results/yuseong_dong_demand_table.csv")

def fig_B3(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig = plt.figure(figsize=(14, 8), facecolor=S["bg"])
    head(fig, S, "유성구 다문화가정 아동 교육지원 — 왜 위치 최적화가 필요한가")
    ax = fig.add_axes([0.52, 0.08, 0.46, 0.80]); yu_base(ax, S)
    dong.plot(ax=ax, color=S["seq"][1], edgecolor="white", lw=1); dong[dong.ADM_NM.isin(SW)].plot(ax=ax, color=S["acc2"], edgecolor="white", lw=1)
    e0 = ex[ex.sid == "E0"].iloc[0]; ax.scatter([e0.x], [e0.y], marker="s", s=120, color=S["site"], ec="white", lw=2, zorder=5)
    ax.annotate("가족센터 본관(관평동)", (e0.x, e0.y), xytext=(8, 8), textcoords="offset points", fontsize=S["b"] - 1, color=S["ink"])
    items = [(f"{YU:,}명", "유성구 다문화가구 미성년 자녀\n(2025.11.1. · 전국 69위)"), (f"{SWN}명 · {SWN/YU:.1%}", "남서부 6개 동에 거주\n(진잠·학하·상대·원신흥·온천1·온천2)"),
             ("9.8%", "가족센터 본관에서 직선 2km 안\n(본관만 기준; 등록 장소 포함 시 35.1%)"), ("40명", "2026년 등록된 기초학습 그룹 4곳의\n정원 합계(실제 이용자 수 아님)")]
    for i, (big, small) in enumerate(items):
        y = 0.78 - i * 0.18
        fig.patches.append(FancyBboxPatch((0.03, y - 0.13), 0.44, 0.15, boxstyle="round,pad=0.005,rounding_size=0.015", transform=fig.transFigure, fc=S["card"], ec=S["grid"]))
        fig.text(0.05, y - 0.02, big, fontsize=S["t"] + 6, weight="bold", color=S["acc"], va="top")
        fig.text(0.26, y - 0.025, small, fontsize=S["b"], color=S["ink"], va="top")
    foot(fig, S, SRC_Y + " · 가족센터 프로그램 데이터(2026.9.14.)", "포괄률은 직선거리 기반 잠재 접근성 · 정원은 등록 정원")
    save(fig, cat, name, "B3", "수요는 남서부에, 본관은 북동쪽에", grade, prop, pres, "9.8%는 본관만 기준임을 함께 표기", "yuseong_dong_2025Q2.gpkg; existing_sites_revised.csv")

# ================================================================== C1 기존 교육지원 장소 지도
def draw_sites(ax, S, ids=("E0", "E1", "E2", "E3"), circles=True, labels=True, cap=True, size=None):
    e = ex[ex.sid.isin(ids)]
    for _, r in e.iterrows():
        if circles:
            ax.add_patch(plt.Circle((r.x, r.y), 2000, fill=False, ec=S["site"], lw=1.3, ls="--"))
    ax.scatter(e.x, e.y, marker="s", s=size or 110, color=S["site"], ec="white", lw=2, zorder=6)
    if labels:
        off = {"E0": (10, 6), "E1": (-12, -22), "E2": (10, 6), "E3": (10, -14)}
        ha = {"E0": "left", "E1": "right", "E2": "left", "E3": "left"}
        for _, r in e.iterrows():
            t = r["name"] + (f" (정원 {r.cap})" if cap else "")
            ax.annotate(t, (r.x, r.y), xytext=off[r.sid], textcoords="offset points", ha=ha[r.sid], fontsize=S["b"] - 1, color=S["ink"], weight="bold",
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8))

def fig_C1(sty, mode, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    pres_ = sty == "present"
    fig = plt.figure(figsize=(16, 9) if (pres_ or mode == "table") else (9, 11), facecolor=S["bg"])
    ax = fig.add_axes([0.0, 0.06, 0.55, 0.80] if (pres_ or mode == "table") else [0.02, 0.07, 0.96, 0.80]); yu_base(ax, S)
    dong.plot(ax=ax, color=S["seq"][1], edgecolor="white", lw=1); dong[dong.ADM_NM.isin(SW)].plot(ax=ax, color=S["seq"][2], edgecolor="white", lw=1)
    dong_labels(ax, S, False, S["b"] - 3.5)
    draw_sites(ax, S)
    ax.legend(handles=[Line2D([], [], marker="s", ls="", color=S["site"], ms=10, label="등록 교육지원 장소(기초학습 그룹)"),
                       Line2D([], [], color=S["site"], ls="--", label="반경 2km(직선)"), Patch(fc=S["seq"][2], label="남서부 6개 동")],
              loc="upper left", frameon=False, fontsize=S["b"] - 1.5)
    ttl = "유성구 등록 교육지원 장소 4곳(다문화가족 자녀 기초학습지원)"
    sub = "2026.9.14. 게시본에 행사기간이 2026-11-03을 포함하도록 등록된 그룹 · 정원 합계 40명"
    if pres_ or mode == "table":
        fig.text(0.57, 0.90, ttl, fontsize=S["t"] - (3 if pres_ else 0), weight="bold", color=S["ink"], va="top", wrap=True)
        fig.text(0.57, 0.83, sub, fontsize=S["b"] - 1, color=S["muted"], va="top", wrap=True)
        rows = [("장소", "유형", "행정동", "정원")] + [(r["name"], TYPE[r.sid], r["좌표행정동"], f"{r.cap}명") for _, r in ex.sort_values("sid").iterrows()] + [("합계", "", "", "40명")]
        xs = [0.57, 0.76, 0.86, 0.93]
        for i, row in enumerate(rows):
            y = 0.74 - i * 0.07
            if i == 0 or i == len(rows) - 1:
                fig.patches.append(Rectangle((0.565, y - 0.045), 0.42, 0.06, transform=fig.transFigure, fc=S["card"], ec="none"))
            for x, v in zip(xs, row):
                fig.text(x, y - 0.015, v, fontsize=S["b"] - (0 if pres_ else 1), color=S["ink"], weight="bold" if i in (0, len(rows) - 1) else "normal", va="center")
        fig.text(0.57, 0.24, "· 실제 운영·잔여 정원·외부 아동 참여 가능 여부는 미확인\n· 학교 내 그룹은 재학생 한정 가능성\n· 장대동 온돌방 좌표는 도로 수준(번지 미일치)",
                 fontsize=S["b"] - 1.5, color=S["muted"], va="top")
    else:
        head(fig, S, ttl, sub)
    foot(fig, S, SRC_S, "정원 = 등록 정원(실제 이용자 수 아님) · 원자료 줄 4786·4787·4795·4824")
    save(fig, cat, name, "C1", "본관 외에 학교·마을돌봄 공간 3곳에서 소규모 그룹 운영이 등록됨", grade, prop, pres,
         "운영 확정 아님(등록 일정 기준)", "submission_revision/yuseong/existing_sites_revised.csv", editable=editable, hi=editable)

def fig_C2(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig = plt.figure(figsize=(16, 7), facecolor=S["bg"])
    head(fig, S, "등록된 기초학습지원 장소 4곳 한눈에 보기", "자료상 2026-11-03이 행사기간에 포함된 다문화가족 자녀 기초학습지원 그룹(가족센터 프로그램 데이터, 2026.9.14.)")
    for i, (_, r) in enumerate(ex.sort_values("sid").iterrows()):
        x0 = 0.02 + i * 0.245
        fig.patches.append(FancyBboxPatch((x0, 0.14), 0.225, 0.64, boxstyle="round,pad=0.005,rounding_size=0.02", transform=fig.transFigure, fc=S["card"], ec=S["grid"], lw=1.2))
        fig.patches.append(Rectangle((x0, 0.70), 0.225, 0.08, transform=fig.transFigure, fc=S["site"], ec="none"))
        fig.text(x0 + 0.012, 0.74, r["name"], fontsize=S["b"] + 1.5, color="white", weight="bold", va="center")
        lines = [("유형", TYPE[r.sid]), ("행정동", r["좌표행정동"]), ("주소", "유성구 " + r["도로명주소"]), ("행사기간", r["행사기간"].replace("2026-", "").replace(" ~ ", "~") + " (2026)"),
                 ("대상", textwrap.fill(r["참여대상"], 17)), ("정원", f"{r.cap}명(등록)"), ("좌표", "도로 수준" if "도로" in r["좌표정밀도"] else ("공식 좌표" if "공식" in r["좌표정밀도"] else "번지 일치"))]
        y = 0.65
        for k, v in lines:
            fig.text(x0 + 0.012, y, k, fontsize=S["b"] - 1.5, color=S["muted"], va="top")
            fig.text(x0 + 0.065, y, v, fontsize=S["b"] - 1.5, color=S["ink"], va="top")
            y -= 0.065 + 0.03 * v.count("\n")
    foot(fig, S, "운영 여부·잔여 정원·외부 아동 참여 가능 여부 미확인(학교 내 그룹은 재학생 한정 가능) · 정원 합계 40명 ≠ 이용자 수", SRC_S)
    save(fig, cat, name, "C2", "4곳의 유형·기간·대상·정원", grade, prop, pres, "운영 확정처럼 쓰지 말 것", "existing_sites_revised.csv")

def fig_C3(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig = plt.figure(figsize=(16, 7.5), facecolor=S["bg"])
    head(fig, S, "기존 장소를 어디까지 반영하느냐에 따라 '현재 접근성'이 달라진다", "같은 수요·같은 반경(2km)·같은 방법으로 기존 거점 가정만 바꿔 계산")
    for i, sc in enumerate(SC):
        x0 = 0.02 + i * 0.33
        axm = fig.add_axes([x0, 0.20, 0.14, 0.55]); yu_base(axm, S, ctx=False)
        dong.plot(ax=axm, color=S["seq"][1], edgecolor="white", lw=0.6); draw_sites(axm, S, SCIDS[sc], circles=True, labels=False, size=40)
        fig.text(x0 + 0.15, 0.70, SCL[sc], fontsize=S["b"] + 2, color=S["ink"], weight="bold")
        fig.text(x0 + 0.15, 0.62, {SC[0]: "가족센터 본관 1곳", SC[1]: "본관 + 장대동 온돌방", SC[2]: "본관 + 온돌방 + 어은초 + 전민초"}[sc], fontsize=S["b"] - 1, color=S["muted"])
        fig.text(x0 + 0.15, 0.50, f"{M[sc].coverage_before:.1%}", fontsize=34, color=S["acc"], weight="bold")
        fig.text(x0 + 0.15, 0.43, "2km 안 다문화가구 자녀 비율", fontsize=S["b"] - 1, color=S["ink"])
        fig.text(x0 + 0.15, 0.33, f"최적 1곳 추가 → {M[sc].coverage_after:.1%}\n추가 포괄 약 {M[sc].new_children:.0f}명", fontsize=S["b"], color=S["ink"])
    foot(fig, S, COVN, "S1·S2는 등록 장소가 외부 아동에게도 열려 있다는 가정 — 미확인 · " + SRC_S.split(" · ")[0])
    save(fig, cat, name, "C3", "본관만 가정하면 접근성 과소·추가효과 과대 가능", grade, prop, pres, "", "summary_by_scenario.csv; sensitivity_top1_by_scenario.csv")

# ================================================================== D 시나리오 비교
def fig_D1(sty, kind, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    pres_ = sty == "present"
    fig, ax = plt.subplots(figsize=(16, 9) if pres_ else (10, 6.4), facecolor=S["bg"]); fig.subplots_adjust(left=0.2 if kind == "dumbbell" else 0.09, right=0.95, top=0.80, bottom=0.17)
    b = [M[s].coverage_before * 100 for s in SC]; a = [M[s].coverage_after * 100 for s in SC]; labs = [SCL[s] for s in SC]
    if kind == "grouped":
        x = np.arange(3); w = 0.36
        ax.bar(x - w / 2 - 0.01, b, w, color=S["acc2"] if sty != "report" else S["seq"][2], label="현재(기존 장소)", hatch="..." if S["hatch"] else None)
        ax.bar(x + w / 2 + 0.01, a, w, color=S["acc"], label="+ 최적 신규 거점 1곳")
        for i in range(3):
            ax.text(i - w / 2, b[i] + 1, f"{b[i]:.1f}%", ha="center", fontsize=S["b"], color=S["ink"])
            ax.text(i + w / 2, a[i] + 1, f"{a[i]:.1f}%", ha="center", fontsize=S["b"], color=S["ink"], weight="bold")
        ax.set_xticks(x, labs); ax.set_ylim(0, 60); ax.set_ylabel("2km 포괄률(%)", color=S["ink"]); clean(ax, S)
        ax.legend(frameon=False, fontsize=S["b"] - 1, loc="upper left")
    elif kind == "dumbbell":
        y = np.arange(3)[::-1]
        for i in range(3):
            ax.plot([b[i], a[i]], [y[i], y[i]], color=S["grid"] if sty != "bw" else "#999999", lw=6, solid_capstyle="round", zorder=1)
        ax.scatter(b, y, s=150, color=S["acc2"] if sty != "report" else S["seq"][3], zorder=2, label="현재(기존 장소)", ec="white", lw=1.5)
        ax.scatter(a, y, s=150, color=S["acc"], zorder=3, label="+ 최적 신규 거점 1곳", ec="white", lw=1.5, marker="o" if not S["hatch"] else "D")
        for i in range(3):
            ax.text(b[i], y[i] + 0.2, f"{b[i]:.1f}%", ha="center", fontsize=S["b"], color=S["ink"])
            ax.text(a[i], y[i] + 0.2, f"{a[i]:.1f}%", ha="center", fontsize=S["b"], color=S["ink"], weight="bold")
            ax.text(a[i] + 1.5, y[i], f"+{a[i]-b[i]:.1f}%p", va="center", fontsize=S["b"] - 1, color=S["muted"])
        ax.set_yticks(y, labs); ax.set_xlim(0, 60); ax.set_ylim(-0.6, 2.7); ax.set_xlabel("2km 포괄률(%)", color=S["ink"]); clean(ax, S); ax.grid(axis="x", color=S["grid"]); ax.grid(axis="y", visible=False)
        ax.legend(frameon=False, fontsize=S["b"] - 1, loc="lower right")
    head(fig, S, "기존 장소 가정별 2km 포괄률: 현재 → 신규 거점 1곳 추가", "유성구 다문화가구 자녀 1,500명 기준 · 수요 면적균등 배분(D2) · MCLP 정확해")
    foot(fig, S, COVN, "S1·S2는 등록 장소의 외부 아동 이용 가능을 가정(미확인) · " + SRC_S.split(" · ")[0])
    save(fig, cat, name, "D1", "어떤 가정에서도 1곳 추가 시 잠재 접근성 개선(+11.4~22.1%p)", grade, prop, pres, "포괄률 ≠ 이용률",
         "submission_revision/yuseong/sensitivity_top1_by_scenario.csv", editable=editable, hi=editable)

def fig_D1_arrow(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig = plt.figure(figsize=(14, 7.5), facecolor=S["bg"])
    head(fig, S, "신규 교육지원 거점 1곳 — 잠재 접근성은 얼마나 달라지나", "직선 2km 안에 사는 다문화가구 자녀 비율(포괄률)")
    for i, sc in enumerate(SC):
        y = 0.70 - i * 0.22
        fig.patches.append(FancyBboxPatch((0.03, y - 0.09), 0.94, 0.17, boxstyle="round,pad=0.005,rounding_size=0.02", transform=fig.transFigure, fc=S["card"], ec=S["grid"]))
        fig.text(0.05, y, SCL[sc], fontsize=S["b"] + 2, weight="bold", color=S["ink"], va="center")
        fig.text(0.30, y, f"{M[sc].coverage_before:.1%}", fontsize=30, color=S["muted"], va="center", weight="bold")
        fig.patches.append(FancyArrowPatch((0.45, y), (0.58, y), transform=fig.transFigure, arrowstyle="simple", mutation_scale=30, color=S["acc"]))
        fig.text(0.62, y, f"{M[sc].coverage_after:.1%}", fontsize=34, color=S["acc"], va="center", weight="bold")
        fig.text(0.80, y, f"+약 {M[sc].new_children:.0f}명\n(거리상 포괄)", fontsize=S["b"], color=S["ink"], va="center")
    foot(fig, S, COVN, "추가 포괄 인원은 거리 기준 잠재 수요이며 실제 이용자 수가 아님")
    save(fig, cat, name, "D1", "1곳 추가 효과(시나리오별)", grade, prop, pres, "포괄률 ≠ 이용률", "sensitivity_top1_by_scenario.csv")

def fig_D2(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig, ax = plt.subplots(figsize=(10, 6) if sty != "present" else (16, 9), facecolor=S["bg"]); fig.subplots_adjust(left=0.09, right=0.95, top=0.80, bottom=0.2)
    n = [M[s].new_children for s in SC]
    bars = ax.bar([SCL[s] for s in SC], n, color=[S["acc"], S["acc2"], S["acc2"]], width=0.55)
    for bb, v, s in zip(bars, n, SC):
        ax.text(bb.get_x() + bb.get_width() / 2, v + 6, f"약 {v:.0f}명", ha="center", fontsize=S["b"] + 1, color=S["ink"], weight="bold")
        ax.text(bb.get_x() + bb.get_width() / 2, 12, f"{M[s].best}\n({M[s].best_dong})", ha="center", fontsize=S["b"] - 2.5, color="white")
    clean(ax, S); ax.set_ylim(0, 400); ax.set_ylabel("새로 2km 안에 들어오는 자녀(명)", color=S["ink"])
    head(fig, S, "최적 신규 거점 1곳이 새로 포괄하는 잠재 수요", "기존 장소 범위가 넓을수록(S1·S2) 신규 거점의 추가 효과는 작아진다")
    foot(fig, S, "※ '추가 포괄 수요' = 직선 2km 안에 새로 들어오는 다문화가구 자녀(면적균등 배분) — 실제 서비스 이용자 수가 아님", "정원·이동시간·참여 의사 미반영 · " + SRC_S.split(" · ")[0])
    save(fig, cat, name, "D2", "추가 포괄 331명(S0) vs 171명(S1·S2)", grade, prop, pres, "실제 이용자 아님(주석 포함)", "sensitivity_top1_by_scenario.csv")

SCOL = lambda S: [S["acc"], S["acc2"], S["c3"]]
RAD = [1000, 1500, 2000, 3000, 5000]
def fig_D3(sty, kind, cat, name, grade, prop, pres):
    S = STY[sty]
    mk = ["o", "s", "^"]
    if kind == "line":
        fig, ax = plt.subplots(figsize=(10, 6.4) if sty != "present" else (16, 9), facecolor=S["bg"]); fig.subplots_adjust(left=0.09, right=0.78, top=0.80, bottom=0.17)
        for c, sc, m in zip(SCOL(S), SC, mk):
            t = sens[(sens.scenario == sc) & (sens.demand == "D2_면적균등")].sort_values("radius_m")
            ax.plot(t.radius_m / 1000, t.coverage_before * 100, color=c, ls="--", marker=m, lw=1.6)
            ax.plot(t.radius_m / 1000, t.coverage_after * 100, color=c, ls="-", marker=m, lw=2.4)
            ax.text(5.15, t.coverage_after.iloc[-1] * 100 + {SC[0]: -4, SC[1]: 0, SC[2]: 4}[sc], SCL[sc], color=c if sty != "bw" else S["ink"], fontsize=S["b"] - 1, va="center")
        clean(ax, S); ax.set_xticks([1, 1.5, 2, 3, 5]); ax.set_xlabel("반경(km, 직선)", color=S["ink"]); ax.set_ylabel("포괄률(%)", color=S["ink"]); ax.set_ylim(0, 100)
        ax.legend(handles=[Line2D([], [], color=S["muted"], ls="--", label="현재(기존 장소)"), Line2D([], [], color=S["muted"], ls="-", lw=2.4, label="+ 최적 1곳")]
                  + [Line2D([], [], color=c, marker=m, ls="", label=SCL[s]) for c, s, m in zip(SCOL(S), SC, mk)], frameon=False, fontsize=S["b"] - 2, loc="upper left")
        head(fig, S, "거리 기준(반경)에 따른 포괄률 민감도", "수요 면적균등 배분(D2) · 반경이 바뀌어도 '1곳 추가 시 개선'이라는 방향은 같다")
    elif kind == "panel":
        fig, axs = plt.subplots(1, 3, figsize=(16, 6) if sty != "present" else (16, 9), sharey=True, facecolor=S["bg"]); fig.subplots_adjust(left=0.06, right=0.98, top=0.76, bottom=0.2, wspace=0.08)
        for ax, dem, dl in zip(axs, ["D2_면적균등", "D3_건물가중", "D1_대표점"], ["D2 면적균등 배분", "D3 건물 바닥면적 가중", "D1 행정동 대표점"]):
            for c, sc, m in zip(SCOL(S), SC, mk):
                t = sens[(sens.scenario == sc) & (sens.demand == dem)].sort_values("radius_m")
                ax.plot(t.radius_m / 1000, t.coverage_before * 100, color=c, ls="--", marker=m, lw=1.4)
                ax.plot(t.radius_m / 1000, t.coverage_after * 100, color=c, ls="-", marker=m, lw=2.2, label=SCL[sc])
            clean(ax, S); ax.set_title(dl, fontsize=S["b"] + 1, color=S["ink"]); ax.set_xticks([1, 2, 3, 5]); ax.set_xlabel("반경(km)", color=S["ink"])
        axs[0].set_ylabel("포괄률(%)", color=S["ink"]); axs[0].legend(frameon=False, fontsize=S["b"] - 2, loc="upper left", title="실선 +1곳 · 점선 현재", title_fontsize=S["b"] - 2)
        head(fig, S, "수요 배분 방식 × 반경 민감도", "행정동 안 거주 분포를 모르기 때문에 세 가지 배분 가정으로 확인")
    else:  # compact heat-table: after coverage
        fig, ax = plt.subplots(figsize=(9, 4.6), facecolor=S["bg"]); fig.subplots_adjust(left=0.24, right=0.97, top=0.72, bottom=0.2)
        Z = np.array([[sens[(sens.scenario == sc) & (sens.demand == "D2_면적균등") & (sens.radius_m == r)].coverage_after.iloc[0] * 100 for r in RAD] for sc in SC])
        Z0 = np.array([[sens[(sens.scenario == sc) & (sens.demand == "D2_면적균등") & (sens.radius_m == r)].coverage_before.iloc[0] * 100 for r in RAD] for sc in SC])
        ax.imshow(Z, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("s", S["seq"][:6]), vmin=0, vmax=100, aspect="auto")
        for i in range(3):
            for j in range(5):
                ax.text(j, i, f"{Z0[i,j]:.0f}→{Z[i,j]:.0f}", ha="center", va="center", fontsize=S["b"] - 0.5, color="white" if Z[i, j] > 55 else S["ink"])
        ax.set_xticks(range(5), [f"{r/1000:g}km" for r in RAD]); ax.set_yticks(range(3), [SCL[s] for s in SC]); ax.tick_params(length=0, labelsize=S["b"] - 1)
        for sp in ax.spines.values(): sp.set_visible(False)
        head(fig, S, "포괄률(%) 현재 → +1곳, 반경별", "D2 면적균등 배분")
    foot(fig, S, COVN.replace("2km", "r km"), "MCLP 정확해 · " + SRC_S.split(" · ")[0])
    save(fig, cat, name, "D3", "반경·수요배분이 달라도 개선 방향은 동일, 크기는 달라짐", grade, prop, pres, "", "sensitivity_top1_by_scenario.csv")

# ================================================================== E 추천 지도
def rec_map(ax, S, sc, k=1, top=True, region=False):
    yu_base(ax, S)
    if region:
        dong.plot(ax=ax, color="#dfe5ec" if not S["hatch"] else "#ffffff", edgecolor="#9aa3ad", lw=0.8)
        dong.dissolve().boundary.plot(ax=ax, color=S["ink"], lw=1.0)
        dong[dong.ADM_NM.isin(SW)].plot(ax=ax, color=S["seq"][3] if not S["hatch"] else "#bdbdbd", edgecolor="white", lw=1, hatch="///" if S["hatch"] else None)
        dong[dong.ADM_NM.isin(NE)].plot(ax=ax, color=S["seq"][1] if not S["hatch"] else "#e0e0e0", edgecolor="white", lw=1, hatch="..." if S["hatch"] else None)
        dong[dong.ADM_NM.isin(SW)].dissolve().boundary.plot(ax=ax, color=S["ink"], lw=1.6)
        dong[dong.ADM_NM.isin(NE)].dissolve().boundary.plot(ax=ax, color=S["ink"], lw=1.2, ls="--")
    else:
        dong.plot(ax=ax, column="mc_children", cmap=matplotlib.colors.ListedColormap(S["seq"][0:5]), edgecolor="white", lw=0.9)
    draw_sites(ax, S, SCIDS[sc], circles=True, labels=False, size=80)
    if top:
        t = top15[top15.scenario == sc].head(10)
        c10 = cand.set_index("시설명").loc[t.시설명]
        ax.scatter(c10.x, c10.y, s=26, color=S["cand"], alpha=0.55, lw=0, zorder=5)
    sites = K[(sc, k)].sites.split(" + ")
    for s in sites:
        c = cand[cand.시설명 == s].iloc[0]
        ax.add_patch(plt.Circle((c.x, c.y), 2000, fill=False, ec=S["cand"], lw=1.8))
        ax.scatter([c.x], [c.y], marker="*", s=300, color=S["cand"], ec="white", lw=1.3, zorder=7)
    return sites

def sty_is_bw(S):
    return S["hatch"]

def fig_E1_panel(sty, k, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    fig, axs = plt.subplots(1, 3, figsize=(18, 8.2), facecolor=S["bg"]); fig.subplots_adjust(left=0.01, right=0.99, top=0.78, bottom=0.12, wspace=0.02)
    for ax, sc in zip(axs, SC):
        sites = rec_map(ax, S, sc, k=k)
        r = K[(sc, k)]
        ax.set_title(f"{SCL[sc]}\n현재 {r.coverage_before:.1%} → {k}곳 추가 {r.coverage_after:.1%}", fontsize=S["b"] + 2, color=S["ink"])
        ax.text(0.02, 0.02, "추가 거점: " + "\n".join(f"{s} ({d})" for s, d in zip(sites, r.dongs.split(" + "))), transform=ax.transAxes, fontsize=S["b"] - 2.5, color=S["ink"], va="bottom")
    fig.legend(handles=[Line2D([], [], marker="s", ls="", color=S["site"], ms=9, label="등록 교육지원 장소(시나리오별)"),
                        Line2D([], [], marker="*", ls="", color=S["cand"], ms=15, label=f"MCLP 최적 신규 거점 {k}곳"),
                        Line2D([], [], marker="o", ls="", color=S["cand"], alpha=0.55, ms=6, label="상위 10 후보(1곳 기준)"),
                        Line2D([], [], color=S["muted"], ls="--", label="반경 2km")], loc="lower center", ncol=4, frameon=False, fontsize=S["b"] - 1, bbox_to_anchor=(0.5, 0.06))
    head(fig, S, f"유성구 신규 교육지원 거점 {k}곳 최적 위치(수정 후)", "기존 장소 가정 3가지 · 직선 2km · 수요 면적균등 배분 · 바탕색 = 행정동 다문화가구 자녀 수")
    foot(fig, S, "MCLP 결과는 '협의를 시작할 권역'의 우선순위이며 특정 시설 확정이 아님 · 후보 시설 사용 가능성(공간·인력·학교 협조) 미확인", COVN)
    save(fig, cat, name, "E1" if k == 1 else "E3", f"{k}곳: 모든 가정에서 남서부" + (" + 노은 권역" if k == 2 else "") + " 선택", grade, prop, pres, "시설 확정 아님",
         "mclp_k_sites_by_scenario.csv; candidate_sites_revised.csv; existing_sites_revised.csv", editable=editable, hi=editable)

def fig_E1_single(sty, sc, cat, name, grade, prop, pres):
    S = STY[sty]
    fig = plt.figure(figsize=(9, 11) if sty != "present" else (16, 9), facecolor=S["bg"])
    ax = fig.add_axes([0.02, 0.08, 0.96, 0.78] if sty != "present" else [0.0, 0.05, 0.58, 0.83])
    rec_map(ax, S, sc, 1)
    t = top15[top15.scenario == sc].head(5)
    txt = "\n".join(f"{int(r['rank'])}. {r.시설명} ({r.행정동}) +{r.new_children:.0f}명" for _, r in t.iterrows())
    r = K[(sc, 1)]
    if sty == "present":
        fig.text(0.60, 0.88, f"{SCL[sc]}: 최적 신규 거점 1곳", fontsize=S["t"], weight="bold", color=S["ink"], va="top")
        fig.text(0.60, 0.76, f"{r.coverage_before:.1%} → {r.coverage_after:.1%}", fontsize=40, weight="bold", color=S["acc"], va="top")
        fig.text(0.60, 0.64, "2km 포괄률(직선거리, 잠재 접근성)", fontsize=S["b"], color=S["muted"], va="top")
        fig.text(0.60, 0.55, "상위 5 후보(차이가 작아 '권역'으로 추천)\n" + txt, fontsize=S["b"] - 1, color=S["ink"], va="top")
    else:
        head(fig, S, f"{SCL[sc]} — 신규 거점 1곳 최적 위치", f"2km 포괄률 {r.coverage_before:.1%} → {r.coverage_after:.1%} · 상위 후보 간 차이가 작아 권역 단위로 해석")
        ax.text(0.02, 0.02, "상위 5 후보\n" + txt, transform=ax.transAxes, fontsize=S["b"] - 2, color=S["ink"], va="bottom",
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=S["grid"]))
    foot(fig, S, "시설 확정 아님(협의 필요) · " + COVN)
    save(fig, cat, name, "E1", f"{SCL[sc]}: 최적 1곳 {r.sites}", grade, prop, pres, "시설 확정 아님", "mclp_top15_D2_2km_by_scenario.csv; mclp_k_sites_by_scenario.csv")

def fig_E2(sty, mode, cat, name, grade, prop, pres, editable=False):
    S = STY[sty]
    pres_ = sty == "present" or mode == "memo"
    fig = plt.figure(figsize=(16, 9) if pres_ else (9, 11), facecolor=S["bg"])
    ax = fig.add_axes([0.0, 0.06, 0.55, 0.80] if pres_ else [0.02, 0.07, 0.96, 0.80])
    rec_map(ax, S, SC[2], k=2, top=False, region=True)
    draw_sites(ax, S, ("E0", "E1", "E2", "E3"), circles=False, labels=False, size=80)
    for nm, ids, lab in [("1순위", SW, f"남서부 권역\n(상대·원신흥 일대)"), ("2순위", NE, "노은 권역")]:
        g = dong[dong.ADM_NM.isin(ids)].dissolve().geometry.iloc[0].representative_point()
        ax.text(g.x + (2500 if nm == "1순위" else -1500), g.y + (-1500 if nm == "1순위" else 2500), f"{nm}\n{lab}", fontsize=S["b"] + 1, weight="bold", color=S["ink"], ha="center",
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=S["ink"], lw=1))
    h = [Patch(fc=S["seq"][3] if not S["hatch"] else "#bdbdbd", hatch="///" if S["hatch"] else None, ec=S["ink"], label=f"1순위 검토: 남서부 6개 동({SWN}명)"),
         Patch(fc=S["seq"][1] if not S["hatch"] else "#e0e0e0", hatch="..." if S["hatch"] else None, ec=S["ink"], ls="--", label=f"2순위 검토: 노은 1·2·3동({NEN}명)"),
         Line2D([], [], marker="s", ls="", color=S["site"], ms=9, label="등록 교육지원 장소 4곳"),
         Line2D([], [], marker="*", ls="", color=S["cand"], ms=14, label="최적 2곳 예시(S2: 호산나반석·흥도초)")]
    ax.legend(handles=h, loc="upper left", frameon=False, fontsize=S["b"] - 1.5)
    ttl = "권역 단위 추천: 남서부 우선, 노은 권역 확장 검토"
    if pres_:
        fig.text(0.57, 0.90, ttl, fontsize=S["t"] - 1, weight="bold", color=S["ink"], va="top", wrap=True)
        notes = [("1순위 남서부(상대·원신흥 일대)", f"기존 장소 가정 S0·S1·S2 모두에서 2km 최적 1곳이 이 권역\n(15개 민감도 설정 중 1위: S0 12 · S1 8 · S2 8)"),
                 ("2순위 노은 권역", "거점 2곳일 때 모든 가정에서 노은3동(호산나반석) 포함\n건물가중 수요·3km 이상에서는 1위"),
                 ("시설이 아니라 권역", "상위 10 후보 간 차이 17~26명 → 권역 안 시설은\n학교·지역아동센터·도서관과 협의로 결정"),
                 ("확인 필요", "후보 시설의 공간·인력·협조, 등록 그룹의 외부 아동 참여")]
        for i, (a, b) in enumerate(notes):
            y = 0.78 - i * 0.17
            fig.patches.append(FancyBboxPatch((0.57, y - 0.13), 0.41, 0.145, boxstyle="round,pad=0.005,rounding_size=0.015", transform=fig.transFigure, fc=S["card"], ec=S["grid"]))
            fig.text(0.585, y - 0.005, a, fontsize=S["b"] + 1, weight="bold", color=S["acc"] if i < 3 else S["muted"], va="top")
            fig.text(0.585, y - 0.05, b, fontsize=S["b"] - 1.5, color=S["ink"], va="top")
    else:
        head(fig, S, ttl, "특정 시설 확정이 아니라 협의를 시작할 권역의 우선순위")
    foot(fig, S, COVN, "MCLP·민감도 결과(submission_revision/yuseong) 기반 · 시설 확정 아님")
    save(fig, cat, name, "E2", "남서부 1순위, 노은 2순위(권역)", grade, prop, pres, "시설 확정 아님", "sensitivity_top1_by_scenario.csv; mclp_k_sites_by_scenario.csv", editable=editable, hi=editable)

def fig_E3_bar(sty, cat, name, grade, prop, pres):
    S = STY[sty]
    fig, ax = plt.subplots(figsize=(10, 6.2) if sty != "present" else (16, 9), facecolor=S["bg"]); fig.subplots_adjust(left=0.09, right=0.8, top=0.8, bottom=0.17)
    xs = [0, 1, 2, 3]
    for c, sc, m in zip(SCOL(S), SC, ["o", "s", "^"]):
        v = [K[(sc, 1)].coverage_before * 100] + [K[(sc, k)].coverage_after * 100 for k in (1, 2, 3)]
        ax.plot(xs, v, color=c, marker=m, lw=2.4, ms=8)
        for x, vv in zip(xs, v):
            ax.text(x, vv + 1.6, f"{vv:.1f}", ha="center", fontsize=S["b"] - 2, color=S["ink"])
        ax.text(3.1, v[-1], SCL[sc], va="center", fontsize=S["b"] - 1, color=S["ink"])
    clean(ax, S); ax.set_xticks(xs, ["현재", "+1곳", "+2곳", "+3곳"]); ax.set_ylim(0, 70); ax.set_ylabel("2km 포괄률(%)", color=S["ink"])
    head(fig, S, "신규 거점 수에 따른 포괄률(정확해)", "추가 효과는 거점이 늘수록 체감 · 2곳 조합은 모든 가정에서 남서부 + 노은 권역")
    foot(fig, S, COVN, "k=2·3은 정확 열거(MCLP) · " + SRC_S.split(" · ")[0])
    save(fig, cat, name, "E3", "1→2→3곳 체감 효과", grade, prop, pres, "포괄률 ≠ 이용률", "mclp_k_sites_by_scenario.csv")

# ================================================================== F 정책·스토리
def boxes_flow(sty, steps, title, sub, cat, name, fid, msg, grade, prop, pres, vertical=False, notes=None):
    S = STY[sty]
    fig = plt.figure(figsize=(16, 7) if not vertical else (9, 12), facecolor=S["bg"])
    head(fig, S, title, sub)
    n = len(steps)
    for i, (a, b) in enumerate(steps):
        if vertical:
            x0, y0, w, h = 0.08, 0.80 - i * (0.72 / n), 0.84, 0.72 / n - 0.03
        else:
            w = (0.96 - 0.02 * (n - 1)) / n; x0, y0, h = 0.02 + i * (w + 0.02), 0.22, 0.50
        fig.patches.append(FancyBboxPatch((x0, y0 - (h if vertical else 0)), w, h, boxstyle="round,pad=0.004,rounding_size=0.02", transform=fig.transFigure,
                                          fc=S["card"], ec=S["acc"] if i == n - 1 else S["grid"], lw=2 if i == n - 1 else 1.2))
        if vertical:
            fig.text(x0 + 0.03, y0 - 0.02, f"{i+1}", fontsize=S["t"] + 6, color=S["acc"], weight="bold", va="top")
            fig.text(x0 + 0.13, y0 - 0.02, a, fontsize=S["b"] + 4, color=S["ink"], weight="bold", va="top")
            fig.text(x0 + 0.13, y0 - 0.055, b, fontsize=S["b"] + 0.5, color=S["ink"], va="top", linespacing=1.4)
        else:
            fig.text(x0 + 0.015, y0 + h - 0.03, f"{i+1}", fontsize=S["t"] + 10, color=S["acc"], weight="bold", va="top")
            fig.text(x0 + 0.015, y0 + h - 0.14, a, fontsize=S["b"] + 4, color=S["ink"], weight="bold", va="top", wrap=True)
            fig.text(x0 + 0.015, y0 + h - 0.23, b, fontsize=S["b"] + 1, color=S["ink"], va="top", linespacing=1.5)
            if i < n - 1:
                fig.patches.append(FancyArrowPatch((x0 + w - 0.004, y0 + h / 2), (x0 + w + 0.022, y0 + h / 2), transform=fig.transFigure, arrowstyle="-|>", mutation_scale=18, color=S["muted"]))
    if notes:
        foot(fig, S, *notes)
    save(fig, cat, name, fid, msg, grade, prop, pres, "", "review_report.md")

FLOW = [("전국 수요 진단", f"다문화가구 자녀\n{TOTAL:,}명, 229개 시군구\n상위 10%에 {TOP_SHARE:.1%}"),
        ("유성구 수요 권역", f"유성구 {YU:,}명\n남서부 6개 동 {SWN}명\n({SWN/YU:.1%})"),
        ("기존 교육지원 확인", "등록 기초학습 그룹 4곳\n(본관·온돌방·어은초·전민초)\n정원 합계 40명"),
        ("MCLP 권역 검토", "2km 포괄률\n9.8~35.1% → 31.9~46.5%\n남서부 → 노은"),
        ("기존 공공시설 활용", "학교·지역아동센터·도서관을\n위성 거점으로 지정\n(협의 후 시범 운영)")]
ROAD = [("1단계 · 협의와 확인", "등록 그룹 4곳의 운영·외부 참여 확인\n남서부 권역 후보 시설과 공간·인력 협의"),
        ("2단계 · 남서부 시범 운영", "상대·원신흥 일대 위성 거점 1곳\n가족센터 강사 순회(기초학습·진로)"),
        ("3단계 · 수요·이용 검증", "실제 신청·출석·대기 인원 수집\n포괄률이 아닌 이용 지표로 평가"),
        ("4단계 · 노은 권역 확장", "검증 결과에 따라 노은 1·2·3동 거점 추가\n같은 방법으로 다른 시군구에 적용")]
DIFF = [("수요를 공표값으로", "행정동별 다문화가구 자녀 수를\n추정 없이 공식 통계로 사용"),
        ("기존 서비스 반영", "가족센터 본관뿐 아니라 등록된\n학교·마을돌봄 그룹까지 확인"),
        ("공간 최적화", "MCLP 정확해 + 반경·수요배분\n민감도로 권역 추천"),
        ("짓지 않고 활용", "학교·지역아동센터·도서관 등\n기존 공공시설을 위성 거점으로"),
        ("확장 가능", "전국 229개 시군구 수요 자료로\n같은 절차를 다른 지역에 적용")]
CAV = [("포괄률 ≠ 이용률", "포괄률은 직선 2km 안에 사는 자녀 비율(잠재 접근성)입니다.\n실제로 프로그램을 이용하는 비율이 아닙니다."),
       ("정원 ≠ 이용자", "40명은 등록 정원 합계입니다. 실제 이용자 수는 자료에 없습니다."),
       ("수요 = 대리지표", "1,500명은 다문화가구 미성년 자녀 수입니다. 교육지원이 필요한 인원 그 자체가 아닙니다."),
       ("직선거리", "도로망·이동시간·대중교통은 반영하지 않았습니다."),
       ("운영 미확인", "등록 그룹의 실제 운영·잔여 정원·외부 아동 참여 가능 여부, 후보 시설의 사용 가능성은 추가 확인이 필요합니다.")]

def fig_F4(sty, cat, name, grade, prop, pres, compact=False):
    S = STY[sty]
    fig = plt.figure(figsize=(16, 3.4) if compact else (12, 9), facecolor=S["bg"])
    if compact:
        fig.patches.append(FancyBboxPatch((0.01, 0.06), 0.98, 0.88, boxstyle="round,pad=0.004,rounding_size=0.02", transform=fig.transFigure, fc=S["card"], ec=S["acc"], lw=1.5))
        fig.text(0.025, 0.88, "(!) 해석 시 유의사항", fontsize=S["b"] + 5, weight="bold", color=S["acc"], va="top")
        for i, (a, b) in enumerate(CAV):
            fig.text(0.025 + (i % 3) * 0.325, 0.68 - (i // 3) * 0.33, f"• {a}", fontsize=S["b"] + 3, weight="bold", color=S["ink"], va="top")
            fig.text(0.025 + (i % 3) * 0.325, 0.58 - (i // 3) * 0.33, textwrap.fill(b.replace("\n", " "), 38), fontsize=S["b"] + 0.5, color=S["muted"], va="top")
    else:
        head(fig, S, "결과를 읽을 때 꼭 구분해야 할 다섯 가지")
        for i, (a, b) in enumerate(CAV):
            y = 0.86 - i * 0.165
            fig.patches.append(FancyBboxPatch((0.03, y - 0.135), 0.94, 0.145, boxstyle="round,pad=0.004,rounding_size=0.015", transform=fig.transFigure, fc=S["card"], ec=S["grid"]))
            fig.text(0.065, y - 0.06, "!", fontsize=22, color="white", weight="bold", va="center", ha="center", bbox=dict(boxstyle="circle,pad=0.3", fc=S["acc"], ec="none"))
            fig.text(0.12, y - 0.02, a, fontsize=S["b"] + 2, weight="bold", color=S["ink"], va="top")
            fig.text(0.12, y - 0.065, b, fontsize=S["b"] - 0.5, color=S["muted"], va="top")
    save(fig, cat, name, "F4", "포괄률≠이용률, 정원≠이용자, 직선거리, 운영 미확인", grade, prop, pres, "", "review_report.md")

# ================================================================== 표-그림
def table_fig(sty, title, cols, rows, widths, cat, name, fid, msg, grade, prop, pres, note=None, data=""):
    S = STY[sty]
    pres_ = sty == "present"
    rh = 0.075 if pres_ else 0.06
    H = (2.0 + 0.55 * (len(rows) + 1) + (0.4 if note else 0)) * (1.25 if pres_ else 1)
    fig = plt.figure(figsize=(16, max(H, 6)) if pres_ else (12, H), facecolor=S["bg"])
    fs = S["b"] + (4 if pres_ else 2.5)
    fig.text(0.02, 0.97, title, fontsize=S["t"] - (0 if pres_ else 2), weight="bold", color=S["ink"], va="top")
    top = 1 - (1.0 / fig.get_figheight()); lh = 0.5 / fig.get_figheight() * (1.25 if pres_ else 1)
    xs = np.cumsum([0.02] + widths[:-1])
    fig.patches.append(Rectangle((0.015, top - lh * 0.75), 0.97, lh, transform=fig.transFigure, fc=S["acc"] if sty != "bw" else "#333333", ec="none"))
    for x, c in zip(xs, cols):
        fig.text(x, top - lh * 0.25, c, fontsize=fs - 0.5, weight="bold", color="white", va="center")
    for i, row in enumerate(rows):
        y = top - lh * (i + 1)
        if i % 2 == 1:
            fig.patches.append(Rectangle((0.015, y - lh * 0.75), 0.97, lh, transform=fig.transFigure, fc=S["card"], ec="none"))
        for x, v in zip(xs, row):
            fig.text(x, y - lh * 0.25, str(v), fontsize=fs - 1.5, color=S["ink"], va="center")
    if note:
        fig.text(0.02, top - lh * (len(rows) + 1) - 0.01, note, fontsize=fs - 3, color=S["muted"], va="top", wrap=True)
    save(fig, cat, name, fid, msg, grade, prop, pres, "", data)

def tables(sty, suf):
    cat = "tab"
    table_fig(sty, "핵심 수치 요약", ["항목", "값", "기준·정의"],
              [["전국 다문화가구 자녀", f"{TOTAL:,}명", "229개 기초지자체 합 = 원표 전국값(2025.11.1.)"],
               ["상위 10% 시군구(23곳) 비중", f"{TOP_SHARE:.1%}", "자녀 수 기준"],
               ["대전 유성구", f"{YU:,}명 (전국 {YU_RANK}위)", "13개 행정동 합 = 구 합계"],
               ["남서부 6개 동", f"{SWN}명 ({SWN/YU:.1%})", "진잠·학하·상대·원신흥·온천1·온천2"],
               ["등록 기초학습 장소", "4곳 · 정원 합계 40명", "등록 정원(이용자 수 아님)"],
               ["2km 포괄률 현재", "9.8% / 25.5% / 35.1%", "S0 / S1 / S2(직선거리, 잠재 접근성)"],
               ["최적 1곳 추가 후", "31.9% / 36.9% / 46.5%", "추가 약 331 / 171 / 171명"],
               ["최적 2곳 추가 후", f"{K[(SC[0],2)].coverage_after:.1%} / {K[(SC[1],2)].coverage_after:.1%} / {K[(SC[2],2)].coverage_after:.1%}", "남서부 + 노은 권역"]],
              [0.30, 0.25, 0.45], cat, f"tab01_key_numbers_{suf}", "T1", "핵심 수치", "A", "예", "예", note=DEF + " · " + COVN, data="여러 CSV(assert 검증)")
    table_fig(sty, "기존 장소 가정별 결과 비교(직선 2km, D2)", ["시나리오", "기존 장소", "현재", "최적 1곳(행정동)", "+1곳", "+2곳"],
              [[SCL[s], {SC[0]: "본관", SC[1]: "본관·온돌방", SC[2]: "본관·온돌방·어은초·전민초"}[s], f"{M[s].coverage_before:.1%}", f"{M[s].best}({M[s].best_dong})",
                f"{M[s].coverage_after:.1%}", f"{K[(s,2)].coverage_after:.1%}"] for s in SC],
              [0.16, 0.24, 0.09, 0.27, 0.11, 0.11], cat, f"tab02_scenario_comparison_{suf}", "T2", "시나리오 비교", "A", "예", "예",
              note="S1·S2는 등록 장소의 외부 아동 이용 가능을 가정(미확인). " + COVN, data="sensitivity_top1_by_scenario.csv; mclp_k_sites_by_scenario.csv")
    table_fig(sty, "등록 기초학습지원 장소 4곳", ["장소", "유형", "행정동", "행사기간(2026)", "대상", "정원"],
              [[r["name"], TYPE[r.sid], r["좌표행정동"], r["행사기간"].replace("2026-", "").replace(" ~ ", "~"), textwrap.shorten(r["참여대상"], 26, placeholder="…"), f"{r.cap}명"]
               for _, r in ex.sort_values("sid").iterrows()] + [["합계", "", "", "", "", "40명"]],
              [0.20, 0.13, 0.09, 0.14, 0.34, 0.08], cat, f"tab03_existing_sites_{suf}", "T3", "4곳 요약", "A", "예", "예",
              note="자료: 가족센터 프로그램 데이터(2026.9.14. 게시본) 원자료 줄 4786·4787·4795·4824 · 실제 운영·외부 참여 미확인 · 정원 ≠ 이용자", data="existing_sites_revised.csv")
    nsw = {s: int(sens[(sens.scenario == s)].best_in_SW.sum()) for s in SC}
    table_fig(sty, "검토 권역 요약", ["권역", "행정동", "자녀", "근거(민감도 15개 설정 = 수요배분 3 × 반경 5)"],
              [["1순위 남서부", "진잠·학하·상대·원신흥·온천1·온천2", f"{SWN}명", f"D2 2km 최적 1곳이 S0·S1·S2 모두 이 권역 · 1위 횟수 S0 {nsw[SC[0]]} / S1 {nsw[SC[1]]} / S2 {nsw[SC[2]]}"],
               ["2순위 노은", "노은1·노은2·노은3", f"{NEN}명", "2곳 조합에서 모든 가정이 노은3동(호산나반석) 포함 · D3 2km·D2 3km+(S1·S2) 1위"]],
              [0.13, 0.27, 0.07, 0.53], cat, f"tab04_candidate_regions_{suf}", "T4", "권역 추천 근거", "A", "예", "예",
              note="상위 10 후보 간 차이 17~26명 → 시설이 아닌 권역 추천 · 권역 내 시설은 협의로 결정", data="sensitivity_top1_by_scenario.csv")
    table_fig(sty, "활용 데이터와 기준시점", ["자료", "제공", "기준시점", "용도"],
              [["외국인주민 현황(통계표 수정본)", "행정안전부", "2025.11.1.(2026.10. 공표)", "시군구·행정동 다문화가구 자녀"],
               ["행정구역 경계·인구", "국가데이터처 SGIS", "경계 2025.6.30. / 인구 2024", "경계, 0~19세 인구(비율 분모)"],
               ["가족센터 프로그램 데이터", "한국건강가정진흥원", "2026.9.14. 게시본", "등록 기초학습 장소 4곳"],
               ["유성구 지역아동센터 현황", "유성구", "2026.6.30.", "후보지 목록(22곳)"],
               ["지역아동센터·초중등학교·도서관 표준데이터", "공공데이터포털", "2026.7~10.", "후보·장소 공식 좌표"],
               ["OpenStreetMap", "OSM 기여자(ODbL)", "2026.11.3. 수집", "행정복지센터 등 후보, 건물(D3)"]],
              [0.33, 0.18, 0.22, 0.27], cat, f"tab05_data_sources_{suf}", "T5", "출처·기준시점", "A", "예", "예", data="review_report.md; 패키지 README")

# ================================================================== 실행
G = []
def run(f, *a):
    try:
        f(*a)
    except Exception as e:
        import traceback; traceback.print_exc(); G.append((f.__name__, a, repr(e)))

# A1
run(fig_A1, "report", "abs", "main", "fig01_national_demand_map_report_v1", "A", "예", "", True)
run(fig_A1, "report", "top", "var", "fig01_national_demand_map_top23_v2", "A", "예(대안)", "예")
run(fig_A1, "info", "abs", "var", "fig01_national_demand_map_infotone_v3", "B", "대안", "")
run(fig_A1, "bw", "abs", "var", "fig01_national_demand_map_bw_v4", "B", "흑백 인쇄 시", "")
run(fig_A1, "report", "ratio", "var", "fig01b_national_ratio_map_per1000_v1", "B", "보조", "", False)
run(fig_A1, "present", "top", "pres", "fig01_national_demand_map_presentation_v1", "A", "", "예")
# A2
run(fig_A2, "report", "bar", "main", "fig02_national_concentration_top23_bar_v1", "B", "보조", "", True)
run(fig_A2, "report", "pareto", "var", "fig02_national_concentration_pareto_v2", "A", "예", "예")
run(fig_A2, "bw", "pareto", "var", "fig02_national_concentration_pareto_bw_v3", "B", "흑백 인쇄 시", "")
run(fig_A2, "info", "info", "info", "fig02_national_concentration_infographic_v1", "A", "예", "예")
run(fig_A2, "present", "info", "pres", "fig02_national_concentration_presentation_v1", "A", "", "예")
# A3
run(fig_A3, "report", "main", "fig03_story_national_to_yuseong_v1", "A", "예", "예", True)
run(fig_A3, "info", "info", "fig03_story_national_to_yuseong_infographic_v2", "A", "대안", "예")
run(fig_A3, "bw", "var", "fig03_story_national_to_yuseong_bw_v3", "B", "흑백 인쇄 시", "")
# B1
run(fig_B1, "report", "sw", "main", "fig04_yuseong_demand_map_southwest_v1", "A", "예", "예", True)
run(fig_B1, "report", "plain", "var", "fig04_yuseong_demand_map_choropleth_v2", "A", "대안", "")
run(fig_B1, "report", "detail", "var", "fig04_yuseong_demand_map_labels_detail_v3", "A", "대안", "")
run(fig_B1, "report", "minimal", "var", "fig04_yuseong_demand_map_minimal_v4", "B", "", "")
run(fig_B1, "bw", "sw", "var", "fig04_yuseong_demand_map_southwest_bw_v5", "B", "흑백 인쇄 시", "")
run(fig_B1, "info", "sw", "var", "fig04_yuseong_demand_map_southwest_infotone_v6", "B", "", "")
run(fig_B1, "present", "sw", "pres", "fig04_yuseong_demand_map_presentation_v1", "A", "", "예")
# B2/B3
run(fig_B2, "report", "main", "fig05_yuseong_dong_ranking_bar_v1", "A", "예", "", )
run(fig_B2, "present", "pres", "fig05_yuseong_dong_ranking_presentation_v1", "B", "", "예")
run(fig_B2, "bw", "var", "fig05_yuseong_dong_ranking_bw_v2", "B", "흑백 인쇄 시", "")
run(fig_B3, "info", "info", "fig06_yuseong_summary_infographic_v1", "A", "예", "예")
run(fig_B3, "report", "var", "fig06_yuseong_summary_report_v2", "B", "대안", "")
# C
run(fig_C1, "report", "map", "main", "fig07_existing_sites_map_v1", "A", "예", "", True)
run(fig_C1, "report", "table", "var", "fig07_existing_sites_map_with_table_v2", "A", "예(대안)", "예")
run(fig_C1, "bw", "map", "var", "fig07_existing_sites_map_bw_v3", "B", "흑백 인쇄 시", "")
run(fig_C1, "present", "table", "pres", "fig07_existing_sites_presentation_v1", "A", "", "예")
run(fig_C2, "report", "info", "fig08_existing_sites_cards_v1", "A", "예", "예")
run(fig_C2, "info", "var", "fig08_existing_sites_cards_infotone_v2", "B", "", "예")
run(fig_C3, "report", "main", "fig09_why_existing_sites_matter_v1", "A", "예", "예")
run(fig_C3, "present", "pres", "fig09_why_existing_sites_matter_presentation_v1", "A", "", "예")
# D
run(fig_D1, "report", "grouped", "main", "fig10_coverage_scenarios_grouped_bar_v1", "A", "예", "", True)
run(fig_D1, "report", "dumbbell", "var", "fig10_coverage_scenarios_dumbbell_v2", "A", "예(대안)", "예")
run(fig_D1, "bw", "dumbbell", "var", "fig10_coverage_scenarios_dumbbell_bw_v3", "B", "흑백 인쇄 시", "")
run(fig_D1, "present", "grouped", "pres", "fig10_coverage_scenarios_presentation_v1", "A", "", "예")
run(fig_D1_arrow, "info", "info", "fig10_coverage_before_after_arrow_infographic_v1", "A", "대안", "예")
run(fig_D2, "report", "main", "fig11_added_coverage_children_v1", "B", "보조", "")
run(fig_D2, "present", "pres", "fig11_added_coverage_children_presentation_v1", "B", "", "예")
run(fig_D3, "report", "line", "main", "fig12_radius_sensitivity_line_v1", "A", "예", "")
run(fig_D3, "report", "panel", "var", "fig12_radius_demand_sensitivity_panel_v2", "A", "부록", "")
run(fig_D3, "report", "compact", "var", "fig12_radius_sensitivity_compact_table_v3", "A", "예(소형)", "")
run(fig_D3, "bw", "line", "var", "fig12_radius_sensitivity_line_bw_v4", "B", "흑백 인쇄 시", "")
# E
run(fig_E1_panel, "report", 1, "main", "fig13_new_site_recommendation_panel_k1_v1", "A", "예", "", True)
run(fig_E1_panel, "present", 1, "pres", "fig13_new_site_recommendation_panel_k1_presentation_v1", "A", "", "예")
run(fig_E1_panel, "bw", 1, "var", "fig13_new_site_recommendation_panel_k1_bw_v2", "B", "흑백 인쇄 시", "")
for i, sc in enumerate(SC):
    run(fig_E1_single, "report", sc, "var", f"fig13_new_site_map_{['S0','S1','S2'][i]}_single_v{3+i}", "B", "부록", "")
run(fig_E1_single, "present", SC[0], "pres", "fig13_new_site_map_S0_presentation_v1", "B", "", "예")
run(fig_E2, "report", "map", "main", "fig14_regional_recommendation_map_v1", "A", "예", "", True)
run(fig_E2, "report", "memo", "info", "fig14_regional_recommendation_policy_memo_v1", "A", "예", "예")
run(fig_E2, "present", "memo", "pres", "fig14_regional_recommendation_presentation_v1", "A", "", "예")
run(fig_E2, "bw", "map", "var", "fig14_regional_recommendation_map_bw_v2", "B", "흑백 인쇄 시", "")
run(fig_E1_panel, "report", 2, "var", "fig15_new_sites_k2_panel_v1", "A", "예(대안)", "예")
run(fig_E3_bar, "report", "main", "fig15_k1_k2_k3_coverage_v1", "A", "예", "")
run(fig_E3_bar, "present", "pres", "fig15_k1_k2_k3_coverage_presentation_v1", "B", "", "예")
# F
run(boxes_flow, "report", FLOW, "정책 제안 흐름: 전국 진단에서 유성구 처방까지", "데이터 → 확인 → 최적화 → 기존 공공시설 활용", "main", "fig16_policy_flow_v1", "F1", "분석·제안 흐름", "A", "예", "예",
    False, [DEF, COVN])
run(boxes_flow, "info", FLOW, "정책 제안 흐름", "전국 진단 → 유성구 처방", "info", "fig16_policy_flow_infographic_v2", "F1", "분석·제안 흐름", "A", "대안", "예", True, [COVN])
run(boxes_flow, "present", FLOW, "전국 진단 → 유성구 처방", "", "pres", "fig16_policy_flow_presentation_v1", "F1", "분석·제안 흐름", "A", "", "예", False, [COVN])
run(boxes_flow, "info", DIFF, "우리 아이디어의 차별성", "새로 짓기보다, 데이터로 찾고 있는 시설을 활용한다", "info", "fig17_differentiation_infographic_v1", "F2", "차별성 5가지", "A", "예", "예", False,
    ["실행 가능성은 후보 시설 협의를 전제로 함"])
run(boxes_flow, "report", ROAD, "정책 실행 단계(제안)", "남서부 시범 → 이용 검증 → 노은 권역 확장", "info", "fig18_implementation_roadmap_v1", "F3", "단계별 실행안", "A", "예", "예", False,
    ["각 단계는 제안이며 운영 확정 아님 · 3단계에서 포괄률이 아닌 실제 이용 지표로 평가"])
run(boxes_flow, "present", ROAD, "실행 로드맵(제안)", "", "pres", "fig18_implementation_roadmap_presentation_v1", "F3", "단계별 실행안", "A", "", "예", False, ["운영 확정 아님"])
run(fig_F4, "report", "info", "fig19_interpretation_caveats_v1", "A", "예(부록·하단)", "예")
run(fig_F4, "report", "var", "fig19_interpretation_caveats_footer_box_v2", "A", "예(하단 박스)", "", True)
run(fig_F4, "bw", "var", "fig19_interpretation_caveats_bw_v3", "B", "흑백 인쇄 시", "")
# tables
for sty, suf in (("report", "doc"), ("present", "presentation")):
    tables(sty, suf)

reg = pd.DataFrame(REG); reg.to_csv(DIRS["rep"] / "figure_registry.csv", index=False, encoding="utf-8-sig")
print("generated", len(reg), "errors", G)
