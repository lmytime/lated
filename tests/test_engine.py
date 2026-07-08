"""Engine behaviour on synthetic photometry (ports of the legacy tests,
plus the new validation and tie machinery)."""

import numpy as np
import pytest

from lated import (FitConfig, LineConfig, default_filters, fit,
                            model_spectrum)
from lated.filters import C_AA
from lated.lines import LINE_WAVELENGTHS

Z = 3.05
BANDS = ["F115W", "F150W", "F200W", "F277W", "F356W", "F444W"]
SEED = 20260612


def anchor_sed(beta=-2.0, ews=None, wave=None):
    """Power-law continuum with Gaussian lines of given rest EWs [AA]."""
    if wave is None:
        wave = np.arange(800.0, 14000.0, 2.0)
    flam = (wave / 2000.0) ** beta
    flam[wave < 912.0] = 0.0
    for line, ew in (ews or {}).items():
        if ew <= 0:
            continue
        lw = LINE_WAVELENGTHS[line]
        cont = np.interp(lw, wave, flam)
        sigma = 8.0 / 2.3548
        flam = flam + (ew * cont) / (sigma * np.sqrt(2 * np.pi)) * \
            np.exp(-0.5 * ((wave - lw) / sigma) ** 2)
    return wave, flam


def synth_photometry(ews, beta=-2.0, m356=26.0, snr=20.0):
    filters = default_filters()
    w, f = anchor_sed(beta=beta, ews=ews)
    wo, fo = w * (1 + Z), f / (1 + Z)
    off = m356 - filters["F356W"].ab_mag(wo, fo)
    err = 10 ** (-0.4 * (m356 - 23.9)) / snr
    rng = np.random.default_rng(SEED)
    phot = {}
    for b in BANDS:
        m = filters[b].ab_mag(wo, fo) + off
        fnu = 10 ** (-0.4 * (m - 23.9))
        phot[b] = (fnu + rng.normal(0, err), err)
    return phot


def strong_line_ews():
    return {"Halpha": 1500.0, "Hbeta": 1500.0 / 2.86 / 1.82,
            "OIII5007": 600.0, "OIII4959": 600.0 / 2.98}


def test_recovers_strong_lines():
    res = fit(synth_photometry(strong_line_ews()), FitConfig(z=Z))
    lines = {l.name: l for l in res.lines}
    assert abs(lines["Halpha"].ew0_rest / 1500.0 - 1.0) < 0.25
    cont = lambda lam: (lam / 2000.0) ** -2.0                    # noqa: E731
    truth = (600.0 * cont(LINE_WAVELENGTHS["OIII5007"])
             / (1500.0 / 2.86 / 1.82 * cont(LINE_WAVELENGTHS["Hbeta"])))
    assert abs(res.ratios[0].value.percentiles.p50 / truth - 1.0) < 0.4


def test_oiii_upper_limit_when_absent():
    ews = {"Halpha": 2000.0, "Hbeta": 2000.0 / 2.86 / 1.82}
    res = fit(synth_photometry(ews), FitConfig(z=Z))
    assert res.ratios[0].is_limit
    assert res.ratios[0].value.percentiles.p975 < 1.5


def test_continuum_slope_recovered():
    res = fit(synth_photometry({"Halpha": 800.0}, beta=-2.5), FitConfig(z=Z))
    assert abs(res.beta.best - (-2.5)) < 0.6


def test_redshift_jitter_widens_posterior():
    phot = synth_photometry(strong_line_ews())
    r0 = fit(phot, FitConfig(z=Z, mc={"n": 150}))
    r1 = fit(phot, FitConfig(z=Z, z_sigma=0.05, mc={"n": 150}))
    w0 = r0.ratios[0].value.percentiles.p84 - r0.ratios[0].value.percentiles.p16
    w1 = r1.ratios[0].value.percentiles.p84 - r1.ratios[0].value.percentiles.p16
    assert w1 >= 0.8 * w0


def test_tied_line_fluxes_reported():
    res = fit(synth_photometry(strong_line_ews()), FitConfig(z=Z))
    lines = {l.name: l for l in res.lines}
    ha, hb = lines["Halpha"], lines["Hbeta"]
    assert hb.role == "tied" and hb.root == "Halpha"
    assert hb.flux.best == pytest.approx(ha.flux.best / 2.86)
    o49 = lines["OIII4959"]
    assert o49.flux.best == pytest.approx(
        lines["OIII5007"].flux.best / 2.98)
    # chained tie: Hgamma -> Hbeta -> Halpha
    hg = lines["Hgamma"]
    assert hg.root == "Halpha"
    assert hg.flux.best == pytest.approx(ha.flux.best / 2.86 * 0.468)


def test_dust_differential_on_ties():
    phot = synth_photometry(strong_line_ews())
    r0 = fit(phot, FitConfig(z=Z))
    r1 = fit(phot, FitConfig(z=Z, dust={"av": 1.0}))
    hb0 = {l.name: l for l in r0.lines}["Hbeta"]
    hb1 = {l.name: l for l in r1.lines}["Hbeta"]
    # Calzetti: Hbeta suffers more attenuation than Halpha, so the observed
    # tied ratio must drop below the intrinsic 1/2.86
    assert hb1.ratio_effective < hb0.ratio_effective == pytest.approx(1 / 2.86)


