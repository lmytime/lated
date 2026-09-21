"""Build docs/webapp.png: the README figure for the lated workbench.

The layout follows the web app itself, left to right: the photometry you type
in, then what the fit gives back.  Everything here is drawn from a real run of
the packaged API, so the numbers in the figure are the numbers the app reports
for the same input.

    python docs/make_webapp_figure.py

Worked example: MPG-CR3 (Cai et al. 2025), a metal-free candidate at z=3.193
whose [O III] is undetected, so R3 comes back as an upper limit.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.path import Path
from matplotlib.patches import PathPatch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lated import FitConfig, fit                       # noqa: E402
from lated.engine import model_spectrum                # noqa: E402
from lated.filters import default_filters              # noqa: E402

# ---------------------------------------------------------------- the example
NJY = 1e-3                                             # nJy -> uJy
SOURCE = "MPG-CR3"
REFERENCE = "Cai+2025"
Z = 3.193
PHOT = {"F200W": (13.6 * NJY, 1.9 * NJY),
        "F277W": (24.9 * NJY, 1.6 * NJY),
        "F356W": (4.0 * NJY, 1.4 * NJY)}
MC_DRAWS = 3000                                        # the worked-example setting
MC_SEED = 9496

# ------------------------------------------------------------- the app palette
BG          = "#f6f2ea"
BG_RAISE    = "#fffdf9"
BG_INSET    = "#f3eee3"
LINE        = "#e4ddcc"
LINE_STRONG = "#c9c0aa"
INK         = "#2a2823"
INK_DIM     = "#6c675a"
INK_FAINT   = "#97917f"
AMBER       = "#b45309"
ROSE        = "#be123c"
CYAN        = "#0e7490"
BRACE       = "#3b4cca"

MONO = ["DejaVu Sans Mono", "Menlo", "monospace"]
SANS = ["Helvetica", "Helvetica Neue", "Arial", "DejaVu Sans"]


def band_color(pivot_aa: float) -> tuple:
    """The app's bandColor(): piecewise-log pivot wavelength into turbo."""
    um = pivot_aa / 1e4
    seg = lambda v, lo, hi: (np.log(v) - np.log(lo)) / (np.log(hi) - np.log(lo))
    if um <= 5.6:
        t = 0.80 * min(1.0, max(0.0, seg(um, 0.3, 5.6)))
    else:
        t = 0.80 + 0.20 * min(1.0, max(0.0, seg(um, 5.6, 27)))
    return matplotlib.colormaps["turbo"](0.06 + 0.88 * t)


def darken(color, f=0.62):
    """Darkened variant, as hex: matplotlib reads a bare RGBA 4-tuple as one
    colour per dataset in some calls (hist), so keep colours as strings."""
    r, g, b, _ = matplotlib.colors.to_rgba(color)
    return matplotlib.colors.to_hex((r * f, g * f, b * f))


def card(ax, x, y, w, h, fc=BG_RAISE, ec=LINE, lw=1.2, r=0.012, z=1):
    """A rounded panel in the app's card style, in axes coordinates."""
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                       linewidth=lw, edgecolor=ec, facecolor=fc,
                       transform=ax.transAxes, zorder=z, clip_on=False)
    ax.add_patch(p)
    return p


# ------------------------------------------------------------------ run the fit
def run():
    base = FitConfig.fixed_slope(z=Z)
    cfg = base.model_copy(update={"mc": base.mc.model_copy(
        update={"n": MC_DRAWS, "seed": MC_SEED, "keep_draws": True})})
    return fit(PHOT, cfg)


