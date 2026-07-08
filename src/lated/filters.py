"""Filter transmission curves and band integration.

Filter curves are bundled with the package as two-column ASCII
(wavelength [AA], transmission), originally from the SVO Filter Profile
Service (see the LATED repository's ``tools/download_data.py``).
Synthetic photometry uses photon-weighted mean flux densities and the
pivot-wavelength AB conversion (Tokunaga & Vacca 2005 conventions).

The numerical conventions match the LATED paper pipeline
(``photometry/filters.py`` and ``photometry/line_recovery.py``) exactly,
so fits from this package agree with the published results by construction.
"""

from __future__ import annotations

import os
import re
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np

# numpy >= 2 renames trapz; keep one alias for both.
_trapz = getattr(np, "trapezoid", np.trapz)

C_AA = 2.99792458e18  # speed of light [AA/s]

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "filters")


class Filter:
    """One transmission curve, trimmed to its non-zero support."""

    def __init__(self, name: str, wave, trans):
        trans = np.asarray(trans, dtype=float)
        wave = np.asarray(wave, dtype=float)
        good = trans > 0
        if not np.any(good):
            raise ValueError(f"filter {name!r} has no positive transmission")
        i0, i1 = np.argmax(good), len(good) - np.argmax(good[::-1])
        self.name = name
        self.wave = wave[max(i0 - 1, 0):i1 + 1]
        self.trans = np.clip(trans[max(i0 - 1, 0):i1 + 1], 0, None)
        # Fine integration grid (<= ~5 AA) for synthetic magnitudes of sampled
        # SEDs; coarse native grids (e.g. Roman ~70 AA) alias narrow lines.
        n = max(len(self.wave), int((self.wave[-1] - self.wave[0]) / 5.0) + 1)
        self._iw = np.linspace(self.wave[0], self.wave[-1], n)
        self._it = np.interp(self._iw, self.wave, self.trans)
        self._iden = _trapz(self._it * self._iw, self._iw)
        self._pivot = float(np.sqrt(
            self._iden / _trapz(self._it / self._iw, self._iw)))
        # Native-grid photon denominator, used for the delta-function line
        # response (T(lam) is piecewise linear, so this convention matches the
        # paper engine exactly; the difference from the fine grid is < 1e-4).
        self._den_native = _trapz(self.trans * self.wave, self.wave)
        self._cont_cache: Dict[Tuple[float, float], float] = {}

    @property
    def pivot(self) -> float:
        """Pivot wavelength [AA]."""
        return self._pivot

    def half_power_edges(self) -> Tuple[float, float]:
        """Wavelengths [AA] where transmission first/last reaches 50% of peak."""
        half = 0.5 * self.trans.max()
        above = np.where(self.trans >= half)[0]
        lo, hi = above[0], above[-1]

        def interp(i, j):
            if self.trans[j] == self.trans[i]:
                return self.wave[i]
            f = (half - self.trans[i]) / (self.trans[j] - self.trans[i])
            return self.wave[i] + f * (self.wave[j] - self.wave[i])

        w_lo = interp(lo - 1, lo) if lo > 0 else self.wave[lo]
        w_hi = interp(hi + 1, hi) if hi < len(self.wave) - 1 else self.wave[hi]
        return float(w_lo), float(w_hi)

    def mean_flam(self, wave, flam) -> float:
        """Photon-weighted mean f_lambda of a sampled SED through the filter
        (fine-grid integration so narrow lines are not aliased)."""
        fl = np.interp(self._iw, wave, flam, left=0.0, right=0.0)
        return float(_trapz(fl * self._it * self._iw, self._iw) / self._iden)

    def ab_mag(self, wave, flam) -> float:
        """Synthetic AB magnitude of (wave [AA], flam [erg/s/cm2/AA])."""
        mean = self.mean_flam(wave, flam)
        if mean <= 0:
            return float(np.inf)
        fnu = mean * self._pivot ** 2 / C_AA
        return float(-2.5 * np.log10(fnu) - 48.60)

    def line_response(self, wave_obs: float) -> float:
        """Contribution of a unit delta-function line at ``wave_obs`` to the
        band's photon-weighted mean f_lambda: T(lam) lam / int(T lam dlam).
        Zero outside the curve's support."""
        t = np.interp(wave_obs, self.wave, self.trans, left=0.0, right=0.0)
        return float(t * wave_obs / self._den_native)

    def continuum_response(self, beta: float, lam0: float) -> float:
        """Photon-weighted mean f_lambda of a unit power-law continuum
        f_lambda = (lam/lam0)^beta through the band (cached per slope)."""
        key = (float(beta), float(lam0))
        if key not in self._cont_cache:
            if len(self._cont_cache) > 20000:   # bound long-server growth
                self._cont_cache.clear()
            num = _trapz((self.wave / lam0) ** beta * self.trans * self.wave,
                         self.wave)
            self._cont_cache[key] = float(num / self._den_native)
        return self._cont_cache[key]

    def fnu_to_mean_flam(self, fnu: float) -> float:
        """AB-calibrated f_nu [erg/s/cm2/Hz] -> the photon-weighted mean
        f_lambda the model predicts for this band."""
        return fnu * C_AA / self._pivot ** 2

    def mean_flam_to_fnu_uJy(self, mean_flam: float) -> float:
        """Inverse of :meth:`fnu_to_mean_flam`, expressed in microJansky."""
        return mean_flam * self._pivot ** 2 / C_AA / 1e-29


