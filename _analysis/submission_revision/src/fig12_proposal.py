"""fig12 패널 (제안서 삽입용): 부제목·하단 각주 제거."""
from pathlib import Path
src = Path(__file__).with_name("fig_make.py").read_text(encoding="utf-8")
exec(compile(src[:src.index("\ndef run(f, *a):")], "fig_make.py", "exec"))

OUT = Path(__file__).resolve().parents[1] / "figures_final"
_head = head
head = lambda fig, S, title, sub=None, **k: _head(fig, S, title, **k)   # 부제목 제거
foot = lambda fig, S, *lines: None                                      # 각주 제거
def save(fig, *a, **k):
    fig.subplots_adjust(top=0.82, bottom=0.12)                          # 비게 된 위·아래 여백 축소
    p = OUT / "fig12_radius_demand_sensitivity_panel.png"
    fig.savefig(p, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.25); plt.close(fig); print(p)
fig_D3("report", "panel", "var", "x", "A", "", "")