# --------------------------------------------------------------- the SED panel
def draw_sed(ax, res, filters):
    wave, total, cont = model_spectrum(res)
    um = wave / 1e4

    ax.set_facecolor(BG_RAISE)
    ax.set_yscale("log")
    lo = min(total.min(), cont.min()) * 0.40
    hi = total.max() * 4.0
    ax.set_ylim(lo, hi)
    ax.set_xlim(um.min(), um.max())

    # filter transmission curves, in the bottom fifth of the panel
    span = np.log10(hi / lo)
    dec = lambda frac: lo * 10 ** (span * frac)          # fraction of the y-range
    for b in res.bands:
        f = filters[b]
        col = band_color(f.pivot)
        t = f.trans / f.trans.max()
        y = dec(0.012 + 0.175 * t)
        ax.fill_between(f.wave / 1e4, dec(0.012), y, color=col, alpha=0.32,
                        lw=0, zorder=1)
        ax.plot(f.wave / 1e4, y, color=col, lw=1.1, alpha=0.75, zorder=1.1)
        ax.text(f.pivot / 1e4, dec(0.048), b, ha="center", va="center",
                color=darken(col, 0.5), fontsize=11, fontweight="bold",
                family=MONO, zorder=2)

    ax.plot(um, total, color=CYAN, lw=1.15, zorder=4, label="best-fit model")

    # observed photometry and the model re-integrated through each band
    piv = np.array([filters[b].pivot / 1e4 for b in res.bands])
    obs = np.array([PHOT[b][0] for b in res.bands])
    err = np.array([PHOT[b][1] for b in res.bands])
    mod = np.array([res.band_model_uJy[b] for b in res.bands])
    ax.errorbar(piv, obs, yerr=err, fmt="o", ms=6.5, color=INK, ecolor=INK,
                elinewidth=1.3, capsize=2.5, zorder=6, label="photometry")
    ax.plot(piv, mod, "s", ms=9, mfc="none", mec=AMBER, mew=1.7, zorder=5,
            label="model in bands")

    # line identifications above the frame; doublets share one label and
    # crowded labels are pushed apart, each keeping a connector to its line
    labels = [(lr.obs_wave / 1e4, lr.name) for lr in res.lines
              if lr.flux.best > 0]
    merged = [m for m in _merge_labels(labels) if um.min() < m[0] < um.max()]
    x0, x1 = ax.get_xlim()
    frac = [(x - x0) / (x1 - x0) for x, _, _ in merged]
    placed = _spread(frac, pitch=0.034)
    for (x, txt, hot), fx in zip(merged, placed):
        col = ROSE if hot else INK_DIM
        ax.axvline(x, color=ROSE if hot else INK_FAINT, lw=0.75,
                   ls=(0, (2.5, 2.5)), alpha=0.85 if hot else 0.5, zorder=3)
        ax.annotate(txt, xy=(x, 1.0), xytext=(fx, 1.035),
                    xycoords=("data", "axes fraction"),
                    textcoords="axes fraction", rotation=90,
                    ha="center", va="bottom", fontsize=10.5, family=SANS,
                    color=col, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color=col,
                                    shrinkA=1.5, shrinkB=0.5, alpha=0.8))

    ax.set_xlabel("observed wavelength  [$\\mu$m]", fontsize=12.5, family=SANS,
                  color=INK, labelpad=6)
    ax.set_ylabel("f$_{\\nu}$  [$\\mu$Jy]", fontsize=12.5, family=SANS, color=INK)
    ax.tick_params(labelsize=11, colors=INK_DIM, which="both")
    for s in ax.spines.values():
        s.set_color(LINE_STRONG)
    ax.grid(True, which="major", color=LINE, lw=0.7, alpha=0.7, zorder=0)
    leg = ax.legend(loc="upper right", fontsize=10.5, frameon=True,
                    facecolor=BG_RAISE, edgecolor=LINE, framealpha=0.95)
    for t in leg.get_texts():
        t.set_color(INK)
        t.set_family(SANS)


def _spread(x, pitch):
    """Push sorted positions apart to at least `pitch`, keeping the set as
    close to where it started as possible (one forward, one backward pass)."""
    v = list(x)
    for i in range(1, len(v)):
        if v[i] - v[i - 1] < pitch:
            v[i] = v[i - 1] + pitch
    over = v[-1] - 1.0 if v and v[-1] > 1.0 else 0.0
    if over > 0:
        v = [u - over for u in v]
        for i in range(len(v) - 2, -1, -1):
            if v[i + 1] - v[i] < pitch:
                v[i] = v[i + 1] - pitch
    return v


def _merge_labels(labels, tol=0.030):
    """Collapse doublets into one species label, mark the R3 numerator red."""
    pretty = {"Halpha": "H$\\alpha$", "Hbeta": "H$\\beta$",
              "Hgamma": "H$\\gamma$", "Hdelta": "H$\\delta$",
              "Hepsilon": "H$\\epsilon$", "H8": "H8", "H9": "H9", "H10": "H10",
              "OIII5007": "[O III]", "OIII4959": "[O III]"}
    out, used = [], set()
    labels = sorted(labels)
    for i, (x, n) in enumerate(labels):
        if i in used:
            continue
        group = [(x, n)]
        for j in range(i + 1, len(labels)):
            if j not in used and abs(labels[j][0] - x) < tol and \
                    pretty.get(labels[j][1]) == pretty.get(n):
                group.append(labels[j])
                used.add(j)
        xm = float(np.mean([g[0] for g in group]))
        hot = n.startswith("OIII")
        out.append((xm, pretty.get(n, n), hot))
    return out


