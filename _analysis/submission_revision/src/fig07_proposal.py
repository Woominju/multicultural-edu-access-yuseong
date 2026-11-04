"""fig07 지도 (제안서 삽입용): 오른쪽 표 제거, 각주는 포괄률 정의만."""
from pathlib import Path
src = Path(__file__).with_name("fig_make.py").read_text(encoding="utf-8")
exec(compile(src[:src.index("\ndef run(f, *a):")], "fig_make.py", "exec"))

S = STY["report"]
fig = plt.figure(figsize=(9, 11), facecolor=S["bg"])
ax = fig.add_axes([0.02, 0.05, 0.96, 0.87]); yu_base(ax, S)
dong.plot(ax=ax, color=S["seq"][1], edgecolor="white", lw=1); dong[dong.ADM_NM.isin(SW)].plot(ax=ax, color=S["seq"][2], edgecolor="white", lw=1)
dong_labels(ax, S, False, S["b"] - 3.5)
draw_sites(ax, S)
ax.legend(handles=[Line2D([], [], marker="s", ls="", color=S["site"], ms=10, label="등록 교육지원 장소(기초학습 그룹)"),
                   Line2D([], [], color=S["site"], ls="--", label="반경 2km(직선)"), Patch(fc=S["seq"][2], label="남서부 6개 동")],
          loc="upper left", frameon=False, fontsize=S["b"] - 1.5)
head(fig, S, "유성구 등록 교육지원 장소 4곳(다문화가족 자녀 기초학습지원)")
foot(fig, S, "포괄률 = 거점에서 직선 2km 안에 사는 다문화가구 자녀 비율(행정동 내 면적균등 배분 가정)")
out = Path(__file__).resolve().parents[1] / "figures_final" / "fig07_existing_sites_map.png"
fig.savefig(out, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25)
print(out)
