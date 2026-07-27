# LATED

**Measure emission lines you can't spectroscopically resolve, straight from photometry.**

[![PyPI version](https://img.shields.io/pypi/v/lated.svg)](https://pypi.org/project/lated/)
[![Python versions](https://img.shields.io/pypi/pyversions/lated.svg)](https://pypi.org/project/lated/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/lmytime/lated/actions/workflows/ci.yml/badge.svg)](https://github.com/lmytime/lated/actions/workflows/ci.yml)

You have JWST (or Roman) photometry of a galaxy, and one of the bands looks
too bright: an emission line is boosting it. `lated` turns that excess into a
number. It fits a simple continuum + emission-line model *through the real
filter curves* and reports the line fluxes, rest-frame equivalent widths and
line ratios (for example `[O III] 5007 / Hβ`) that the photometry implies.

When a line is genuinely there, you get a measurement with uncertainties.
When it isn't, you get an **honest upper limit**, not a fabricated value. That
distinction is the whole point of the tool.

Use it two ways: a point-and-click **web app** (no coding), or a small
**Python API** for scripting and batch work.

![The lated web workbench](https://raw.githubusercontent.com/lmytime/lated/main/docs/webapp.png)

## Install

```bash
pip install lated
```

That is everything: the Python library, the command line, and the web app.
Python 3.9+ (depends only on NumPy, SciPy, pydantic and FastAPI).

## The web app

```bash
lated serve            # open http://127.0.0.1:8321
```

Pick a redshift, tick the bands you have, paste your fluxes, and press run.
You get a verdict card (measurement or limit), an SED figure and a corner
plot, all exportable to PDF. Start from one of the built-in literature
examples to see the whole workflow in a single click. Everything on the board
is editable: the line list, which lines are free / tied / off, the nebular
conditions that set the Balmer ratios (Osterbrock & Ferland 2006 Case A/B by
temperature and density), the continuum slope, dust, and the error budget.

## From Python

```python
from lated import FitConfig, fit

photometry = {"F200W": (0.0136, 0.0019),   # {band: (flux, error)} in microJansky
              "F277W": (0.0249, 0.0016),
              "F356W": (0.0040, 0.0014)}

res = fit(photometry, FitConfig.fixed_slope(z=3.193))
print(res.ratios[0].status)                # 'upper_limit', 'measured', ...
```

That is the whole idea. The [example notebook](examples/quickstart.ipynb)
walks through reading the results, plotting the SED and corner, editing line
roles, choosing nebular conditions, and the posterior error budget.

## What you get back

Every line ratio carries a **status**, so a number is never mistaken for a
measurement it isn't:

| status | meaning | quote |
|---|---|---|
| `measured` | both lines detected | the value with 16/50/84 percentiles |
| `upper_limit` | numerator consistent with zero | `< p97.5` (2σ) |
| `lower_limit` | denominator consistent with zero | `> p2.5` |
| `unconstrained` | no band covers the line | nothing usable |

Each line also reports the faintest flux your photometry could have detected,
so every non-detection comes with its depth.

## How it works

Per band, the predicted flux is the photon-weighted mean of

```
f_λ(λ) = C (λ/λ0)^β  +  Σ_l  F_l · δ(λ − λ_l (1+z))
```

integrated through the real transmission curve and compared to your photometry
with a Gaussian likelihood; amplitudes are solved by error-weighted
non-negative least squares over a grid of slopes. Every parameter has an
explicit role (free, fixed, or tied) that you can change, and invalid setups
(unknown bands, tie cycles, non-positive errors, under-constrained fits) are
raised as errors rather than silently ignored.

## Command line

```bash
lated serve                 # run the web app
lated fit input.json        # fit from a JSON file
lated bands                 # list the bundled filter curves
lated lines                 # show the default line registry
```

The web app also exposes a small REST API (`/api/meta`,
`/api/filters/{name}`, `/api/fit`) with interactive docs at `/docs`.

## Citing

If `lated` contributes to your research, please cite Li et al. (2026, LATED
Paper I).

## Development

```bash
git clone https://github.com/lmytime/lated
cd lated
pip install -e ".[test]"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/ -q
```

Issues and contributions are welcome at
[github.com/lmytime/lated](https://github.com/lmytime/lated).
Released under the [MIT License](LICENSE).
