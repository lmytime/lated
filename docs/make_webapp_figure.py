"""Build docs/webapp.png: the README figure for the lated workbench.

The figure is authored as HTML/CSS and rendered with headless Chrome, which
buys real typography (Source Serif 4, Inter, IBM Plex Mono via Google Fonts),
tabular figures and optical spacing.

Legibility is the constraint that drives the layout.  A README image is read
at roughly 900 px wide, so everything in it has to survive being halved.  That
rules out the full 4x4 corner plot, whose axis units are unreadable at any
README width; the figure shows the SED large and, of the posterior, only the
R3 panel that carries the actual result.  The plots are the app's *own* PDF
exports (`cr3_sed.pdf`, `cr3_corner.pdf`, from the "save PDF" buttons), and
the verdict numbers come from a live run of the packaged API, so neither can
drift from the code.

    python docs/make_webapp_figure.py

Worked example: MPG-CR3 (Cai et al. 2025), a metal-free candidate at z=3.193
whose [O III] is undetected, so R3 comes back as an upper limit.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lated import FitConfig, fit                       # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------- the example
NJY = 1e-3                                             # nJy -> uJy
SOURCE, REFERENCE, Z = "MPG-CR3", "Cai et al. 2025", 3.193
PHOT = {"F200W": (13.6 * NJY, 1.9 * NJY),
        "F277W": (24.9 * NJY, 1.6 * NJY),
        "F356W": (4.0 * NJY, 1.4 * NJY)}
MC_DRAWS, MC_SEED = 3000, 9496                         # the worked-example setting

SED_PDF, CORNER_PDF = HERE / "cr3_sed.pdf", HERE / "cr3_corner.pdf"
# the R3 posterior sits in the free upper-right corner of the triangle
R3_CROP = (0.672, 0.052, 0.980, 0.374)                 # left, top, right, bottom
# band swatches as the app's own export draws them (sampled from cr3_sed.pdf)
BAND_FILL = {"F200W": "#c3e88f", "F277W": "#f7bf6a", "F356W": "#f2916b"}

CANVAS_W, CANVAS_H, SCALE = 1600, 900, 2               # -> 3200 x 1800
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def rasterise(pdf: pathlib.Path, into: pathlib.Path, dpi: int = 300,
              crop: tuple | None = None, name: str | None = None) -> str:
    """Rasterise a PDF export beside the page, optionally cropping a region
    given as fractions of the trimmed image.  Returns the file name."""
    stem = into / (name or pdf.stem)
    subprocess.run(["pdftocairo", "-png", "-r", str(dpi), "-singlefile",
                    str(pdf), str(stem)], check=True)
    png = stem.with_suffix(".png")
    if crop:
        im = Image.open(png)
        w, h = im.size
        l, t, r, b = crop
        im.crop((int(l * w), int(t * h), int(r * w), int(b * h))).save(png)
    return png.name


def rows_html() -> str:
    return "\n".join(
        f'<tr><th><i style="background:{BAND_FILL[b]}"></i>{b}</th>'
        f'<td class="v">{f_ / NJY:g}</td>'
        f'<td class="e">&plusmn;&thinsp;{e_ / NJY:g}</td></tr>'
        for b, (f_, e_) in PHOT.items())


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper:#f7f3ec; --card:#fffdf9;
    --rule:#e2dacb; --rule-firm:#cdc4ae;
    --ink:#23211c; --dim:#645e52; --faint:#8e8775;
    --amber:#a8590a; --rose:#b3123a;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    width:{W}px; height:{H}px; background:var(--paper); color:var(--ink);
    font-family:"Inter",system-ui,sans-serif; -webkit-font-smoothing:antialiased;
    padding:52px 58px 46px; display:flex; flex-direction:column;
  }}
  .eyebrow {{
    font-weight:600; font-size:15px; letter-spacing:.17em;
    text-transform:uppercase; color:var(--faint); margin-bottom:14px;
  }}

  /* ---------- masthead ---------- */
  header {{ display:flex; align-items:baseline; gap:16px; padding-bottom:18px; }}
  .word {{ font-family:"Source Serif 4",serif; font-weight:700; font-size:48px;
           letter-spacing:-.015em; }}
  .kind {{ font-family:"Source Serif 4",serif; font-style:italic; font-weight:400;
           font-size:37px; color:var(--dim); letter-spacing:-.01em; }}
  header .spacer {{ flex:1; }}
  .subject {{ text-align:right; line-height:1.5; }}
  .subject b {{ font-family:"IBM Plex Mono",monospace; font-weight:600;
                font-size:18px; letter-spacing:.01em; }}
  .subject span {{ font-size:16px; color:var(--dim); }}
  .hr {{ height:1px; background:var(--ink); opacity:.85; }}

  /* ---------- body grid ---------- */
  main {{ flex:1; display:grid; grid-template-columns:372px 1fr 348px;
          gap:46px; padding-top:26px; min-height:0; }}
  .col {{ display:flex; flex-direction:column; min-height:0; }}

  /* ---------- cards ---------- */
  .card {{ background:var(--card); border:1px solid var(--rule);
           border-radius:14px; box-shadow:0 1px 2px rgba(90,75,40,.05),
           0 12px 28px -16px rgba(90,75,40,.30); }}
  .pcard {{ padding:24px 26px 22px; }}
  .pcard h3 {{ font-size:17px; font-weight:600; letter-spacing:.01em;
               color:var(--dim); display:flex; align-items:center; gap:10px; }}
  .pcard h3 em {{ font-family:"IBM Plex Mono",monospace; font-style:normal;
                  color:var(--amber); font-weight:600; }}
  .unit {{ margin-left:auto; font-family:"IBM Plex Mono",monospace; font-size:14px;
           color:var(--card); background:var(--ink); padding:4px 10px;
           border-radius:6px; letter-spacing:.02em; }}
  table {{ width:100%; border-collapse:collapse; margin-top:18px; }}
  thead th {{ font-size:13px; font-weight:500; color:var(--faint);
              letter-spacing:.09em; text-transform:uppercase;
              padding-bottom:9px; border-bottom:1px solid var(--rule-firm); }}
  thead th:nth-child(2), thead th:nth-child(3) {{ text-align:right; }}
  tbody th {{ text-align:left; font-family:"IBM Plex Mono",monospace;
              font-weight:500; font-size:19px; padding:14px 0;
              display:flex; align-items:center; gap:11px; }}
  tbody th i {{ width:13px; height:13px; border-radius:50%; display:inline-block;
                box-shadow:inset 0 0 0 1px rgba(0,0,0,.20); }}
  tbody td {{ text-align:right; font-family:"IBM Plex Mono",monospace;
              font-variant-numeric:tabular-nums; padding:14px 0; }}
  td.v {{ font-size:22px; font-weight:500; }}
  td.e {{ font-size:17px; color:var(--dim); width:100px; }}
  tbody tr + tr th, tbody tr + tr td {{ border-top:1px solid var(--rule); }}
  .redshift {{ margin-top:20px; padding-top:16px; border-top:1px solid var(--rule);
               display:flex; justify-content:space-between; align-items:baseline;
               font-family:"IBM Plex Mono",monospace; font-size:20px;
               font-weight:500; }}
  .redshift span {{ color:var(--faint); font-size:13px; letter-spacing:.09em;
                    text-transform:uppercase; font-family:"Inter",sans-serif;
                    font-weight:500; }}
  .note {{ margin-top:20px; font-family:"Source Serif 4",serif; font-size:19px;
           font-style:italic; color:var(--dim); line-height:1.55; }}
  .note b {{ font-style:normal; font-weight:600; color:var(--ink); }}

  /* ---------- plots ---------- */
  .plot {{ min-height:0; display:flex; align-items:center;
           justify-content:center; overflow:hidden; }}
  .plot img {{ max-width:100%; max-height:100%; width:auto; height:auto; }}
  .col.mid .plot {{ flex:1 1 0; }}

  /* ---------- verdict ---------- */
  .verdict {{ padding:24px 26px 26px; }}
  .verdict .lab {{ font-family:"IBM Plex Mono",monospace; font-size:17px;
                   color:var(--dim); }}
  .verdict .num {{ font-family:"Source Serif 4",serif; font-weight:700;
                   font-size:76px; line-height:1.0; color:var(--amber);
                   letter-spacing:-.03em; margin:10px 0 0;
                   font-variant-numeric:tabular-nums; }}
  .tag {{ display:inline-block; font-size:14px; font-weight:600;
          letter-spacing:.10em; color:var(--rose); border:1.5px solid var(--rose);
          border-radius:999px; padding:7px 14px; margin-top:16px; }}
  .verdict .one {{ margin-top:16px; padding-top:14px;
                   border-top:1px solid var(--rule);
                   font-family:"IBM Plex Mono",monospace; font-size:18px;
                   color:var(--dim); }}
  .post {{ margin-top:24px; display:flex; flex-direction:column; min-height:0;
           flex:1 1 0; }}
  .post .plot {{ flex:1 1 0; background:var(--card); border:1px solid var(--rule);
                 border-radius:14px; padding:16px 18px;
                 box-shadow:0 1px 2px rgba(90,75,40,.05),
                            0 12px 28px -16px rgba(90,75,40,.30); }}
  .post .cap {{ font-size:14px; color:var(--faint); letter-spacing:.06em;
                text-transform:uppercase; font-weight:500; margin-bottom:10px; }}
</style></head>
<body>
  <header>
    <span class="word">LATED</span><span class="kind">inference</span>
    <span class="spacer"></span>
    <span class="subject"><b>{SOURCE}</b><br>
      <span>{REFERENCE} &middot; <i>z</i>&thinsp;=&thinsp;{Z}</span></span>
  </header>
  <div class="hr"></div>

  <main>
    <section class="col">
      <div class="eyebrow">Input</div>
      <div class="card pcard">
        <h3><em>03</em> Photometry <span class="unit">nJy</span></h3>
        <table>
          <thead><tr><th>Band</th><th>Flux</th><th>Error</th></tr></thead>
          <tbody>
{ROWS}
          </tbody>
        </table>
        <div class="redshift"><span>Redshift</span><b>{Z}</b></div>
      </div>
      <p class="note">Three NIRCam bands and a redshift. <b>{SOURCE}</b> is a
      metal&#8209;free candidate whose [O&#8239;III] is undetected, so the
      ratio comes back as an honest limit rather than a fabricated value.</p>
    </section>

    <section class="col mid">
      <div class="eyebrow">Fit</div>
      <div class="plot"><img src="{SED}" alt="best-fit model through the bands"></div>
    </section>

    <section class="col">
      <div class="eyebrow">Result</div>
      <div class="card verdict">
        <div class="lab">R3 = [O&#8239;III] / H&beta;</div>
        <div class="num">&lt;&thinsp;{P975}</div>
        <span class="tag">2&sigma; UPPER LIMIT</span>
        <div class="one">1&sigma;&nbsp;&nbsp;&lt;&thinsp;{P84}</div>
      </div>
      <div class="post">
        <div class="cap">Posterior</div>
        <div class="plot"><img src="{R3}" alt="R3 posterior"></div>
      </div>
    </section>
  </main>
</body></html>
"""


