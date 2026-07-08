"""Tests for the Case B (T_e, n_e) tie-ratio control and posterior draws."""

import pytest

from lated import FitConfig, balmer_ratios, case_b_ratios, fit

from test_engine import Z, strong_line_ews, synth_photometry


def test_case_b_default_row_matches_paper():
    """(1e4 K, 1e2 cm^-3) must reproduce the paper's tie ratios exactly."""
    cfg0 = FitConfig(z=Z)
    cfg1 = cfg0.with_case_b(10000.0, 100.0)
    assert [l.model_dump() for l in cfg1.lines] == \
           [l.model_dump() for l in cfg0.lines]
    r = case_b_ratios(10000.0, 100.0)
    assert r["Hbeta"] == pytest.approx(1 / 2.86)
    assert r["Hgamma"] == 0.468


def test_case_b_temperature_changes_ties():
    cfg = FitConfig(z=Z).with_case_b(20000.0, 100.0)
    lines = {l.name: l for l in cfg.lines}
    assert lines["Hbeta"].ratio == pytest.approx(1 / 2.747)  # OF06 p.78
    assert lines["Hgamma"].ratio == 0.475
    assert lines["H10"].ratio == 0.0540
    # non-Balmer ties untouched
    assert lines["OIII4959"].ratio == pytest.approx(1 / 2.98)


def test_case_b_leaves_custom_ties_alone():
    """A user-retied Hbeta (different parent or a free role) is not
    overwritten by the temperature control."""
    cfg = FitConfig(z=Z).with_line_role("Hbeta", "free")
    cfg2 = cfg.with_case_b(20000.0, 100.0)
    lines = {l.name: l for l in cfg2.lines}
    assert lines["Hbeta"].role == "free"
    # higher orders still tied to Hbeta -> updated
    assert lines["Hgamma"].ratio == 0.475


def test_case_b_invalid_values_rejected():
    with pytest.raises(ValueError, match="T_e"):
        case_b_ratios(12345.0, 100.0)
    with pytest.raises(ValueError, match="n_e"):
        case_b_ratios(10000.0, 7.0)
    with pytest.raises(ValueError, match="case"):
        balmer_ratios("C", 10000.0, 100.0)


def test_case_a_ratios():
    """Case A values from Osterbrock & Ferland (2006), low-density limit."""
    r = balmer_ratios("A", 10000.0)
    assert r["Hbeta"] == pytest.approx(1 / 2.86)
    assert r["Hgamma"] == 0.470      # differs from Case B's 0.468
    assert r["H10"] == 0.0544
    r25 = balmer_ratios("A", 2500.0)  # Case A reaches down to 2500 K
    assert r25["Hbeta"] == pytest.approx(1 / 3.42)
    with pytest.raises(ValueError, match="T_e"):
        balmer_ratios("B", 2500.0)    # ... but Case B does not


def test_case_b_high_density():
    """OF06 tabulates Case B up to n_e = 1e6 cm^-3; high-n lines respond."""
    lo = balmer_ratios("B", 10000.0, 100.0)
    hi = balmer_ratios("B", 10000.0, 1000000.0)
    assert hi["Hbeta"] == pytest.approx(1 / 2.806)
    assert hi["H10"] > lo["H10"]      # collisional boost of high-n lines


def test_with_balmer_case_a():
    cfg = FitConfig(z=Z).with_balmer("A", 20000.0)
    lines = {l.name: l for l in cfg.lines}
    assert lines["Hbeta"].ratio == pytest.approx(1 / 2.69)
    assert lines["Hgamma"].ratio == 0.485


def test_case_b_affects_fit():
    phot = synth_photometry(strong_line_ews())
    r0 = fit(phot, FitConfig(z=Z))
    r1 = fit(phot, FitConfig(z=Z).with_case_b(20000.0, 100.0))
    hb0 = {l.name: l for l in r0.lines}["Hbeta"]
    hb1 = {l.name: l for l in r1.lines}["Hbeta"]
    assert hb1.ratio_effective == pytest.approx(1 / 2.747)
    assert hb1.ratio_effective > hb0.ratio_effective


def test_posterior_draws_absent_by_default():
    res = fit(synth_photometry(strong_line_ews()),
              FitConfig(z=Z, mc={"n": 100}))
    assert res.posterior_draws is None


def test_posterior_draws_returned_and_aligned():
    res = fit(synth_photometry(strong_line_ews()),
              FitConfig(z=Z, mc={"n": 200, "keep_draws": True}))
    d = res.posterior_draws
    assert set(d) == {"C", "beta", "A_V", "Halpha", "OIII5007", "R3"}
    n = len(d["C"])
    assert n == 200
    assert all(len(v) == n for v in d.values())
    # aligned: percentile of the kept draws matches the reported percentiles
    import numpy as np
    ha = {l.name: l for l in res.lines}["Halpha"]
    assert np.percentile(d["Halpha"], 50) == pytest.approx(
        ha.flux.percentiles.p50, rel=1e-9)


def test_posterior_draws_thinned():
    res = fit(synth_photometry(strong_line_ews()),
              FitConfig(z=Z, mc={"n": 3000, "keep_draws": True, "fast": True}))
    assert len(res.posterior_draws["C"]) <= 1500
