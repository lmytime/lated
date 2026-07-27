"""Tests for the engine improvements driven by the multi-agent review of the
paper engine: boundary-safe posterior limits, ratio statuses, EW percentiles,
sensitivities and warnings."""

import pytest

from lated import FitConfig, RatioConfig, default_filters, fit

from test_engine import Z, synth_photometry, strong_line_ews


def shifted_photometry(shift_band, nsigma, ews=None, snr=15.0):
    """Synthetic photometry with one band shifted by nsigma errors."""
    phot = dict(synth_photometry(ews or {"Halpha": 1500.0,
                                         "Hbeta": 1500.0 / 2.86 / 1.82},
                                 snr=snr))
    f, e = phot[shift_band]
    phot[shift_band] = (f + nsigma * e, e)
    return phot


def test_bootstrap_limit_can_collapse_but_is_warned():
    """The review's scenario: no [O III], the [O III] band (F200W at z=3.05)
    fluctuates 2.5 sigma low.  Bootstrap collapses to a zero upper limit;
    the engine must at least warn about it."""
    phot = shifted_photometry("F200W", -2.5)
    res = fit(phot, FitConfig(z=Z, mc={"method": "bootstrap"}))
    o3 = {l.name: l for l in res.lines}["OIII5007"]
    if o3.flux.percentiles.p975 < 0.5 * o3.flux_sensitivity_1sig:
        assert any("boundary artefact" in w for w in res.warnings), res.warnings


def test_posterior_limit_respects_depth():
    """Same scenario with mc.method='posterior': the 97.5% upper limit must
    be positive and of order the photometric depth, not zero."""
    phot = shifted_photometry("F200W", -2.5)
    res = fit(phot, FitConfig(z=Z, mc={"method": "posterior"}))
    o3 = {l.name: l for l in res.lines}["OIII5007"]
    assert o3.flux.percentiles.p975 > 0
    assert o3.flux.percentiles.p975 > 0.3 * o3.flux_sensitivity_1sig
    r3 = res.ratios[0]
    assert r3.status == "upper_limit"
    assert r3.value.percentiles.p975 > 0


def test_posterior_matches_bootstrap_when_well_detected():
    """For strong lines away from the boundary the two methods must agree."""
    phot = synth_photometry(strong_line_ews(), snr=30.0)
    rb = fit(phot, FitConfig(z=Z, mc={"n": 400, "method": "bootstrap"}))
    rp = fit(phot, FitConfig(z=Z, mc={"n": 400, "method": "posterior"}))
    for name in ("Halpha", "OIII5007"):
        fb = {l.name: l for l in rb.lines}[name].flux
        fp = {l.name: l for l in rp.lines}[name].flux
        width_b = fb.percentiles.p84 - fb.percentiles.p16
        assert abs(fp.percentiles.p50 - fb.percentiles.p50) < 1.0 * width_b
        width_p = fp.percentiles.p84 - fp.percentiles.p16
        assert 0.4 < width_p / width_b < 2.5, (name, width_p, width_b)


def test_ratio_lower_limit_status():
    """Strong [O III], Halpha at continuum: the data support only a LOWER
    limit on R3 -- a state the paper engine could not represent."""
    phot = {"F150W": (0.05, 0.01), "F200W": (0.50, 0.01), "F277W": (0.05, 0.01),
            "F356W": (0.05, 0.01), "F444W": (0.045, 0.01)}
    res = fit(phot, FitConfig(z=Z, mc={"method": "bootstrap"}))
    r3 = res.ratios[0]
    assert r3.status in ("lower_limit", "unconstrained"), r3
    assert not r3.is_limit          # not an UPPER limit
    assert r3.pinned_fraction > 0.1
    # best is bounded (the paper engine returned ~1e284 here)
    assert r3.value.best <= 1e3


# photometry of a real faint GOODS-S source (all three bands at S/N ~ 3-4)
# whose Halpha and [O III] are each individually undetected: the per-line
# detection tests sit on their threshold, so the status used to flip between
# 'upper_limit' and 'unconstrained' with the Monte-Carlo seed alone.
_WEAK_PHOT = {"F277W": (1.642742e-3, 0.376376e-3),
              "F356W": (1.649971e-3, 0.424756e-3),
              "F444W": (1.488542e-3, 0.487806e-3)}
_WEAK_Z = 4.3624


def _weak_cfg(seed, method="posterior"):
    return FitConfig(z=_WEAK_Z,
                     continuum={"beta_mode": "fixed", "beta": -2.0},
                     dust={"av": 0.0, "av_sigma": 0.0},
                     mc={"n": 300, "seed": seed, "method": method})


def test_weak_ratio_reports_limit_not_unconstrained():
    """With neither line individually detected the ratio posterior can still
    bound R3 from above; the engine must quote that limit instead of
    discarding it, and the label must not depend on the MC seed."""
    seen = set()
    for seed in (11, 22, 33, 44):
        r3 = fit(_WEAK_PHOT, _weak_cfg(seed)).ratios[0]
        seen.add(r3.status)
        assert 0 < r3.value.percentiles.p975 < 1e3   # an informative bound
    assert seen == {"upper_limit"}, seen