# Instrument grouping for the bundled curves.  MIRI filters carry a pivot
# >= 5 um (F560W and the 4-digit names), NIRCam sits below it; Roman WFI is
# the RomanF* family.  Any curve not matched here (e.g. a user-supplied
# ground-based filter via LATED_FILTERS_DIR) falls into "other".
_GROUP_PATTERNS = [
    (r"^F\d{3,4}(W2?|M|N)$", "_JWST_"),
    (r"^Roman", "Roman WFI"),
]


def filter_group(name: str) -> str:
    """Coarse instrument grouping used by the web UI's band picker."""
    for pat, group in _GROUP_PATTERNS:
        if re.match(pat, name):
            if group == "_JWST_":
                num = int(re.match(r"^F(\d+)", name).group(1))
                return "JWST MIRI" if num >= 560 else "JWST NIRCam"
            return group
    return "other"


class FilterSet:
    """Dict-like collection of :class:`Filter`, loaded from a directory of
    ``<name>.dat`` two-column ASCII curves (default: the bundled data)."""

    def __init__(self, filters: Dict[str, Filter]):
        self._filters = dict(filters)

    @classmethod
    def load(cls, data_dir: Optional[str] = None) -> "FilterSet":
        data_dir = data_dir or os.environ.get("LATED_FILTERS_DIR",
                                              DEFAULT_DATA_DIR)
        filters = {}
        for fn in sorted(os.listdir(data_dir)):
            if fn.endswith(".dat"):
                arr = np.loadtxt(os.path.join(data_dir, fn))
                filters[fn[:-4]] = Filter(fn[:-4], arr[:, 0], arr[:, 1])
        if not filters:
            raise FileNotFoundError(f"no .dat filter curves in {data_dir}")
        return cls(filters)

    def __getitem__(self, name: str) -> Filter:
        try:
            return self._filters[name]
        except KeyError:
            raise KeyError(
                f"unknown band {name!r}; available: "
                f"{', '.join(sorted(self._filters))}") from None

    def __contains__(self, name: str) -> bool:
        return name in self._filters

    def __iter__(self) -> Iterator[str]:
        return iter(self._filters)

    def __len__(self) -> int:
        return len(self._filters)

    def names(self) -> List[str]:
        return list(self._filters)

    def add(self, filt: Filter) -> None:
        """Register a custom filter (e.g. user-uploaded curve)."""
        self._filters[filt.name] = filt


_default_set: Optional[FilterSet] = None


def default_filters() -> FilterSet:
    """The bundled filter set, loaded once per process."""
    global _default_set
    if _default_set is None:
        _default_set = FilterSet.load()
    return _default_set
