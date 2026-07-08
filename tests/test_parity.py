"""Parity with the paper engine (photometry/line_recovery.py).

The default FitConfig must reproduce recover_lines_from_photometry exactly:
identical best-fit amplitudes/slope (deterministic) and identical Monte-Carlo
percentiles (the RNG draw order is mirrored).  Covered legacy paths: free and
fixed slope, z_sigma (with both slope modes), fast_mc, hb_factor (== editing
the Hbeta tie ratio), include_nii_sii (== with_contaminant_mode), and dust.

One DELIBERATE difference (see README "Differences from the paper engine"):
with dust_av > 0 the new R3 is the self-consistent observed (attenuated)
ratio, while the legacy engine divided the observed [O III] by an
intrinsic-frame Hbeta; they differ by the Hbeta-vs-Halpha attenuation factor
(identical at A_V = 0, where all published numbers live).  Dust cases
therefore skip the direct R3 comparison and pin the exact relation instead
(test_dust_r3_definitional_relation).

Requires the LATED repo root on sys.path; skipped on standalone installs.
"""

import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

legacy = pytest.importorskip("photometry.line_recovery")

from lated import FitConfig, default_filters, fit  # noqa: E402
from lated.dust import attenuation_ratio  # noqa: E402
from lated.lines import LINE_WAVELENGTHS  # noqa: E402

# The package uses VACUUM rest wavelengths while the paper pipeline tabulates
# the conventional air values (a < 2 AA rest-frame difference, negligible for
# band photometry but far above the 1e-9 parity tolerance).  Patch the legacy
# engine onto the same vacuum table so these tests isolate the ALGORITHM;
# the wavelength convention itself is a documented difference (README).
VACUUM_BALMER = [(LINE_WAVELENGTHS["Hbeta"], 1.0),
                 (LINE_WAVELENGTHS["Hgamma"], 0.468),
                 (LINE_WAVELENGTHS["Hdelta"], 0.259),
                 (LINE_WAVELENGTHS["Hepsilon"], 0.159),
                 (LINE_WAVELENGTHS["H8"], 0.105),
                 (LINE_WAVELENGTHS["H9"], 0.0731),
                 (LINE_WAVELENGTHS["H10"], 0.0530)]


@pytest.fixture(autouse=True)
def _legacy_on_vacuum_wavelengths(monkeypatch):
    import photometry.line_excess as le
    for name in ("Halpha", "Hbeta", "Hgamma", "Hdelta", "Hepsilon", "H8",
                 "H9", "H10", "OIII5007", "OIII4959", "OII3727", "HeI10830",
                 "NII6584", "SII6717", "SII6731"):
        monkeypatch.setitem(le.LINES, name, LINE_WAVELENGTHS[name])
    monkeypatch.setattr(legacy, "BALMER_SERIES", VACUUM_BALMER)
    yield

PHOT_5BAND = {"F150W": (0.05, 0.01), "F200W": (0.05, 0.01),
              "F277W": (0.50, 0.01), "F356W": (0.07, 0.01),
              "F444W": (0.06, 0.01)}
PHOT_3BAND = {"F200W": (0.0136, 0.0019), "F277W": (0.0249, 0.0016),
              "F356W": (0.0040, 0.0014)}
PHOT_DUST_O3 = {"F150W": (0.05, 0.01), "F200W": (0.40, 0.01),
                "F277W": (0.20, 0.01), "F356W": (0.07, 0.01),
                "F444W": (0.06, 0.01)}   # detected [O III] AND Halpha

# (id, z, photometry, legacy config, new-config kwargs, compare_r3)
CASES = [
    ("free-slope", 3.1, PHOT_5BAND, dict(nmc=200), dict(), True),
    ("three-band", 3.05, PHOT_3BAND, dict(nmc=200, fix_beta=-2.0),
     dict(three_band=True), True),
    ("wz2.1", 2.12, {"F150W": (0.30, 0.02), "F200W": (0.08, 0.02),
                     "F277W": (0.06, 0.02)},
     dict(nmc=150, fix_beta=-2.0), dict(three_band=True), True),
    ("wz6.1", 6.1, {"F356W": (0.02, 0.005), "F444W": (0.09, 0.005),
                    "F410M": (0.015, 0.006)},
     dict(nmc=150, fix_beta=-2.0), dict(three_band=True), True),
    ("zsigma-free", 2.12, {"F150W": (0.30, 0.02), "F200W": (0.08, 0.02),
                           "F277W": (0.06, 0.02), "F356W": (0.05, 0.02)},
     dict(nmc=200, z_sigma=0.03), dict(z_sigma=0.03), True),
    ("zsigma-fixed", 3.05, PHOT_3BAND,
     dict(nmc=200, fix_beta=-2.0, z_sigma=0.02),
     dict(three_band=True, z_sigma=0.02), True),
    ("fast-mc", 3.1, PHOT_5BAND, dict(nmc=200, fast_mc=True),
     dict(fast=True), True),
    ("hb-factor", 3.1, PHOT_DUST_O3, dict(nmc=200, hb_factor=1.5),
     dict(hb_factor=1.5), True),
    ("nii-sii", 3.1, PHOT_DUST_O3,
     dict(nmc=200, include_nii_sii=True, nii_sii_frac=0.35),
     dict(contaminant=0.35), True),
    ("dust-limit", 3.1, PHOT_5BAND, dict(nmc=150, dust_av=0.5),
     dict(dust_av=0.5), False),
    ("dust-detected", 3.1, PHOT_DUST_O3, dict(nmc=150, dust_av=0.5),
     dict(dust_av=0.5), False),
]
IDS = [c[0] for c in CASES]
PCTS = ["p025", "p16", "p50", "p84", "p975"]


