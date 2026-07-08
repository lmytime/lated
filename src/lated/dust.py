"""Dust attenuation laws (identical to the paper pipeline's photometry/dust.py).

Attenuation enters the fit only as a *differential* on tied line ratios:
each free line's amplitude absorbs its own absolute attenuation, and a tied
line's ratio is multiplied by 10^(-0.4 (A(line) - A(root))).
"""

import numpy as np


def calzetti_alam(wave, av):
    """Calzetti et al. (2000) A_lambda for a given A_V; wave in AA (rest)."""
    um = np.clip(np.asarray(wave, dtype=float) / 1e4, 0.12, 2.2)
    k = np.where(
        um < 0.63,
        2.659 * (-2.156 + 1.509 / um - 0.198 / um ** 2 + 0.011 / um ** 3) + 4.05,
        2.659 * (-1.857 + 1.040 / um) + 4.05,
    )
    return np.clip(k, 0, None) * av / 4.05


def smclike_alam(wave, av, slope=1.2):
    """Steep 'SMC-like' power-law approximation A_lam/A_V = (5500/lam)^slope."""
    lam = np.clip(np.asarray(wave, dtype=float), 912.0, None)
    return av * (5500.0 / lam) ** slope


LAWS = {"calzetti": calzetti_alam, "smc": smclike_alam}


def attenuation_ratio(wave_rest: float, ref_wave_rest: float, av: float,
                      law: str = "calzetti") -> float:
    """Flux suppression of a line at ``wave_rest`` relative to a reference
    line at ``ref_wave_rest``: 10^(-0.4 (A(wave) - A(ref)))."""
    if av <= 0:
        return 1.0
    fn = LAWS[law]
    a = fn(np.array([wave_rest]), av)[0]
    a_ref = fn(np.array([ref_wave_rest]), av)[0]
    return float(10 ** (-0.4 * (a - a_ref)))
