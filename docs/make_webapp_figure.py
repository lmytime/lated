"""Build docs/webapp.png: the README figure for the lated workbench.

The figure is authored as HTML/CSS and rendered with headless Chrome, which
buys real typography (Source Serif 4, Inter, IBM Plex Mono via Google Fonts),
proper optical spacing and hairline rules -- things a plotting library will
not give you.

The two plots are the app's *own* exports (`docs/cr3_sed.pdf` and
`docs/cr3_corner.pdf`, produced by the "save PDF" buttons in the web app), so
the figure shows exactly what a user gets rather than a reimplementation of
it.  The verdict numbers come from a live run of the packaged API, so they
cannot drift from the code.

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
# band swatches as the app's own export draws them (sampled from cr3_sed.pdf)
BAND_FILL = {"F200W": "#c3e88f", "F277W": "#f7bf6a", "F356W": "#f2916b"}

CANVAS_W, CANVAS_H, SCALE = 1600, 900, 2               # -> 3200 x 1800
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def rasterise(pdf: pathlib.Path, into: pathlib.Path, dpi: int = 300) -> str:
    """Rasterise one of the app's PDF exports next to the page; return its name."""
    stem = into / pdf.stem
    subprocess.run(["pdftocairo", "-png", "-r", str(dpi), "-singlefile",
                    str(pdf), str(stem)], check=True)
    return stem.with_suffix(".png").name


def rows_html() -> str:
    out = []
    for b, (f_, e_) in PHOT.items():
        out.append(
            f'<tr><th><i style="background:{BAND_FILL[b]}"></i>{b}</th>'
            f'<td class="v">{f_ / NJY:g}</td>'
            f'<td class="e">&plusmn;&thinsp;{e_ / NJY:g}</td></tr>')
    return "\n".join(out)


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper:#f7f3ec; --card:#fffdf9; --inset:#f2ece1;
    --rule:#e2dacb; --rule-firm:#cdc4ae;
    --ink:#23211c; --dim:#6b6558; --faint:#9c9584;
    --amber:#a8590a; --rose:#b3123a;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    width:{W}px; height:{H}px; background:var(--paper); color:var(--ink);
    font-family:"Inter",system-ui,sans-serif; -webkit-font-smoothing:antialiased;
    padding:54px 60px 48px; display:flex; flex-direction:column;
  }}
  .eyebrow {{
    font-family:"Inter",sans-serif; font-weight:600; font-size:12px;
    letter-spacing:.20em; text-transform:uppercase; color:var(--faint);
  }}

  /* ---------- masthead ---------- */
  header {{ display:flex; align-items:baseline; gap:14px; padding-bottom:16px; }}
  .word {{ font-family:"Source Serif 4",serif; font-weight:700; font-size:40px;
           letter-spacing:-.015em; }}
  .kind {{ font-family:"Source Serif 4",serif; font-style:italic; font-weight:400;
           font-size:31px; color:var(--dim); letter-spacing:-.01em; }}
  header .spacer {{ flex:1; }}
  .subject {{ text-align:right; line-height:1.45; }}
  .subject b {{ font-family:"IBM Plex Mono",monospace; font-weight:600;
                font-size:14px; letter-spacing:.02em; }}
  .subject span {{ font-size:12.5px; color:var(--dim); }}
  .hr {{ height:1px; background:var(--ink); opacity:.85; }}
  .hr.thin {{ background:var(--rule-firm); opacity:1; }}

  /* ---------- body grid ---------- */
  main {{ flex:1; display:grid; grid-template-columns:352px 1fr;
          gap:44px; padding-top:26px; min-height:0; }}
  .col {{ display:flex; flex-direction:column; min-height:0; }}
  .col > .eyebrow {{ margin-bottom:12px; }}

  /* ---------- input ---------- */
  .card {{ background:var(--card); border:1px solid var(--rule);
           border-radius:12px; box-shadow:0 1px 2px rgba(90,75,40,.05),
           0 10px 26px -14px rgba(90,75,40,.28); }}
  .pcard {{ padding:22px 24px 20px; }}
  .pcard h3 {{ font-size:13px; font-weight:600; letter-spacing:.04em;
               color:var(--dim); display:flex; align-items:center; gap:8px; }}
  .pcard h3 em {{ font-family:"IBM Plex Mono",monospace; font-style:normal;
                  color:var(--amber); font-weight:600; }}
  .unit {{ margin-left:auto; font-family:"IBM Plex Mono",monospace; font-size:11px;
           color:var(--card); background:var(--ink); padding:3px 8px;
           border-radius:5px; letter-spacing:.03em; }}
  table {{ width:100%; border-collapse:collapse; margin-top:16px; }}
  thead th {{ font-size:11px; font-weight:500; color:var(--faint);
              letter-spacing:.06em; text-transform:uppercase;
              padding-bottom:7px; border-bottom:1px solid var(--rule-firm); }}
  thead th:nth-child(2), thead th:nth-child(3) {{ text-align:right; }}
  tbody th {{ text-align:left; font-family:"IBM Plex Mono",monospace;
              font-weight:500; font-size:14.5px; padding:11px 0;
              display:flex; align-items:center; gap:9px; }}
  tbody th i {{ width:10px; height:10px; border-radius:50%; display:inline-block;
                box-shadow:inset 0 0 0 1px rgba(0,0,0,.18); }}
  tbody td {{ text-align:right; font-family:"IBM Plex Mono",monospace;
              font-variant-numeric:tabular-nums; padding:11px 0; }}
  td.v {{ font-size:16px; font-weight:500; }}
  td.e {{ font-size:13.5px; color:var(--dim); width:84px; }}
  tbody tr + tr th, tbody tr + tr td {{ border-top:1px solid var(--rule); }}
  .redshift {{ margin-top:18px; padding-top:14px; border-top:1px solid var(--rule);
               display:flex; justify-content:space-between; align-items:baseline;
               font-family:"IBM Plex Mono",monospace; font-size:13.5px; }}
  .redshift span {{ color:var(--faint); font-size:11px; letter-spacing:.06em;
                    text-transform:uppercase; font-family:"Inter",sans-serif; }}
  .source {{ margin-top:16px; font-family:"Source Serif 4",serif; font-size:15px;
             font-style:italic; color:var(--dim); line-height:1.5; }}
  .source b {{ font-style:normal; font-weight:600; color:var(--ink); }}

  /* ---------- output ---------- */
  .plot {{ min-height:0; display:flex; align-items:center;
           justify-content:center; overflow:hidden; }}
  .plot img {{ max-width:100%; max-height:100%; width:auto; height:auto;
               object-fit:contain; }}
  .outgrid {{ flex:1; display:grid; grid-template-columns:1fr 1fr;
              gap:34px; min-height:0; }}
  .stack {{ display:flex; flex-direction:column; gap:22px; min-height:0; }}
  .stack .sed {{ flex:1 1 0; }}
  .stack .verdict {{ flex:0 0 186px; }}
  .outgrid > .plot {{ align-items:flex-start; }}
  .verdict {{ padding:18px 24px; display:flex; flex-direction:column;
              justify-content:center; }}
  .verdict .lab {{ font-family:"IBM Plex Mono",monospace; font-size:13px;
                   color:var(--dim); letter-spacing:.01em; }}
  .verdict .num {{ font-family:"Source Serif 4",serif; font-weight:700;
                   font-size:54px; line-height:1.02; color:var(--amber);
                   letter-spacing:-.025em; margin:6px 0 2px;
                   font-variant-numeric:tabular-nums; }}
  .tag {{ display:inline-block; align-self:flex-start; font-family:"Inter",sans-serif;
          font-size:10.5px; font-weight:600; letter-spacing:.12em;
          color:var(--rose);
          border:1px solid var(--rose); border-radius:999px;
          padding:5px 11px; margin-top:10px; }}
  .verdict .one {{ margin-top:14px; font-family:"IBM Plex Mono",monospace;
                   font-size:13px; color:var(--dim); }}