def new_config(z, legacy_cfg, kw):
    kw = dict(kw)
    # pin the legacy defaults: the package now defaults to seed 9496 and
    # an A_V jitter of 0.01, neither of which the paper engine has
    extra = {"z_sigma": kw.pop("z_sigma", 0.0),
             "mc": {"n": legacy_cfg.get("nmc", 300), "seed": 20260612,
                    "fast": kw.pop("fast", False)},
             "dust": {"av": kw.pop("dust_av", 0.0) and legacy_cfg["dust_av"],
                      "av_sigma": 0.0}}
    if kw.pop("three_band", False):
        cfg = FitConfig.three_band(z, beta=legacy_cfg["fix_beta"], **extra)
    else:
        cfg = FitConfig.paper_default(z, **extra)
    hbf = kw.pop("hb_factor", None)
    if hbf:
        cfg = cfg.with_line_role("Hbeta", "tied", tied_to="Halpha",
                                 ratio=hbf / 2.86)
    frac = kw.pop("contaminant", None)
    if frac:
        cfg = cfg.with_contaminant_mode(frac)
    assert not kw, kw
    return cfg


def run_pair(z, phot, legacy_cfg, kw):
    from photometry.filters import load_all
    old = legacy.recover_lines_from_photometry(
        phot, load_all(), z, config=dict(legacy_cfg))
    new = fit(phot, new_config(z, legacy_cfg, kw), default_filters())
    return old, new


@pytest.mark.parametrize("cid,z,phot,legacy_cfg,kw,cmp_r3", CASES, ids=IDS)
def test_parity(cid, z, phot, legacy_cfg, kw, cmp_r3):
    old, new = run_pair(z, phot, legacy_cfg, kw)

    # best fit (deterministic)
    assert new.beta.best == pytest.approx(old["beta"], abs=1e-12)
    assert new.continuum_flam_at_pivot.best == pytest.approx(
        old["continuum_flam_at_pivot"], rel=1e-9, abs=1e-30)
    assert new.chi2 == pytest.approx(old["chi2"], rel=1e-9, abs=1e-20)

    # line fluxes: every published percentile, plus best and EW
    lines = {l.name: l for l in new.lines}
    for ln in ("Halpha", "OIII5007"):
        assert lines[ln].flux.best == pytest.approx(
            old[f"F_{ln}"]["best"], rel=1e-9, abs=1e-30), ln
        for p in PCTS:
            assert getattr(lines[ln].flux.percentiles, p) == pytest.approx(
                old[f"F_{ln}"][p], rel=1e-9, abs=1e-30), (ln, p)
        if f"EW0_{ln}" in old:
            assert lines[ln].ew0_rest == pytest.approx(
                old[f"EW0_{ln}"], rel=1e-9), ln

    # slope posterior
    for p in PCTS:
        assert getattr(new.beta.percentiles, p) == pytest.approx(
            old["beta_pct"][p], rel=1e-9, abs=1e-12), p

    # R3 (skipped for dust: deliberate definitional difference, see module
    # docstring and test_dust_r3_definitional_relation)
    if cmp_r3:
        r3 = new.ratios[0]
        assert r3.is_limit == old["R3_is_limit"]
        for p in PCTS:
            assert getattr(r3.value.percentiles, p) == pytest.approx(
                old["R3"][p], rel=1e-9, abs=1e-12), p


def test_dust_r3_definitional_relation():
    """With dust, new R3 = legacy R3 / attenuation_ratio(Hbeta, Halpha):
    the legacy denominator was the intrinsic-frame Hbeta, the new one is the
    observed (attenuated) Hbeta."""
    av = 0.5
    old, new = run_pair(3.1, PHOT_DUST_O3, dict(nmc=150, dust_av=av),
                        dict(dust_av=av))
    att = attenuation_ratio(LINE_WAVELENGTHS["Hbeta"],
                            LINE_WAVELENGTHS["Halpha"], av)
    assert att < 1.0
    r3 = new.ratios[0]
    assert r3.status == "measured"
    for p in ("p16", "p50", "p84"):
        assert getattr(r3.value.percentiles, p) == pytest.approx(
            old["R3"][p] / att, rel=1e-9), p


def test_with_line_role_revalidates():
    """Switching off a line that others are tied to must fail at config
    time with a clear message, not deep inside fit()."""
    cfg = FitConfig(z=3.05)
    with pytest.raises(Exception, match="tied to|Halpha"):
        cfg.with_line_role("Halpha", "off")
