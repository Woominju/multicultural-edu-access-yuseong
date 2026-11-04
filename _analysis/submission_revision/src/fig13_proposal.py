"""fig13 패널 (제안서 삽입용): 하단 각주는 포괄률 정의만."""
from pathlib import Path
src = Path(__file__).with_name("fig_make.py").read_text(encoding="utf-8")
exec(compile(src[:src.index("\ndef run(f, *a):")], "fig_make.py", "exec"))

OUT = Path(__file__).resolve().parents[1] / "figures_final"
COVN = "포괄률 = 거점에서 직선 2km 안에 사는 다문화가구 자녀 비율(행정동 내 면적균등 배분 가정)"
_foot = foot
foot = lambda fig, S, *lines: _foot(fig, S, COVN)          # 각주 = 포괄률 정의 한 줄
def save(fig, cat, name, *a, **k):
    p = OUT / "fig13_new_site_recommendation_panel_k1.png"
    fig.savefig(p, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25); plt.close(fig); print(p)
fig_E1_panel("report", 1, "main", "x", "A", "", "")