# ------------------------------------------------------------ the corner plot
def draw_corner(fig, rect, res):
    d = res.posterior_draws
    keys = [k for k in ("C", "Halpha", "OIII5007") if k in d]
    lbl = {"C": "C", "Halpha": "H$\\alpha$", "OIII5007": "[O III]5007"}
    n = len(keys)
    x0, y0, w, h = rect
    pad = 0.006
    cw, ch = (w - pad * (n - 1)) / n, (h - pad * (n - 1)) / n
    data = {k: np.asarray(d[k], float) for k in keys}
    scale = {k: 10 ** np.floor(np.log10(np.percentile(np.abs(v[v != 0]), 99)))
             if np.any(v != 0) else 1.0 for k, v in data.items()}

    for i, ky in enumerate(keys):
        for j, kx in enumerate(keys):
            if j > i:
                continue
            ax = fig.add_axes([x0 + j * (cw + pad),
                               y0 + (n - 1 - i) * (ch + pad), cw, ch])
            ax.set_facecolor(BG_RAISE)
            X, Y = data[kx] / scale[kx], data[ky] / scale[ky]
            if i == j:
                ax.hist(X, bins=42, color=AMBER, alpha=0.55,
                        edgecolor=darken(AMBER, 0.85),
                        linewidth=0.5)
                for q, ls in ((16, ":"), (50, "--"), (84, ":")):
                    ax.axvline(np.percentile(X, q), color=INK_DIM, lw=0.9, ls=ls)
                ax.set_yticks([])
                p16, p50, p84 = np.percentile(X, [16, 50, 84])
                ax.set_title(f"{lbl[ky]} = ${p50:.2f}^{{+{p84-p50:.2f}}}"
                             f"_{{-{p50-p16:.2f}}}$", fontsize=9.5,
                             family=SANS, color=INK, pad=4)
            else:
                ax.plot(X, Y, ".", ms=1.0, color=CYAN, alpha=0.20, zorder=1)
                _contour(ax, X, Y)
                ax.plot(np.median(X), np.median(Y), "+", color=ROSE, ms=8,
                        mew=1.6, zorder=4)
            for s in ax.spines.values():
                s.set_color(LINE_STRONG)
                s.set_linewidth(0.8)
            ax.tick_params(labelsize=7.5, colors=INK_FAINT, length=2.5)
            if i == n - 1:
                ax.set_xlabel(lbl[kx], fontsize=9.5, family=SANS, color=INK,
                              labelpad=2)
            else:
                ax.set_xticklabels([])
            if j == 0 and i != 0:
                ax.set_ylabel(lbl[ky], fontsize=9.5, family=SANS, color=INK,
                              labelpad=2)
            else:
                ax.set_yticklabels([])

    # the reported ratio, in the free upper-right corner of the triangle
    r3 = res.ratios[0]
    draws = np.asarray(d.get(r3.name, []), float)
    if draws.size:
        lim = r3.value.percentiles.p975
        axr = fig.add_axes([x0 + 1.46 * (cw + pad),
                            y0 + (n - 1) * (ch + pad) + 0.26 * ch,
                            w - 1.46 * (cw + pad), 0.74 * ch])
        axr.set_facecolor(BG_RAISE)
        top = np.percentile(draws, 99.5)
        axr.hist(np.clip(draws, None, top), bins=40, range=(0, top),
                 color=AMBER, alpha=0.55, edgecolor=darken(AMBER, 0.85),
                 linewidth=0.5)
        axr.axvspan(0, lim, color=ROSE, alpha=0.07, lw=0)
        axr.axvline(lim, color=ROSE, lw=1.6)
        axr.axvline(r3.value.percentiles.p84, color=ROSE, lw=1.0,
                    ls=(0, (3, 2)))
        axr.set_xlim(0, top)
        axr.set_yticks([])
        axr.set_title(f"R3 < {lim:.2f}  (2$\\sigma$)", fontsize=10,
                      family=SANS, color=ROSE, pad=4)
        axr.tick_params(labelsize=7.5, colors=INK_FAINT, length=2.5)
        for s in axr.spines.values():
            s.set_color(LINE_STRONG)
            s.set_linewidth(0.8)


