"""FastAPI application: REST API + the static single-page frontend.

Endpoints
---------
GET  /api/meta                 version, presets, filter inventory, default
                               line registry / continuum / dust / MC / ratios
GET  /api/filters/{name}       downsampled transmission curve for plotting
POST /api/fit                  run one fit; returns the full FitResult plus a
                               ready-to-plot model spectrum
GET  /                         the web app (static files)
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..config import (ContinuumConfig, DustConfig, FitConfig, MCConfig,
                      RatioConfig, default_lines)
from ..engine import fit, model_spectrum
from ..filters import default_filters, filter_group
from ..presets import WINDOW_PRESETS

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_CURVE_POINTS = 400
MODEL_CURVE_POINTS = 3000
# The web UI offers space-telescope bands only; the engine itself accepts
# every bundled filter (use the Python API for ground-based photometry).
UI_FILTER_GROUPS = ("JWST NIRCam", "JWST MIRI", "Roman WFI")


class FitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    photometry: Dict[str, Tuple[float, float]] = Field(
        ..., description="band name -> (flux_uJy, err_uJy)")
    config: FitConfig


def _downsample(x: np.ndarray, y: np.ndarray, n: int):
    if len(x) <= n:
        return x, y
    idx = np.linspace(0, len(x) - 1, n).astype(int)
    return x[idx], y[idx]


def create_app() -> FastAPI:
    # No CORS middleware: the frontend is served same-origin by this app,
    # and an open localhost API would let any web page drive the fitter.
    app = FastAPI(title="LATED line recovery", version=__version__)
    filters = default_filters()

    @app.get("/api/meta")
    def meta():
        inventory = []
        for name in filters.names():
            group = filter_group(name)
            if group not in UI_FILTER_GROUPS:
                continue
            f = filters[name]
            lo, hi = f.half_power_edges()
            inventory.append({
                "name": name,
                "group": group,
                "pivot_aa": round(f.pivot, 1),
                "half_power_aa": [round(lo, 1), round(hi, 1)],
            })
        inventory.sort(key=lambda d: d["pivot_aa"])
        from ..lines import (CASE_A_TEMPERATURES, CASE_B_DENSITIES,
                             CASE_B_TEMPERATURES, balmer_ratios)
        return {
            "version": __version__,
            "presets": [p.model_dump() for p in WINDOW_PRESETS.values()],
            "filters": inventory,
            "default_lines": [l.model_dump() for l in default_lines()],
            "default_continuum": ContinuumConfig().model_dump(),
            "default_dust": DustConfig().model_dump(),
            "default_mc": MCConfig().model_dump(),
            "default_ratios": [RatioConfig().model_dump()],
            "balmer": {
                "cases": ["A", "B"],
                "temperatures_K": {"A": list(CASE_A_TEMPERATURES),
                                   "B": list(CASE_B_TEMPERATURES)},
                "densities_cm3": list(CASE_B_DENSITIES),
                # ratios[case][te][ne]; Case A is low-density limit only
                # (same row under every density key)
                "ratios": {
                    "A": {str(int(te)): {str(int(ne)): balmer_ratios("A", te)
                                         for ne in CASE_B_DENSITIES}
                          for te in CASE_A_TEMPERATURES},
                    "B": {str(int(te)): {str(int(ne)):
                                         balmer_ratios("B", te, ne)
                                         for ne in CASE_B_DENSITIES}
                          for te in CASE_B_TEMPERATURES},
                },
            },
        }

    @app.get("/api/filters/{name}")
    def filter_curve(name: str):
        if name not in filters:
            raise HTTPException(404, f"unknown band {name!r}")
        f = filters[name]
        w, t = _downsample(f.wave, f.trans / f.trans.max(), MAX_CURVE_POINTS)
        return {"name": name, "pivot_aa": f.pivot,
                "wave_aa": [round(float(v), 1) for v in w],
                "trans": [round(float(v), 5) for v in t]}

    @app.post("/api/fit")
    def run_fit(req: FitRequest):
        try:
            result = fit(req.photometry, req.config, filters)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        lam, total, cont = model_spectrum(result, filters=filters)
        lam_d, total_d = _downsample(lam, total, MODEL_CURVE_POINTS)
        _, cont_d = _downsample(lam, cont, MODEL_CURVE_POINTS)
        out = result.model_dump()
        out["model_curve"] = {
            "wave_aa": [float(v) for v in lam_d],
            "total_uJy": [float(v) for v in total_d],
            "continuum_uJy": [float(v) for v in cont_d],
        }
        return out

    @app.get("/", include_in_schema=False)
    def index():
        # never cache the shell: it pins the ?v= of every asset, and a
        # stale shell silently loads outdated CSS/JS
        return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                            headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
