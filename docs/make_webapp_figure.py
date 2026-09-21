"""Build docs/webapp.png: the README figure for the lated workbench.

The layout follows the app itself, left to right: the photometry you type in,
then what the fit gives back.

The two plots are the app's *own* exports (`docs/cr3_sed.pdf` and
`docs/cr3_corner.pdf`, produced by the "save PDF" buttons in the web app), so
the figure shows exactly what a user gets rather than a reimplementation of
it.  Only the surrounding chrome -- the masthead, the photometry card and the
verdict card -- is drawn here.  The verdict numbers come from a real run of
the packaged API, so they cannot drift from the code.

    python docs/make_webapp_figure.py

Worked example: MPG-CR3 (Cai et al. 2025), a metal-free candidate at z=3.193
whose [O III] is undetected, so R3 comes back as an upper limit.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from lated import FitConfig, fit                       # noqa: E402

# ---------------------------------------------------------------- the example
NJY = 1e-3                                             # nJy -> uJy
SOURCE, REFERENCE, Z = "MPG-CR3", "Cai+2025", 3.193
PHOT = {"F200W": (13.6 * NJY, 1.9 * NJY),
        "F277W": (24.9 * NJY, 1.6 * NJY),
        "F356W": (4.0 * NJY, 1.4 * NJY)}
MC_DRAWS, MC_SEED = 3000, 9496                         # the worked-example setting

SED_PDF, CORNER_PDF = HERE / "cr3_sed.pdf", HERE / "cr3_corner.pdf"
RASTER_DPI = 400

# ------------------------------------------------------------- the app palette
BG, BG_RAISE, BG_INSET = "#f6f2ea", "#fffdf9", "#f3eee3"
LINE, LINE_STRONG = "#e4ddcc", "#c9c0aa"
INK, INK_DIM, INK_FAINT = "#2a2823", "#6c675a", "#97917f"
AMBER, ROSE, BRACE = "#b45309", "#be123c", "#3b4cca"
# band fills as the app's own export draws them (sampled from cr3_sed.pdf)
BAND_FILL = {"F200W": "#d8faa1", "F277W": "#ffcf7e", "F356W": "#faa780"}

MONO = ["DejaVu Sans Mono", "Menlo", "monospace"]
SANS = ["Helvetica", "Helvetica Neue", "Arial", "DejaVu Sans"]


def darken(color, f=0.55):
    r, g, b, _ = matplotlib.colors.to_rgba(color)
    return matplotlib.colors.to_hex((r * f, g * f, b * f))


def card(ax, x, y, w, h, fc=BG_RAISE, ec=LINE, lw=1.2, r=0.012, z=1):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", linewidth=lw,
        edgecolor=ec, facecolor=fc, transform=ax.transAxes, zorder=z,
        clip_on=False))


def rasterise(pdf: pathlib.Path) -> Image.Image:
    """The app's PDF export as a trimmed RGBA image."""
    with tempfile.TemporaryDirectory() as td:
        stem = pathlib.Path(td) / pdf.stem
        subprocess.run(["pdftocairo", "-png", "-r", str(RASTER_DPI),
                        "-singlefile", str(pdf), str(stem)], check=True)
        im = Image.open(stem.with_suffix(".png")).convert("RGBA")
        im.load()
    a = np.asarray(im)
    ink = (a[:, :, :3].min(axis=2) < 243) & (a[:, :, 3] > 0)
    if ink.any():                                      # trim the white margin
        ys, xs = np.where(ink)
        im = im.crop((int(xs.min()), int(ys.min()),
                      int(xs.max()) + 1, int(ys.max()) + 1))
    return im


def place(fig, im: Image.Image, cx, cy, w, h):
    """Draw `im` centred on (cx, cy), fitted inside w x h in figure fractions."""
    fw, fh = fig.get_size_inches()
    box_ar = (w * fw) / (h * fh)
    im_ar = im.width / im.height
    if im_ar > box_ar:                                 # width-limited
        dw, dh = w, w * fw / im_ar / fh
    else:                                              # height-limited
        dh, dw = h, h * fh * im_ar / fw
    ax = fig.add_axes([cx - dw / 2, cy - dh / 2, dw, dh])
    ax.imshow(im, interpolation="lanczos")
    ax.set_axis_off()
    return ax