def _contour(ax, X, Y):
    H, xe, ye = np.histogram2d(X, Y, bins=26)
    H = H.T
    if H.max() <= 0:
        return
    s = np.sort(H.ravel())[::-1]
    cum = np.cumsum(s) / s.sum()
    lv = [s[np.searchsorted(cum, f)] for f in (0.393, 0.865)][::-1]
    lv = sorted(set(float(v) for v in lv))
    if len(lv) < 1:
        return
    xc = 0.5 * (xe[1:] + xe[:-1])
    yc = 0.5 * (ye[1:] + ye[:-1])
    ax.contour(xc, yc, H, levels=lv, colors=[CYAN], linewidths=0.9, zorder=3)


# ------------------------------------------------------------------ input card
def draw_input(ax, res, filters):
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

    hdr_y = 0.745
    ax.text(0.09, hdr_y, "band", fontsize=10.5, family=MONO, color=INK_DIM,
            transform=ax.transAxes, va="center")
    ax.text(0.45, hdr_y, "flux [nJy]", fontsize=10.5, family=MONO,
            color=INK_DIM, transform=ax.transAxes, va="center", ha="center")
    ax.text(0.83, hdr_y, "± err", fontsize=10.5, family=MONO,
            color=INK_DIM, transform=ax.transAxes, va="center", ha="center")
    ax.plot([0.07, 0.93], [hdr_y - 0.045] * 2, color=INK, lw=1.3,
            transform=ax.transAxes, clip_on=False)

    y = hdr_y - 0.130
    for b in res.bands:
        col = band_color(filters[b].pivot)
        ax.plot([0.10], [y], "o", ms=9, color=col, transform=ax.transAxes,
                clip_on=False, zorder=3)
        ax.text(0.16, y, b, fontsize=11.5, family=MONO, color=INK,
                fontweight="bold", transform=ax.transAxes, va="center")
        for val, cx, cw_ in ((PHOT[b][0] / NJY, 0.45, 0.30),
                             (PHOT[b][1] / NJY, 0.83, 0.20)):
            card(ax, cx - cw_ / 2, y - 0.058, cw_, 0.116, fc=BG_RAISE,
                 ec=LINE_STRONG, lw=0.9, r=0.018, z=2)
            ax.text(cx, y, f"{val:g}", fontsize=11.5, family=MONO, color=INK,
                    ha="center", va="center", transform=ax.transAxes, zorder=3)
        y -= 0.185

    ax.text(0.5, 0.105, f"Input:  {SOURCE}  ({REFERENCE})", fontsize=12.5,
            family=SANS, style="italic", color=BRACE, fontweight="bold",
            ha="center", va="center", transform=ax.transAxes)


def draw_strip(ax, res, filters):
    """The coverage strip under the input card."""
    ax.set_facecolor(BG_RAISE)
    lo = min(filters[b].wave.min() for b in res.bands) / 1e4 * 0.90
    hi = max(filters[b].wave.max() for b in res.bands) / 1e4 * 1.08
    for b in res.bands:
        f = filters[b]
        col = band_color(f.pivot)
        t = f.trans / f.trans.max()
        ax.fill_between(f.wave / 1e4, 0, t, color=col, alpha=0.40, lw=0)
        ax.plot(f.wave / 1e4, t, color=col, lw=1.0, alpha=0.8)
    for lr in res.lines:
        if lr.flux.best <= 0:
            continue
        x = lr.obs_wave / 1e4
        if lo < x < hi:
            hot = lr.name.startswith("OIII")
            ax.axvline(x, color=ROSE if hot else INK_FAINT, lw=1.1 if hot else 0.7,
                       ls="-" if hot else (0, (2, 2)), alpha=0.9)
    ax.set_xlim(lo, hi)
    ax.set_ylim(0, 1.15)
    ax.set_yticks([])
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_color(LINE_STRONG)
    ax.text(0.0, -0.10, f"{lo:.1f} µm", transform=ax.transAxes,
            fontsize=9.5, family=MONO, color=INK_FAINT, va="top")
    ax.text(1.0, -0.10, f"{hi:.1f} µm", transform=ax.transAxes,
            fontsize=9.5, family=MONO, color=INK_FAINT, ha="right", va="top")


