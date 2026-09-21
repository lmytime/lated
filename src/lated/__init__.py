"""lated: photometric emission-line recovery.

Fit a transparent continuum + emission-line model through real filter
transmission curves to recover line fluxes, rest EWs and line ratios
(with upper limits) from broad/medium-band photometry.

>>> from lated import FitConfig, fit
>>> cfg = FitConfig.fixed_slope(z=3.05)         # slope assumed, not fitted
>>> res = fit({"F200W": (0.0136, 0.0019),
...            "F277W": (0.0249, 0.0016),
...            "F356W": (0.0040, 0.0014)}, cfg)
>>> res.ratios[0].name, res.ratios[0].is_limit
('R3', ...)
"""

from .config import (ContinuumConfig, DustConfig, FitConfig, LineConfig,
                     MCConfig, RatioConfig, default_lines)
from .engine import FitResult, LineResult, RatioResult, fit, model_spectrum
from .filters import Filter, FilterSet, default_filters, filter_group
from .lines import (BALMER_CASES, BALMER_TABLE, CASE_A_TEMPERATURES,
                    CASE_B_DENSITIES, CASE_B_TEMPERATURES, LINE_WAVELENGTHS,
                    balmer_ratios, case_b_ratios)
from .presets import WINDOW_PRESETS, WindowPreset

__version__ = "0.3.0"

__all__ = [
    "ContinuumConfig", "DustConfig", "FitConfig", "LineConfig", "MCConfig",
    "RatioConfig", "default_lines", "FitResult", "LineResult", "RatioResult",
    "fit", "model_spectrum", "Filter", "FilterSet", "default_filters",
    "filter_group", "LINE_WAVELENGTHS", "WINDOW_PRESETS", "WindowPreset",
    "BALMER_CASES", "BALMER_TABLE", "CASE_A_TEMPERATURES",
    "CASE_B_DENSITIES", "CASE_B_TEMPERATURES", "balmer_ratios",
    "case_b_ratios", "__version__",
]
