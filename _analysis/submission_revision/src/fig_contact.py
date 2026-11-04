import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
OUT = Path(str(Path(__file__).resolve().parents[2]) + "/submission_revision/figures_for_submission")
font = ImageFont.truetype(str(Path(__file__).resolve().parents[2]) + "/work/fonts/NanumGothic-Regular.ttf", 15)
def sheet(files, dest, cols=4, tw=460, th=320, title=None):
    rows = (len(files) + cols - 1) // cols
    W = cols * (tw + 20) + 20; H = rows * (th + 50) + 20 + (40 if title else 0)
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    y0 = 20
    if title:
        d.text((20, 10), title, fill="black", font=ImageFont.truetype(str(Path(__file__).resolve().parents[2]) + "/work/fonts/NanumGothic-Bold.ttf", 22)); y0 = 50
    for i, f in enumerate(files):
        t = Image.open(f).convert("RGB"); t.thumbnail((tw, th))
        x = 20 + (i % cols) * (tw + 20); y = y0 + (i // cols) * (th + 50)
        im.paste(t, (x + (tw - t.width) // 2, y)); d.rectangle([x - 1, y - 1, x + tw, y + th], outline="#cccccc")
        d.text((x, y + th + 6), f.name[:58], fill="black", font=font)
    im.save(dest)
allf = sorted(p for d in ["01_main_figures", "02_variants", "03_infographics", "04_tables_as_figures", "05_presentation_versions"] for p in (OUT / d).glob("*.png") if "print300" not in p.name)
for i in range(0, len(allf), 20):
    sheet(allf[i:i + 20], OUT / "06_thumbnails_contactsheet" / f"contactsheet_all_{i//20+1:02d}.png", title=f"전체 그림 {i+1}–{min(i+20,len(allf))} / {len(allf)}")
if len(sys.argv) > 1:
    best = [OUT / a for a in sys.argv[1:]]
    sheet(best, OUT / "06_thumbnails_contactsheet" / "contactsheet_best.png", cols=3, tw=620, th=430, title="추천 베스트 그림")
print(len(allf))