# ----------------------------------------------------------------- output card
def draw_output(ax, res):
    ax.set_axis_off()
    card(ax, 0.0, 0.0, 1.0, 1.0, fc=BG_INSET, ec=LINE_STRONG, lw=1.4, r=0.035)
    ax.plot([0.055, 0.945], [0.875] * 2, color=AMBER, lw=3.0,
            transform=ax.transAxes, clip_on=False, solid_capstyle="round")

    r3 = res.ratios[0]
    p = r3.value.percentiles
    ax.text(0.06, 0.70, "R3  =  [O III]5007 / H$\\beta$", fontsize=14,
            family=MONO, color=INK, transform=ax.transAxes, va="center")
    ax.text(0.06, 0.40, f"< {p.p975:.2f}", fontsize=44, family=SANS,
            color=AMBER, fontweight="bold", transform=ax.transAxes,
            va="center")
    card(ax, 0.47, 0.305, 0.46, 0.185, fc="#fdf2f5", ec=ROSE, lw=1.4, r=0.05, z=2)
    ax.text(0.70, 0.3975, "2$\\sigma$  UPPER LIMIT", fontsize=11.5,
            family=MONO, color=ROSE, fontweight="bold", ha="center",
            va="center", transform=ax.transAxes, zorder=3)
    ax.text(0.06, 0.135, f"1$\\sigma$:  < {p.p84:.2f}", fontsize=13,
            family=MONO, color=INK_DIM, transform=ax.transAxes, va="center")


# ---------------------------------------------------------------------- brace
def draw_brace(fig, x_tip, y0, y1, w=0.016, color=BRACE, lw=3.0):
    """A '{' brace: point at x_tip mid-height, arms reaching right to x_tip+w."""
    xa, ym = x_tip + w, 0.5 * (y0 + y1)
    verts, codes = [], []
    for y_end in (y1, y0):                      # upper arm, then lower arm
        d = y_end - ym                          # signed half-height
        knee = (xa - 0.5 * w, ym + 0.52 * d)
        verts += [(xa, y_end),
                  (xa - 0.55 * w, y_end), (xa - 0.45 * w, ym + 0.80 * d), knee,
                  (xa - 0.55 * w, ym + 0.24 * d), (x_tip, ym + 0.16 * d),
                  (x_tip, ym)]
        codes += [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
                  Path.CURVE4, Path.CURVE4, Path.CURVE4]
    fig.add_artist(PathPatch(Path(verts, codes), fc="none", ec=color, lw=lw,
                             capstyle="round", joinstyle="round",
                             transform=fig.transFigure))


def main():
    res = run()
    filters = default_filters()
    r3 = res.ratios[0]
    print(f"{SOURCE}: R3 {r3.status}  < {r3.value.percentiles.p975:.2f} (2σ), "
          f"< {r3.value.percentiles.p84:.2f} (1σ)")

    fig = plt.figure(figsize=(16, 9), dpi=200)
    fig.patch.set_facecolor(BG)

    # ---- masthead
    fig.text(0.037, 0.955, "LATED", fontsize=30, family=SANS, color=INK,
             fontweight="bold", va="center")
    fig.text(0.125, 0.953, "inference", fontsize=24, family=SANS,
             color=INK_DIM, style="italic", va="center")
    fig.add_artist(plt.Line2D([0.035, 0.335], [0.917, 0.917], color=INK,
                              lw=2.2, transform=fig.transFigure))

    # ---- left column: INPUT
    fig.text(0.185, 0.845, "I N P U T", fontsize=34, family=SANS, color=INK,
             fontweight="bold", ha="center", va="center")
    ax_in = fig.add_axes([0.035, 0.235, 0.300, 0.545])
    draw_input(ax_in, res, filters)
    ax_strip = fig.add_axes([0.047, 0.115, 0.276, 0.085])
    draw_strip(ax_strip, res, filters)

    # ---- the brace and arrow
    draw_brace(fig, 0.392, 0.085, 0.925)
    fig.add_artist(FancyArrowPatch((0.345, 0.505), (0.379, 0.505),
                                   transform=fig.transFigure,
                                   arrowstyle="-|>,head_width=7,head_length=9",
                                   color=BRACE, lw=3.2, mutation_scale=1.6))

    # ---- right column: the SED, then OUTPUT
    ax_sed = fig.add_axes([0.470, 0.585, 0.505, 0.350])
    draw_sed(ax_sed, res, filters)

    fig.text(0.585, 0.470, "O U T P U T", fontsize=34, family=SANS, color=INK,
             fontweight="bold", ha="center", va="center")
    ax_out = fig.add_axes([0.448, 0.135, 0.265, 0.235])
    draw_output(ax_out, res)
    draw_corner(fig, (0.745, 0.075, 0.232, 0.435), res)

    out = pathlib.Path(__file__).resolve().parent / "webapp.png"
    fig.savefig(out, dpi=200, facecolor=BG)
    fig.savefig(out.with_suffix(".pdf"), facecolor=BG)
    print("wrote", out, "and", out.with_suffix(".pdf").name)


if __name__ == "__main__":
    main()