</style></head>
<body>
  <header>
    <span class="word">LATED</span><span class="kind">inference</span>
    <span class="spacer"></span>
    <span class="subject"><b>{SOURCE}</b><br><span>{REFERENCE} &middot; <i>z</i>&thinsp;=&thinsp;{Z}</span></span>
  </header>
  <div class="hr"></div>

  <main>
    <section class="col">
      <div class="eyebrow">Input &mdash; what you type in</div>
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
      <p class="source">Three NIRCam bands and a redshift. <b>{SOURCE}</b> is a
      metal&#8209;free candidate whose [O&#8239;III] is undetected, so the ratio
      comes back as an honest limit rather than a fabricated value.</p>
    </section>

    <section class="col">
      <div class="eyebrow">Output &mdash; what the fit gives back</div>
      <div class="outgrid">
        <div class="stack">
          <div class="plot sed"><img src="{SED}" alt="SED"></div>
          <div class="card verdict">
            <div class="lab">R3 = [O&#8239;III]&thinsp;5007 / H&beta;</div>
            <div class="num">&lt;&thinsp;{P975}</div>
            <span class="tag">2&sigma; UPPER LIMIT</span>
            <div class="one">1&sigma; &nbsp;&lt;&thinsp;{P84}</div>
          </div>
        </div>
        <div class="plot"><img src="{CORNER}" alt="corner"></div>
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
        html = HTML.format(W=CANVAS_W, H=CANVAS_H, SOURCE=SOURCE,
                           REFERENCE=REFERENCE, Z=Z, ROWS=rows_html(),
                           SED=rasterise(SED_PDF, work),
                           CORNER=rasterise(CORNER_PDF, work),
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