# ------------------------------------------------------------------ input card
def draw_input(ax):
    ax.set_axis_off()
    card(ax, 0.0, 0.0, 1.0, 1.0, fc=BG_INSET, ec=LINE_STRONG, lw=1.4, r=0.03)
    ax.text(0.07, 0.945, "03", fontsize=13, family=MONO, color=AMBER,
            fontweight="bold", transform=ax.transAxes, va="center")
    ax.text(0.17, 0.945, "P H O T O M E T R Y", fontsize=12, family=MONO,
            color=INK, fontweight="bold", transform=ax.transAxes, va="center")
    for k, (tx, on) in {"µJy": (0.70, False), "nJy": (0.815, True),
                        "AB mag": (0.925, False)}.items():
        card(ax, tx - 0.052, 0.905, 0.104, 0.075,
             fc=INK if on else BG_RAISE, ec=LINE_STRONG, lw=0.9, r=0.02, z=2)
        ax.text(tx, 0.9425, k, fontsize=9.5, family=MONO,
                color=BG_RAISE if on else INK_DIM, ha="center", va="center",
                transform=ax.transAxes, zorder=3)
    ax.text(0.90, 0.845, f"z = {Z}", fontsize=12, family=MONO, color=INK,
            ha="right", va="center", transform=ax.transAxes)

    hdr = 0.745
    for t, x, ha in (("band", 0.09, "left"), ("flux [nJy]", 0.45, "center"),
                     ("± err", 0.83, "center")):
        ax.text(x, hdr, t, fontsize=10.5, family=MONO, color=INK_DIM,
                transform=ax.transAxes, va="center", ha=ha)
    ax.plot([0.07, 0.93], [hdr - 0.045] * 2, color=INK, lw=1.3,
            transform=ax.transAxes, clip_on=False)

    y = hdr - 0.130
    for b, (f_, e_) in PHOT.items():
        ax.plot([0.10], [y], "o", ms=9, color=BAND_FILL[b],
                markeredgecolor=darken(BAND_FILL[b], 0.75), mew=0.8,
                transform=ax.transAxes, clip_on=False, zorder=3)
        ax.text(0.16, y, b, fontsize=11.5, family=MONO, color=INK,
                fontweight="bold", transform=ax.transAxes, va="center")
        for val, cx, cw in ((f_ / NJY, 0.45, 0.30), (e_ / NJY, 0.83, 0.20)):
            card(ax, cx - cw / 2, y - 0.058, cw, 0.116, fc=BG_RAISE,
                 ec=LINE_STRONG, lw=0.9, r=0.018, z=2)
            ax.text(cx, y, f"{val:g}", fontsize=11.5, family=MONO, color=INK,
                    ha="center", va="center", transform=ax.transAxes, zorder=3)
        y -= 0.185

    ax.text(0.5, 0.105, f"Input:  {SOURCE}  ({REFERENCE})", fontsize=12.5,
            family=SANS, style="italic", color=BRACE, fontweight="bold",
            ha="center", va="center", transform=ax.transAxes)


# ----------------------------------------------------------------- output card
def draw_output(ax, res):
    ax.set_axis_off()
    card(ax, 0.0, 0.0, 1.0, 1.0, fc=BG_INSET, ec=LINE_STRONG, lw=1.4, r=0.035)
    ax.plot([0.055, 0.945], [0.875] * 2, color=AMBER, lw=3.0,
            transform=ax.transAxes, clip_on=False, solid_capstyle="round")
    p = res.ratios[0].value.percentiles
    ax.text(0.06, 0.70, "R3  =  [O III]5007 / H$\\beta$", fontsize=14,
            family=MONO, color=INK, transform=ax.transAxes, va="center")
    ax.text(0.06, 0.40, f"< {p.p975:.2f}", fontsize=39, family=SANS,
            color=AMBER, fontweight="bold", transform=ax.transAxes, va="center")
    card(ax, 0.575, 0.310, 0.375, 0.175, fc="#fdf2f5", ec=ROSE, lw=1.4, r=0.05, z=2)
    ax.text(0.7625, 0.3975, "2$\\sigma$ UPPER LIMIT", fontsize=10.5, family=MONO,
            color=ROSE, fontweight="bold", ha="center", va="center",
            transform=ax.transAxes, zorder=3)
    ax.text(0.06, 0.135, f"1$\\sigma$:  < {p.p84:.2f}", fontsize=13,
            family=MONO, color=INK_DIM, transform=ax.transAxes, va="center")


