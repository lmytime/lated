"""The photometry -> emission-line-flux fitting engine.

Algorithm (identical to the LATED paper engine,
``photometry/line_recovery.recover_lines_from_photometry``):

1. Convert the AB-calibrated band fluxes [uJy] to photon-weighted mean
   f_lambda per band.
2. Build one design-matrix column per *free* line (its tied children are
   folded in at their effective ratios, including the dust differential)
   and one continuum column per candidate slope beta.
3. For each beta on the grid (or the single fixed value), solve the
   error-weighted non-negative least squares problem for the amplitudes;
   keep the beta with the smallest residual norm.
4. Uncertainties, two methods (``mc.method``):
   - ``posterior`` (default): sample the truncated-Gaussian posterior of
     the amplitudes (Gaussian likelihood, flat prior on F >= 0) by Gibbs
     sampling, with the slope drawn from its profile weight over the grid
     (free) or its Gaussian prior (fixed).  Boundary-safe limits.
   - ``bootstrap`` (reproduces the legacy paper pipeline): resample the
     photometry and refit; read percentiles of the refits.  Caveat: at the
     non-negativity boundary the refits can collapse to exactly zero, so
     upper limits on absent lines can undershoot the photometric depth
     (each line's ``flux_sensitivity_1sig`` is reported, and a warning is
     issued).
   Either way one can optionally jitter z (``z_sigma``), the dust screen
   (``dust.av_sigma``, truncated at A_V >= 0), and, when the slope is
   fixed, beta (``beta_sigma``), so those systematics enter the budget.
5. Report every enabled line's flux (tied lines at their effective ratio
   times the root's draws), rest-frame EWs, the requested line ratios with
   measurement/upper-limit/lower-limit/unconstrained status, and the
   best-fit model through each band.

This is deliberately NOT an SED fit: no stellar populations, no ages —
just the minimal transparent model needed to turn band excesses into
line-flux constraints with honest errors.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from numpy.linalg import LinAlgError
from pydantic import BaseModel, ConfigDict
from scipy.optimize import nnls
from scipy.special import ndtr, ndtri

from .config import FitConfig, LineConfig
from .dust import attenuation_ratio
from .filters import FilterSet, default_filters

UJY = 1e-29  # erg/s/cm2/Hz per microJansky
PCT_LEVELS = (2.5, 16.0, 50.0, 84.0, 97.5)
RATIO_CLIP = 1e3     # bound on absurd noise tails of flux ratios
DIV_FLOOR = 1e-300   # guard for ratio denominators


def _nnls(A: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, float]:
    """Non-negative least squares, robust to a rank-deficient design.

    When two free lines respond only in the same band their columns are
    collinear and the normal equations are singular.  The legacy Fortran
    ``scipy.optimize.nnls`` tolerated this; the rewritten NNLS fails instead,
    surfacing as ``LinAlgError('Matrix is singular')`` or, on other numpy
    builds, ``ValueError('zero-size array to reduction ...')``.  On failure we
    add a negligible Tikhonov ridge (which gives the augmented system full
    column rank by construction) and report the residual on the original,
    un-regularised system so the reported chi2 is unaffected.  The ordinary
    full-rank path is untouched, so exact paper parity is preserved.
    """
    try:
        return nnls(A, b)
    except (LinAlgError, ValueError):
        n = A.shape[1]
        ridge = np.sqrt(np.finfo(float).eps) * (float(np.linalg.norm(A)) or 1.0)
        coef, _ = nnls(np.vstack([A, ridge * np.eye(n)]),
                       np.concatenate([b, np.zeros(n)]))
        return coef, float(np.linalg.norm(A @ coef - b))


class Percentiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p025: float
    p16: float
    p50: float
    p84: float
    p975: float


class ValueWithError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    best: float
    percentiles: Percentiles


class LineResult(BaseModel):
    """Fitted flux of one enabled line (units of the input photometry's
    integrated flux: erg/s/cm2 if fluxes were uJy-calibrated)."""
    model_config = ConfigDict(extra="forbid")
    name: str
    rest_wave: float
    obs_wave: float
    role: str                       # 'free' or 'tied'
    tied_to: Optional[str] = None
    root: str                       # free line this resolves to (itself if free)
    ratio_effective: float          # F_line / F_root incl. dust differential
    flux: ValueWithError
    # 1-sigma depth for this line's amplitude; None when the line has no
    # band coverage (would be infinite, which JSON cannot carry)
    flux_sensitivity_1sig: Optional[float]
    ew0_rest: Optional[float] = None  # rest-frame EW [AA]; None if continuum 0
    ew0_rest_percentiles: Optional[Percentiles] = None
    constrained: bool               # False if the line falls outside every band


class RatioResult(BaseModel):
    """A derived line ratio.

    ``status`` is decided by which side is detected (16th percentile of the
    flux draws > 0): both -> 'measured'; numerator undetected ->
    'upper_limit' (quote < p975); denominator undetected -> 'lower_limit'
    (quote > p025); neither -> 'unconstrained'.  ``pinned_fraction`` is the
    fraction of draws whose denominator hit zero, which are pinned at the
    RATIO_CLIP bound in the percentiles (paper convention) -- when it is
    large, trust the status, not the percentiles."""
    model_config = ConfigDict(extra="forbid")
    name: str
    numerator: str
    denominator: str
    value: ValueWithError
    status: str
    pinned_fraction: float
    is_limit: bool                  # numerator consistent with zero at 1 sigma


class FitResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bands: List[str]
    beta: ValueWithError
    beta_role: str                  # 'free' or 'fixed'
    continuum_flam_at_pivot: ValueWithError
    lines: List[LineResult]
    ratios: List[RatioResult]
    chi2: float
    ndof: int
    n_free_parameters: int
    band_model_uJy: Dict[str, float]   # best-fit model through each band
    warnings: List[str]
    # thinned MC draws of the free parameters (mc.keep_draws=True):
    # keys 'C', 'beta', and each free line name; aligned across keys
    posterior_draws: Optional[Dict[str, List[float]]] = None
    config: FitConfig                  # echo of the exact fit definition


class _Root:
    """A free line plus its resolved tied children."""

    def __init__(self, line: LineConfig):
        self.line = line
        # (line, effective ratio at the configured A_V, intrinsic chain)
        self.children: List[Tuple[LineConfig, float, float]] = []


def _resolve_roots(config: FitConfig, av: Optional[float] = None) -> List[_Root]:
    """Group enabled lines under their free roots, with effective intrinsic
    ratios (chained) times the dust differential relative to the root.
    ``av`` overrides config.dust.av (the Monte-Carlo A_V jitter)."""
    av_eff = config.dust.av if av is None else av
    enabled = {l.name: l for l in config.lines if l.role != "off"}
    roots = {l.name: _Root(l) for l in enabled.values() if l.role == "free"}
    for l in enabled.values():
        if l.role != "tied":
            continue
        ratio, cur = 1.0, l
        while cur.role == "tied":
            ratio *= cur.ratio
            cur = enabled[cur.tied_to]
        eff = ratio * attenuation_ratio(l.rest_wave, cur.rest_wave,
                                        av_eff, config.dust.law)
        roots[cur.name].children.append((l, eff, ratio))
    # preserve the config's ordering of free lines
    return [roots[l.name] for l in config.lines
            if l.role == "free" and l.name in roots]


def _validate_photometry(photometry, filters: FilterSet,
                         n_free_lines: int, beta_free: bool) -> List[str]:
    if not photometry:
        raise ValueError("photometry is empty")
    bands = list(photometry)
    missing = [b for b in bands if b not in filters]
    if missing:
        raise ValueError(f"unknown band(s) {missing}; available filters: "
                         f"{', '.join(sorted(filters.names()))}")
    for b in bands:
        f, e = photometry[b]
        if not (np.isfinite(f) and np.isfinite(e)):
            raise ValueError(f"band {b!r}: flux/error must be finite "
                             f"(got {f!r} +- {e!r})")
        if e <= 0:
            raise ValueError(f"band {b!r}: error must be > 0 (got {e!r})")
    n_par = 1 + n_free_lines + (1 if beta_free else 0)
    if len(bands) < n_par:
        raise ValueError(
            f"{len(bands)} band(s) cannot constrain {n_par} free parameters "
            f"(continuum amplitude{' + slope' if beta_free else ''} + "
            f"{n_free_lines} line(s)); add bands, fix the slope "
            "(continuum.beta_mode='fixed'), or switch lines off/tied")
    return bands


def fit(photometry: Mapping[str, Tuple[float, float]],
        config: FitConfig,
        filters: Optional[FilterSet] = None) -> FitResult:
    """Fit the transparent continuum + line model to band photometry.

    Parameters
    ----------
    photometry : mapping band name -> (flux_uJy, err_uJy)
        AB-calibrated band fluxes; negative fluxes are allowed (faint or
        noisy bands), errors must be positive.
    config : FitConfig
        The complete fit definition (see :mod:`lated.config`).
    filters : FilterSet, optional
        Defaults to the bundled filter curves.
    """
    filters = filters or default_filters()
    roots = _resolve_roots(config)
    beta_free = config.continuum.beta_mode == "free"
    bands = _validate_photometry(photometry, filters, len(roots), beta_free)
    filts = [filters[b] for b in bands]
    lam0 = config.continuum.pivot_wavelength
    cont = config.continuum

    y = np.array([filters[b].fnu_to_mean_flam(photometry[b][0] * UJY)
                  for b in bands])
    e = np.array([filters[b].fnu_to_mean_flam(photometry[b][1] * UJY)
                  for b in bands])

    beta_grid = (np.linspace(cont.grid_min, cont.grid_max, cont.grid_n)
                 if beta_free else np.array([cont.beta]))

    def line_columns(zz: float, roots_=None) -> List[np.ndarray]:
        cols = []
        for root in (roots_ if roots_ is not None else roots):
            lam = root.line.rest_wave * (1.0 + zz)
            col = np.array([f.line_response(lam) for f in filts])
            for child, eff, _chain in root.children:
                lam_c = child.rest_wave * (1.0 + zz)
                col = col + eff * np.array([f.line_response(lam_c)
                                            for f in filts])
            cols.append(col)
        return cols

    def cont_column(beta: float) -> np.ndarray:
        return np.array([f.continuum_response(beta, lam0) for f in filts])

    line_cols = line_columns(config.z)

    def solve(yvec: np.ndarray, cols: Sequence[np.ndarray]):
        best = None
        for beta in beta_grid:
            A = np.column_stack([cont_column(beta)] + list(cols)) / e[:, None]
            coef, rnorm = _nnls(A, yvec / e)
            if best is None or rnorm < best[0]:
                best = (rnorm, float(beta), coef)
        return best

    rnorm, beta_best, coef = solve(y, line_cols)

    beta_sigma = cont.beta_sigma_effective
    rng = np.random.default_rng(config.mc.seed)
    if config.mc.method == "posterior":
        draws, betas, av_draws = _sample_posterior(
            y, e, beta_grid, beta_best, beta_sigma, beta_free,
            line_cols, line_columns, cont_column, config, rng)
    else:
        # bootstrap: resample the photometry and refit (the RNG draw order
        # matches the paper engine, so percentiles reproduce it exactly)
        draws = np.empty((config.mc.n, 1 + len(roots)))
        betas = np.empty(config.mc.n)
        av_draws = np.full(config.mc.n, config.dust.av)
        av_sigma = config.dust.av_sigma
        for i in range(config.mc.n):
            cols_i = line_cols
            zz = config.z
            if config.z_sigma > 0:   # propagate slice-redshift uncertainty
                zz = config.z + rng.normal(0, config.z_sigma)
            roots_i = None
            if av_sigma > 0:         # propagate the dust-screen uncertainty
                av_i = max(0.0, config.dust.av + rng.normal(0, av_sigma))
                av_draws[i] = av_i
                roots_i = _resolve_roots(config, av=av_i)
            if config.z_sigma > 0 or roots_i is not None:
                cols_i = line_columns(zz, roots_i)
            if beta_sigma > 0:       # marginalise the assumed continuum slope
                b_i = beta_best + rng.normal(0, beta_sigma)
                A = np.column_stack([cont_column(b_i)] + cols_i) / e[:, None]
                cc, _ = _nnls(A, (y + rng.normal(0, e)) / e)
                bb = b_i
            elif config.mc.fast:     # slope pinned at the best fit (fast)
                A = np.column_stack([cont_column(beta_best)] + cols_i) / e[:, None]
                cc, _ = _nnls(A, (y + rng.normal(0, e)) / e)
                bb = beta_best
            else:
                _, bb, cc = solve(y + rng.normal(0, e), cols_i)
            draws[i] = cc
            betas[i] = bb

    def pct(a: np.ndarray) -> Percentiles:
        q = np.percentile(a, PCT_LEVELS)
        return Percentiles(p025=float(q[0]), p16=float(q[1]), p50=float(q[2]),
                           p84=float(q[3]), p975=float(q[4]))

    def val(best: float, a: np.ndarray) -> ValueWithError:
        return ValueWithError(best=float(best), percentiles=pct(a))

    # ---- per-line flux table (free roots from draws, tied at eff ratios) ---
    root_index = {r.line.name: 1 + j for j, r in enumerate(roots)}
    flux_draws: Dict[str, np.ndarray] = {}
    line_results: List[LineResult] = []
    warnings: List[str] = []
    for j, root in enumerate(roots):
        flux_draws[root.line.name] = draws[:, 1 + j]
        for child, eff, chain in root.children:
            if config.dust.av_sigma > 0:
                l10 = np.log10(attenuation_ratio(
                    child.rest_wave, root.line.rest_wave, 1.0,
                    config.dust.law))
                att = 10.0 ** (l10 * av_draws)
            else:
                att = eff / chain
            flux_draws[child.name] = chain * att * draws[:, 1 + j]

    def cont_flam_at(lam_obs: float) -> float:
        return coef[0] * (lam_obs / lam0) ** beta_best

    # per-draw continuum for EW percentiles
    cont_draws_c = draws[:, 0]

    # single-parameter 1-sigma depth of each root amplitude: the error of a
    # weighted-least-squares fit of that column alone
    root_sens = {}
    for j, root in enumerate(roots):
        wnorm = float(np.sum((line_cols[j] / e) ** 2))
        root_sens[root.line.name] = (1.0 / np.sqrt(wnorm) if wnorm > 0
                                     else None)

    for root in roots:
        entries = [(root.line, root.line.name, 1.0)] + \
                  [(child, root.line.name, eff)
                   for child, eff, _chain in root.children]
        for line, root_name, eff in entries:
            lam_obs = line.rest_wave * (1.0 + config.z)
            best_flux = eff * coef[root_index[root_name]]
            c_at = cont_flam_at(lam_obs)
            ew0 = float(best_flux / c_at / (1.0 + config.z)) if c_at > 0 else None
            with np.errstate(divide="ignore", invalid="ignore"):
                cont_d = cont_draws_c * (lam_obs / lam0) ** betas
                ew_d = flux_draws[line.name] / (cont_d * (1.0 + config.z))
            ok = np.isfinite(ew_d) & (cont_d > 0)
            ew_pct = pct(ew_d[ok]) if ok.mean() >= 0.5 else None
            constrained = any(f.line_response(lam_obs) > 0 for f in filts)
            if not constrained and line.role == "free":
                warnings.append(
                    f"line {line.name} at {lam_obs / 1e4:.2f} um falls outside "
                    "every fitted band; its flux is unconstrained")
            rs = root_sens[root_name]
            sens = eff * rs if rs is not None else None
            fp = pct(flux_draws[line.name])
            if (config.mc.method == "bootstrap" and constrained
                    and sens is not None
                    and fp.p16 <= 0 and fp.p975 < 0.5 * sens):
                warnings.append(
                    f"{line.name}: bootstrap upper limit ({fp.p975:.2e}) is "
                    f"tighter than the photometric depth ({sens:.2e}); this "
                    "is a non-negativity boundary artefact -- prefer "
                    "mc.method='posterior' for honest limits")
            line_results.append(LineResult(
                name=line.name, rest_wave=line.rest_wave, obs_wave=lam_obs,
                role=line.role, tied_to=line.tied_to, root=root_name,
                ratio_effective=eff,
                flux=ValueWithError(best=float(best_flux), percentiles=fp),
                flux_sensitivity_1sig=(float(sens) if sens is not None
                                       else None),
                ew0_rest=ew0, ew0_rest_percentiles=ew_pct,
                constrained=constrained))

    # ---- requested ratios with measurement/limit status --------------------
    lr_by_name = {lr.name: lr for lr in line_results}
    ratio_results: List[RatioResult] = []
    ratio_draw_store: Dict[str, np.ndarray] = {}
    for r in config.ratios:
        num, den = flux_draws[r.numerator], flux_draws[r.denominator]
        with np.errstate(divide="ignore", invalid="ignore"):
            rr = num / np.clip(den, DIV_FLOOR, None)
        ratio_draw_store[r.name] = np.clip(
            np.where(np.isfinite(rr), rr, 0.0), 0.0, RATIO_CLIP)
        rr = np.clip(rr[np.isfinite(rr)], 0.0, RATIO_CLIP)
        best_r = lr_by_name[r.numerator].flux.best / max(
            lr_by_name[r.denominator].flux.best, DIV_FLOOR)
        num_p, den_p = pct(num), pct(den)
        if config.mc.method == "posterior":
            # posterior draws never hit exactly zero: call a line detected
            # when its 16th percentile clears a quarter of its 84th (a
            # scale-free ~1.5-sigma threshold for the truncated Gaussian)
            def det(p: Percentiles) -> bool:
                return p.p16 > 0.25 * p.p84 > 0
        else:
            def det(p: Percentiles) -> bool:
                return p.p16 > 0
        num_det, den_det = det(num_p), det(den_p)
        # a tied line is constrained through its free root even when it sits
        # outside every band, so coverage is judged at the root
        num_cov = lr_by_name[lr_by_name[r.numerator].root].constrained
        den_cov = lr_by_name[lr_by_name[r.denominator].root].constrained
        if not (num_cov and den_cov):
            status = "unconstrained"
        elif num_det and den_det:
            status = "measured"
        elif den_det:
            status = "upper_limit"
        elif num_det:
            status = "lower_limit"
        else:
            # Neither line clears its own detection threshold.  The ratio's
            # posterior can still bound it from above: an undetected
            # denominator widens that bound but does not invalidate it, so we
            # quote the limit whenever it carries information, and reserve
            # 'unconstrained' for a bound that has run into the RATIO_CLIP
            # guard (e.g. bootstrap draws with a zero denominator), where the
            # upper percentile is an artefact rather than a constraint.
            # Deciding this on the ratio's own posterior rather than on two
            # knife-edge per-line tests also makes the label stable against
            # the Monte-Carlo seed: for a line sitting near the detection
            # threshold the status no longer flips between 'upper_limit' and
            # 'unconstrained' from one random stream to the next.
            informative = bool(rr.size) and float(
                np.percentile(rr, 97.5)) < 0.5 * RATIO_CLIP
            status = "upper_limit" if informative else "unconstrained"
            if informative:
                warnings.append(
                    f"ratio {r.name}: neither {r.numerator} nor "
                    f"{r.denominator} is individually detected, so the quoted "
                    "upper limit is set by the denominator's posterior and is "
                    "correspondingly weak")
        pinned = float(np.mean(den <= 0))
        if status == "measured" and pinned > 0.05:
            warnings.append(
                f"ratio {r.name}: {pinned:.0%} of draws hit a zero "
                f"denominator and are pinned at {RATIO_CLIP:g} in the "
                "percentiles; treat the upper percentiles with caution")
        # ``is_limit`` says the ratio is quoted as an UPPER limit.  Under
        # bootstrap that is the legacy "numerator consistent with zero" test,
        # which the parity suite pins; the posterior's draws are strictly
        # positive so that test can never fire there, and the status decided
        # above (which uses the posterior's own detection threshold) is the
        # meaningful statement.
        is_lim = (status == "upper_limit" if config.mc.method == "posterior"
                  else bool(num_p.p16 <= 0 or num_p.p50 <= 0))
        ratio_results.append(RatioResult(
            name=r.name, numerator=r.numerator, denominator=r.denominator,
            value=val(min(best_r, RATIO_CLIP), rr),
            status=status, pinned_fraction=pinned, is_limit=is_lim))

    # bands reaching blueward of observed Lya: IGM is not in the model
    lya_obs = 1215.67 * (1.0 + config.z)
    for b, f in zip(bands, filts):
        lo, _ = f.half_power_edges()
        if lo < lya_obs:
            warnings.append(
                f"band {b} extends blueward of observed Lya "
                f"({lya_obs / 1e4:.2f} um); IGM absorption is not modelled, "
                "so its photometry may bias the continuum")

    # ---- best-fit model through each band ----------------------------------
    A_best = np.column_stack([cont_column(beta_best)] + line_cols)
    model_mean_flam = A_best @ coef
    band_model = {b: filters[b].mean_flam_to_fnu_uJy(m)
                  for b, m in zip(bands, model_mean_flam)}

    posterior_draws = None
    if config.mc.keep_draws:
        step = max(1, config.mc.n // 1000)      # cap the payload at ~1000
        sel = slice(None, None, step)
        posterior_draws = {"C": [float(v) for v in draws[sel, 0]],
                           "beta": [float(v) for v in betas[sel]],
                           "A_V": [float(v) for v in av_draws[sel]]}
        for j, root in enumerate(roots):
            posterior_draws[root.line.name] = [float(v)
                                               for v in draws[sel, 1 + j]]
        for rname, arr in ratio_draw_store.items():
            if rname not in posterior_draws:   # avoid name collisions
                posterior_draws[rname] = [float(v) for v in arr[sel]]

    n_free = 1 + len(roots) + (1 if beta_free else 0)
    return FitResult(
        bands=bands,
        beta=val(beta_best, betas),
        beta_role="free" if beta_free else "fixed",
        continuum_flam_at_pivot=val(coef[0], draws[:, 0]),
        lines=line_results,
        ratios=ratio_results,
        chi2=float(rnorm ** 2),
        ndof=int(len(bands) - n_free),
        n_free_parameters=n_free,
        band_model_uJy=band_model,
        warnings=warnings,
        posterior_draws=posterior_draws,
        config=config)


def _sample_posterior(y, e, beta_grid, beta_best, beta_sigma, beta_free,
                      line_cols, line_columns, cont_column, config, rng):
    """Sample the truncated-Gaussian posterior of the amplitudes.

    For each draw: pick the slope (profile-weighted over the grid when free,
    Gaussian prior around the fixed value otherwise), optionally jitter z,
    then Gibbs-sample the amplitude vector from N(theta_LS, (A^T A)^-1)
    truncated to theta >= 0 (flat non-negative prior).  The chain is
    initialised at the NNLS solution and burned in per draw; amplitudes with
    an empty design column (unconstrained lines) are held at zero."""
    n_par = 1 + len(line_cols)
    n_burn = 30
    yw = y / e

    if beta_free and len(beta_grid) > 1:
        # profile weights: w(beta) ~ exp(-chi2_min(beta)/2)
        r2 = np.empty(len(beta_grid))
        for k, b in enumerate(beta_grid):
            A = np.column_stack([cont_column(b)] + list(line_cols)) / e[:, None]
            _, rn = _nnls(A, yw)
            r2[k] = rn ** 2
        w = np.exp(-0.5 * (r2 - r2.min()))
        w /= w.sum()
    else:
        w = None

    draws = np.empty((config.mc.n, n_par))
    betas = np.empty(config.mc.n)
    av_draws = np.full(config.mc.n, config.dust.av)
    av_sigma = config.dust.av_sigma
    for i in range(config.mc.n):
        cols_i = line_cols
        zz = config.z
        if config.z_sigma > 0:
            zz = config.z + rng.normal(0, config.z_sigma)
        roots_i = None
        if av_sigma > 0:
            av_i = max(0.0, config.dust.av + rng.normal(0, av_sigma))
            av_draws[i] = av_i
            roots_i = _resolve_roots(config, av=av_i)
        if config.z_sigma > 0 or roots_i is not None:
            cols_i = line_columns(zz, roots_i)
        if w is not None:
            b_i = float(beta_grid[rng.choice(len(beta_grid), p=w)])
        elif beta_sigma > 0:
            b_i = beta_best + rng.normal(0, beta_sigma)
        else:
            b_i = beta_best
        A = np.column_stack([cont_column(b_i)] + list(cols_i)) / e[:, None]
        theta0, _ = _nnls(A, yw)          # feasible chain start
        lam = A.T @ A                    # precision matrix
        bvec = A.T @ yw
        usable = np.diag(lam) > 0
        theta = theta0.copy()
        theta[~usable] = 0.0
        for _ in range(n_burn):
            for j in range(n_par):
                if not usable[j]:
                    continue
                sig = 1.0 / np.sqrt(lam[j, j])
                mu = (bvec[j] - lam[j] @ theta + lam[j, j] * theta[j]) / lam[j, j]
                lo_cdf = ndtr(-mu / sig)
                if lo_cdf >= 1.0 - 1e-14:   # mass entirely at the boundary
                    theta[j] = 0.0
                    continue
                u = rng.uniform(lo_cdf, 1.0)
                theta[j] = mu + sig * ndtri(min(u, 1.0 - 1e-16))
        draws[i] = theta
        betas[i] = b_i
    return draws, betas, av_draws


def model_spectrum(result: FitResult, wave_obs: Optional[np.ndarray] = None,
                   filters: Optional[FilterSet] = None,
                   display_fwhm_kms: float = 150.0 * 2.3548):
    """Best-fit spectrum as f_nu [uJy] on an observed wavelength grid, for
    plotting: the fitted continuum plus every enabled line at its fitted flux,
    drawn as Gaussians of ``display_fwhm_kms`` (display width only -- the fit
    itself treats lines as delta functions).

    Returns (wave_obs [AA], total_fnu_uJy, continuum_fnu_uJy)."""
    from .filters import C_AA
    cfg = result.config
    if wave_obs is None:
        filters = filters or default_filters()
        piv = np.array([filters[b].pivot for b in result.bands])
        wave_obs = np.linspace(piv.min() * 0.72, piv.max() * 1.22, 9000)
    lam0 = cfg.continuum.pivot_wavelength
    flam_cont = (result.continuum_flam_at_pivot.best
                 * (wave_obs / lam0) ** result.beta.best)
    flam = flam_cont.copy()
    sig_v = display_fwhm_kms / 2.3548 / 2.99792458e5
    for lr in result.lines:
        sig = lr.obs_wave * sig_v
        flam = flam + lr.flux.best / (sig * np.sqrt(2 * np.pi)) * np.exp(
            -0.5 * ((wave_obs - lr.obs_wave) / sig) ** 2)
    to_uJy = wave_obs ** 2 / C_AA / UJY
    return wave_obs, flam * to_uJy, flam_cont * to_uJy
