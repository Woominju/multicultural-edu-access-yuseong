"""fig10 dumbbell (제안서 삽입용): 부제목 제거, 각주는 포괄률 정의만."""
from pathlib import Path
src = Path(__file__).with_name("fig_make.py").read_text(encoding="utf-8")
cut = src.index("\ndef run(f, *a):")
exec(compile(src[:cut], "fig_make.py", "exec"))

S = STY["report"]
fig, ax = plt.subplots(figsize=(10, 6.0), facecolor=S["bg"]); fig.subplots_adjust(left=0.2, right=0.95, top=0.91, bottom=0.15)
b = [M[s].coverage_before * 100 for s in SC]; a = [M[s].coverage_after * 100 for s in SC]; labs = [SCL[s] for s in SC]
y = np.arange(3)[::-1]
for i in range(3):
    ax.plot([b[i], a[i]], [y[i], y[i]], color=S["grid"], lw=6, solid_capstyle="round", zorder=1)
ax.scatter(b, y, s=150, color=S["seq"][3], zorder=2, label="현재(기존 장소)", ec="white", lw=1.5)
ax.scatter(a, y, s=150, color=S["acc"], zorder=3, label="+ 최적 신규 거점 1곳", ec="white", lw=1.5)
for i in range(3):
    ax.text(b[i], y[i] + 0.2, f"{b[i]:.1f}%", ha="center", fontsize=S["b"], color=S["ink"])
    ax.text(a[i], y[i] + 0.2, f"{a[i]:.1f}%", ha="center", fontsize=S["b"], color=S["ink"], weight="bold")
    ax.text(a[i] + 1.5, y[i], f"+{a[i]-b[i]:.1f}%p", va="center", fontsize=S["b"] - 1, color=S["muted"])
ax.set_yticks(y, labs); ax.set_xlim(0, 60); ax.set_ylim(-0.6, 2.7); ax.set_xlabel("2km 포괄률(%)", color=S["ink"]); clean(ax, S); ax.grid(axis="x", color=S["grid"]); ax.grid(axis="y", visible=False)
ax.legend(frameon=False, fontsize=S["b"] - 1, loc="lower right")
head(fig, S, "기존 장소 가정별 2km 포괄률: 현재 → 신규 거점 1곳 추가")
foot(fig, S, "포괄률 = 거점에서 직선 2km 안에 사는 다문화가구 자녀 비율(행정동 내 면적균등 배분 가정)")
out = Path(__file__).resolve().parents[1] / "figures_final" / "fig10_coverage_scenarios_dumbbell.png"
fig.savefig(out, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25)
print(out)
