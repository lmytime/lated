"""API tests (FastAPI TestClient)."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from lated.server.app import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    m = r.json()
    assert any(p["id"] == "Wz3.1" for p in m["presets"])
    names = [f["name"] for f in m["filters"]]
    assert "F277W" in names
    assert "RomanF158" in names
    # the full NIRCam + MIRI imaging sets are offered
    for f in ("F070W", "F150W2", "F212N", "F770W", "F1000W", "F2550W"):
        assert f in names, f
    # the web UI offers space-telescope bands only
    groups = {f["group"] for f in m["filters"]}
    assert groups == {"JWST NIRCam", "JWST MIRI", "Roman WFI"}
    balmer = m["balmer"]
    assert balmer["cases"] == ["A", "B"]
    assert "2500" in balmer["ratios"]["A"]
    assert balmer["ratios"]["B"]["10000"]["100"]["Hbeta"] == \
        pytest.approx(1 / 2.86)
    assert balmer["ratios"]["A"]["10000"]["100"]["Hbeta"] == \
        pytest.approx(1 / 2.86)
    assert balmer["ratios"]["B"]["5000"]["1000000"]["Hbeta"] == \
        pytest.approx(1 / 2.918)
    ln = {l["name"]: l for l in m["default_lines"]}
    assert ln["Halpha"]["role"] == "free"
    assert ln["Hbeta"]["role"] == "tied"
    assert ln["Hbeta"]["tied_to"] == "Halpha"
    assert ln["OII3727"]["role"] == "off"


def test_filter_curve(client):
    r = client.get("/api/filters/F277W")
    assert r.status_code == 200
    c = r.json()
    assert len(c["wave_aa"]) == len(c["trans"]) > 10
    assert client.get("/api/filters/NOPE").status_code == 404


def test_fit_three_band(client):
    body = {
        "photometry": {"F200W": [0.0136, 0.0019], "F277W": [0.0249, 0.0016],
                       "F356W": [0.0040, 0.0014]},
        "config": {"z": 3.05,
                   "continuum": {"beta_mode": "fixed", "beta": -2.0},
                   "mc": {"n": 100}},
    }
    r = client.post("/api/fit", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["beta"]["best"] == -2.0
    assert out["posterior_draws"] is None  # not requested
    lines = {l["name"]: l for l in out["lines"]}
    assert lines["Halpha"]["flux"]["best"] >= 0
    assert out["ratios"][0]["name"] == "R3"
    assert len(out["model_curve"]["wave_aa"]) > 100
    assert set(out["band_model_uJy"]) == {"F200W", "F277W", "F356W"}


def test_fit_validation_errors_are_actionable(client):
    body = {
        "photometry": {"F277W": [1.0, 0.1], "F356W": [1.0, 0.1],
                       "F444W": [1.0, 0.1]},
        "config": {"z": 3.05},
    }
    r = client.post("/api/fit", json=body)
    assert r.status_code == 422
    assert "cannot constrain" in r.json()["detail"]

    bad = {"photometry": {"F277W": [1.0, 0.1]},
           "config": {"z": 3.05, "continuum": {"beta_fix": -2}}}
    r = client.post("/api/fit", json=bad)
    assert r.status_code == 422


def test_fit_with_uncovered_line_is_json_clean(client):
    """A free line outside every band gives an infinite formal depth; the
    response must carry null, not crash JSON serialisation with a 500."""
    body = {
        "photometry": {"F115W": [0.04, 0.01], "F150W": [0.05, 0.01],
                       "F200W": [0.05, 0.01], "F277W": [0.50, 0.01],
                       "F356W": [0.07, 0.01]},
        "config": {"z": 3.05, "mc": {"n": 50}, "ratios": [],
                   "lines": [
                       {"name": "Halpha", "rest_wave": 6562.8, "role": "free"},
                       {"name": "OIII5007", "rest_wave": 5006.84,
                        "role": "free"},
                       {"name": "HeI10830", "rest_wave": 10830.34,
                        "role": "free"}]},
    }
    r = client.post("/api/fit", json=body)
    assert r.status_code == 200, r.text
    hei = [l for l in r.json()["lines"] if l["name"] == "HeI10830"][0]
    assert hei["flux_sensitivity_1sig"] is None
    assert not hei["constrained"]


def test_fit_returns_draws_when_requested(client):
    body = {
        "photometry": {"F200W": [0.0136, 0.0019], "F277W": [0.0249, 0.0016],
                       "F356W": [0.0040, 0.0014]},
        "config": {"z": 3.05,
                   "continuum": {"beta_mode": "fixed", "beta": -2.0},
                   "mc": {"n": 100, "keep_draws": True}},
    }
    r = client.post("/api/fit", json=body)
    assert r.status_code == 200, r.text
    d = r.json()["posterior_draws"]
    assert set(d) == {"C", "beta", "A_V", "Halpha", "OIII5007", "R3"}
    assert len(d["C"]) == 100


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