def test_weak_ratio_bootstrap_stays_unconstrained():
    """The bootstrap counterpart collapses against the F >= 0 boundary, so its
    upper percentile is pinned at the ratio clip and carries no information:
    that case must still be reported as unconstrained (paper behaviour)."""
    r3 = fit(_WEAK_PHOT, _weak_cfg(20260612, method="bootstrap")).ratios[0]
    assert r3.status == "unconstrained"
    assert r3.value.percentiles.p975 >= 1e3


def test_ratio_measured_status():
    phot = synth_photometry(strong_line_ews(), snr=30.0)
    res = fit(phot, FitConfig(z=Z))
    assert res.ratios[0].status == "measured"
    assert res.ratios[0].pinned_fraction < 0.05


def test_ratio_unconstrained_when_no_coverage():
    """Ratio referencing a line outside every band -> unconstrained."""
    cfg = FitConfig(z=Z).with_line_role("HeI10830", "free")
    cfg = cfg.model_copy(update={"ratios": cfg.ratios + [
        RatioConfig(name="HeIHa", numerator="HeI10830",
                    denominator="Halpha")]})
    phot = {b: v for b, v in synth_photometry(strong_line_ews()).items()
            if b != "F444W"}
    res = fit(phot, cfg)
    hr = [r for r in res.ratios if r.name == "HeIHa"][0]
    assert hr.status == "unconstrained"
    assert any("HeI10830" in w for w in res.warnings)


def test_ew_percentiles_present():
    phot = synth_photometry(strong_line_ews(), snr=30.0)
    res = fit(phot, FitConfig(z=Z))
    ha = {l.name: l for l in res.lines}["Halpha"]
    assert ha.ew0_rest_percentiles is not None
    p = ha.ew0_rest_percentiles
    assert p.p16 < ha.ew0_rest < p.p975 or p.p025 < ha.ew0_rest < p.p975


def test_blueward_of_lya_warning():
    """F090W at z=6.1 lies entirely blueward of observed Lya (0.86 um)."""
    phot = {"F090W": (0.01, 0.005), "F356W": (0.02, 0.005),
            "F444W": (0.09, 0.005), "F410M": (0.015, 0.006)}
    res = fit(phot, FitConfig.fixed_slope(6.1, mc={"n": 50}), default_filters())
    assert any("blueward" in w for w in res.warnings), res.warnings


def test_heii4686_available():
    cfg = FitConfig(z=Z).with_line_role("HeII4686", "free")
    res = fit(synth_photometry(strong_line_ews()), cfg)
    assert "HeII4686" in {l.name for l in res.lines}


def test_dust_ratio_is_observed_ratio():
    """With dust the reported ratio is the OBSERVED (attenuated) line ratio:
    numerator and denominator both carry their own attenuation.  (The paper
    engine mixed frames; see README 'Differences from the paper engine' and
    test_parity.test_dust_r3_definitional_relation.)"""
    phot = synth_photometry(strong_line_ews(), snr=30.0)
    r0 = fit(phot, FitConfig(z=Z))
    r1 = fit(phot, FitConfig(z=Z, dust={"av": 1.0}))
    lines0 = {l.name: l for l in r0.lines}
    lines1 = {l.name: l for l in r1.lines}
    # same free amplitudes -> same observed Halpha; Hbeta drops with dust
    assert r1.ratios[0].value.best == pytest.approx(
        lines1["OIII5007"].flux.best / lines1["Hbeta"].flux.best, rel=1e-9)
    assert (lines1["Hbeta"].ratio_effective
            < lines0["Hbeta"].ratio_effective)


def test_posterior_seed_reproducible():
    phot = synth_photometry(strong_line_ews())
    a = fit(phot, FitConfig(z=Z, mc={"n": 100, "method": "posterior"}))
    b = fit(phot, FitConfig(z=Z, mc={"n": 100, "method": "posterior"}))
    assert a.ratios[0].value.percentiles == b.ratios[0].value.percentiles


def test_av_jitter_widens_tied_line_posterior():
    """dust.av_sigma propagates the attenuation uncertainty: a large sigma
    must widen the tied Hbeta flux interval relative to av_sigma=0."""
    phot = synth_photometry(strong_line_ews(), snr=50.0)
    r0 = fit(phot, FitConfig(z=Z, dust={"av": 1.0, "av_sigma": 0.0},
                             mc={"n": 200}))
    r1 = fit(phot, FitConfig(z=Z, dust={"av": 1.0, "av_sigma": 0.5},
                             mc={"n": 200}))
    w = lambda r: (lambda p: p.p84 - p.p16)(
        {l.name: l for l in r.lines}["Hbeta"].flux.percentiles)
    assert w(r1) > w(r0)