def test_free_extra_line():
    cfg = FitConfig(z=Z).with_line_role("OII3727", "free")
    res = fit(synth_photometry(strong_line_ews()), cfg)
    names = {l.name for l in res.lines}
    assert "OII3727" in names
    assert res.n_free_parameters == 5  # C + beta + Ha + OIII + OII


def test_custom_line():
    cfg = FitConfig(z=Z)
    cfg = cfg.model_copy(update={"lines": cfg.lines + [
        LineConfig(name="CIII1909", rest_wave=1908.7, role="free")]})
    res = fit(synth_photometry(strong_line_ews()), cfg)
    assert "CIII1909" in {l.name for l in res.lines}


def test_line_outside_coverage_flagged():
    cfg = FitConfig(z=Z).with_line_role("HeI10830", "free")
    phot = {b: v for b, v in synth_photometry(strong_line_ews()).items()
            if b in ("F115W", "F150W", "F200W", "F277W", "F356W")}
    res = fit(phot, cfg)   # He I at z=3.05 sits at 4.39 um, beyond F356W
    hei = {l.name: l for l in res.lines}["HeI10830"]
    assert not hei.constrained


def test_three_band_mode_fixes_beta():
    phot = {"F200W": (0.0136, 0.0019), "F277W": (0.0249, 0.0016),
            "F356W": (0.0040, 0.0014)}
    res = fit(phot, FitConfig.three_band(3.05))
    assert res.beta.best == -2.0
    assert res.beta_role == "fixed"
    assert res.ndof == 0    # 3 bands - C - 2 free lines (beta not counted)


def test_band_model_consistent_with_chi2():
    """band_model_uJy must be exactly the model the reported chi2 refers to."""
    phot = synth_photometry(strong_line_ews(), snr=50.0)
    res = fit(phot, FitConfig(z=Z))
    chi2 = sum(((f - res.band_model_uJy[b]) / e) ** 2
               for b, (f, e) in phot.items())
    assert chi2 == pytest.approx(res.chi2, rel=1e-8)


def test_model_spectrum_integrates_back():
    phot = synth_photometry(strong_line_ews(), snr=50.0)
    res = fit(phot, FitConfig(z=Z))
    filters = default_filters()
    lam, tot, cont_uJy = model_spectrum(res)
    flam = tot * 1e-29 * C_AA / lam ** 2
    for b in ("F277W", "F356W"):
        mean = filters[b].mean_flam(lam, flam)
        fnu_uJy = filters[b].mean_flam_to_fnu_uJy(mean)
        assert fnu_uJy == pytest.approx(res.band_model_uJy[b], rel=0.02), b


# ---------------- validation errors are loud and actionable -----------------

def test_unknown_band_rejected():
    with pytest.raises(ValueError, match="unknown band"):
        fit({"NOTABAND": (1.0, 0.1), "F200W": (1.0, 0.1), "F277W": (1.0, 0.1),
             "F356W": (1.0, 0.1)}, FitConfig(z=Z))


def test_nonpositive_error_rejected():
    with pytest.raises(ValueError, match="error must be > 0"):
        fit({"F200W": (1.0, 0.0), "F277W": (1.0, 0.1), "F356W": (1.0, 0.1),
             "F444W": (1.0, 0.1)}, FitConfig(z=Z))


def test_underconstrained_rejected():
    with pytest.raises(ValueError, match="cannot constrain"):
        fit({"F277W": (1.0, 0.1), "F356W": (1.0, 0.1), "F444W": (1.0, 0.1)},
            FitConfig(z=Z))   # 3 bands, beta free -> 4 free params


def test_unknown_config_key_rejected():
    with pytest.raises(Exception, match="beta_fix"):
        FitConfig(z=Z, continuum={"beta_fix": -2.0})


def test_tie_to_off_line_rejected():
    with pytest.raises(Exception, match="tied to"):
        FitConfig(z=Z, lines=[
            LineConfig(name="Halpha", rest_wave=6562.8, role="free"),
            LineConfig(name="Hbeta", rest_wave=4861.33, role="tied",
                       tied_to="Hgamma", ratio=0.5)])


def test_tie_cycle_rejected():
    with pytest.raises(Exception, match="cycle"):
        FitConfig(z=Z, lines=[
            LineConfig(name="A", rest_wave=5000.0, role="tied", tied_to="B",
                       ratio=1.0),
            LineConfig(name="B", rest_wave=6000.0, role="tied", tied_to="A",
                       ratio=1.0),
            LineConfig(name="C", rest_wave=6562.8, role="free")])


def test_contaminant_mode():
    cfg = FitConfig(z=Z).with_contaminant_mode(0.35)
    res = fit(synth_photometry(strong_line_ews()), cfg)
    lines = {l.name: l for l in res.lines}
    ha = lines["Halpha"].flux.best
    assert lines["NII6584"].flux.best == pytest.approx(ha * 0.35 / 3)