def main():
    base = FitConfig.fixed_slope(z=Z)
    res = fit(PHOT, base.model_copy(update={"mc": base.mc.model_copy(
        update={"n": MC_DRAWS, "seed": MC_SEED})}))
    p = res.ratios[0].value.percentiles
    print(f"{SOURCE}: R3 {res.ratios[0].status}  "
          f"< {p.p975:.2f} (2σ), < {p.p84:.2f} (1σ)")

    out = HERE / "webapp.png"
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        html = HTML.format(
            W=CANVAS_W, H=CANVAS_H, SOURCE=SOURCE, REFERENCE=REFERENCE, Z=Z,
            ROWS=rows_html(),
            SED=rasterise(SED_PDF, work),
            R3=rasterise(CORNER_PDF, work, crop=R3_CROP, name="cr3_r3"),
            P975=f"{p.p975:.2f}", P84=f"{p.p84:.2f}")
        page = work / "figure.html"
        page.write_text(html, encoding="utf-8")
        shot = work / "shot.png"
        r = subprocess.run([
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--screenshot={shot}",
            f"--window-size={CANVAS_W},{CANVAS_H}",
            f"--force-device-scale-factor={SCALE}",
            page.as_uri(),
        ], capture_output=True, text=True)
        if not shot.exists():
            raise SystemExit("chrome wrote no screenshot:\n" + r.stderr[-1500:])
        shutil.copyfile(shot, out)

    print(f"wrote {out.name} ({CANVAS_W * SCALE}x{CANVAS_H * SCALE})")


if __name__ == "__main__":
    main()