# ---------------------------------------------------------------------- brace
def draw_brace(fig, x_tip, y0, y1, w=0.016, color=BRACE, lw=3.0):
    """A '{' brace: point at x_tip mid-height, arms reaching right to x_tip+w."""
    xa, ym = x_tip + w, 0.5 * (y0 + y1)
    verts, codes = [], []
    for y_end in (y1, y0):
        d = y_end - ym
        verts += [(xa, y_end),
                  (xa - 0.55 * w, y_end), (xa - 0.45 * w, ym + 0.80 * d),
                  (xa - 0.5 * w, ym + 0.52 * d),
                  (xa - 0.55 * w, ym + 0.24 * d), (x_tip, ym + 0.16 * d),
                  (x_tip, ym)]
        codes += [Path.MOVETO] + [Path.CURVE4] * 6
    fig.add_artist(PathPatch(Path(verts, codes), fc="none", ec=color, lw=lw,
                             capstyle="round", joinstyle="round",
                             transform=fig.transFigure))


def main():
    base = FitConfig.fixed_slope(z=Z)
    res = fit(PHOT, base.model_copy(update={"mc": base.mc.model_copy(
        update={"n": MC_DRAWS, "seed": MC_SEED})}))
    p = res.ratios[0].value.percentiles
    print(f"{SOURCE}: R3 {res.ratios[0].status}  "
          f"< {p.p975:.2f} (2σ), < {p.p84:.2f} (1σ)")

    sed, corner = rasterise(SED_PDF), rasterise(CORNER_PDF)

    fig = plt.figure(figsize=(16, 9), dpi=200)
    fig.patch.set_facecolor(BG)

    fig.text(0.037, 0.955, "LATED", fontsize=30, family=SANS, color=INK,
             fontweight="bold", va="center")
    fig.text(0.125, 0.953, "inference", fontsize=24, family=SANS,
             color=INK_DIM, style="italic", va="center")
    fig.add_artist(plt.Line2D([0.035, 0.335], [0.917, 0.917], color=INK,
                              lw=2.2, transform=fig.transFigure))

    fig.text(0.185, 0.845, "I N P U T", fontsize=34, family=SANS, color=INK,
             fontweight="bold", ha="center", va="center")
    draw_input(fig.add_axes([0.035, 0.225, 0.300, 0.555]))

    draw_brace(fig, 0.392, 0.085, 0.925)
    fig.add_artist(FancyArrowPatch(
        (0.345, 0.505), (0.379, 0.505), transform=fig.transFigure,
        arrowstyle="-|>,head_width=7,head_length=9", color=BRACE, lw=3.2,
        mutation_scale=1.6))

    place(fig, sed, cx=0.705, cy=0.745, w=0.500, h=0.430)

    fig.text(0.560, 0.430, "O U T P U T", fontsize=34, family=SANS, color=INK,
             fontweight="bold", ha="center", va="center")
    draw_output(fig.add_axes([0.432, 0.100, 0.262, 0.210]), res)
    place(fig, corner, cx=0.850, cy=0.255, w=0.290, h=0.460)

    out = HERE / "webapp.png"
    fig.savefig(out, dpi=200, facecolor=BG)
    fig.savefig(out.with_suffix(".pdf"), facecolor=BG)
    print("wrote", out.name, "and", out.with_suffix(".pdf").name)


if __name__ == "__main__":
    main()
