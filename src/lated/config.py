"""Fit configuration: every model parameter with an explicit role.

The spectral model is

    f_lambda(lam) = C (lam/lam0)^beta + sum_l F_l delta(lam - lam_l (1+z))

and every parameter is declared here as *free*, *fixed* or *tied*:

===============================  =========================================
parameter                        role
===============================  =========================================
C   (continuum amplitude)        always free (>= 0)
beta (continuum slope)           free (grid-searched) or fixed (with an
                                 optional Gaussian sigma folded into the
                                 Monte-Carlo error budget)
z                                always fixed (the Lya-slice redshift);
                                 z_sigma > 0 propagates its uncertainty
A_V, dust law                    fixed; enters only as a differential on
                                 tied line ratios
F_l (one per line)               free (>= 0), tied (ratio x another line),
                                 or off (excluded from the model)
===============================  =========================================

Unknown keys are rejected (``extra='forbid'``), so a misspelled option is an
error instead of a silent no-op.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .lines import (DEFAULT_REGISTRY, LINE_WAVELENGTHS, balmer_ratios,
                    contaminant_ties)


class ContinuumConfig(BaseModel):
    """The power-law continuum C (lam/lam0)^beta.

    The amplitude C is always free (non-negative).  The slope beta is either
    ``free`` (grid-searched over [grid_min, grid_max]) or ``fixed`` at
    ``beta`` — required when only the three selection bands are given, where
    the slope is degenerate with the amplitudes.  When fixed, ``beta_sigma``
    (default 0.3) marginalises the assumed slope in the Monte-Carlo so the
    systematic enters the error budget."""
    model_config = ConfigDict(extra="forbid")

    beta_mode: Literal["free", "fixed"] = "free"
    beta: float = -2.0
    beta_sigma: Optional[float] = Field(
        None, ge=0, description="None -> 0.3 if fixed, 0.0 if free")
    grid_min: float = -3.5
    grid_max: float = 1.0
    grid_n: int = Field(61, ge=2, le=1001)
    pivot_wavelength: float = Field(20000.0, gt=0,
                                    description="lam0 [AA, observed]")

    @property
    def beta_sigma_effective(self) -> float:
        if self.beta_sigma is not None:
            return self.beta_sigma
        return 0.3 if self.beta_mode == "fixed" else 0.0

    @model_validator(mode="after")
    def _check_grid(self) -> "ContinuumConfig":
        if self.beta_mode == "free" and self.grid_min >= self.grid_max:
            raise ValueError("continuum grid_min must be < grid_max")
        if self.beta_mode == "free" and self.beta_sigma:
            raise ValueError(
                "beta_sigma is only meaningful with beta_mode='fixed' (it is "
                "the Gaussian prior on the assumed slope); with beta_mode="
                "'free' the slope is profiled over the grid instead")
        return self


class LineConfig(BaseModel):
    """One emission line in the model.

    role='free':  amplitude F >= 0 is a fit parameter.
    role='tied':  F = ratio x F(tied_to) x dust differential; tie chains
                  (e.g. Hgamma -> Hbeta -> Halpha) resolve to a free root.
    role='off':   excluded from the model entirely.
    """
    model_config = ConfigDict(extra="forbid")

    name: str
    rest_wave: float = Field(..., gt=0, description="rest wavelength [AA]")
    role: Literal["free", "tied", "off"] = "free"
    tied_to: Optional[str] = None
    ratio: Optional[float] = Field(None, gt=0,
                                   description="F_this / F_tied_to, intrinsic")

    @model_validator(mode="after")
    def _check_tie(self) -> "LineConfig":
        if self.role == "tied":
            if not self.tied_to or self.ratio is None:
                raise ValueError(
                    f"line {self.name!r}: role='tied' requires tied_to and ratio")
        return self


class DustConfig(BaseModel):
    """Attenuation applied differentially to tied line ratios.

    Like the fixed continuum slope, A_V carries a Gaussian uncertainty
    ``av_sigma`` (default 0 +/- 0.01) that is propagated through the
    Monte-Carlo error budget (draws are truncated at A_V >= 0)."""
    model_config = ConfigDict(extra="forbid")

    av: float = Field(0.0, ge=0)
    av_sigma: float = Field(0.01, ge=0)
    law: Literal["calzetti", "smc"] = "calzetti"


class MCConfig(BaseModel):
    """Monte-Carlo error budget.

    method='posterior' (default, and what the web application uses): sample
    the truncated-Gaussian posterior of the amplitudes (Gaussian likelihood,
    flat prior on F >= 0) by Gibbs sampling, with the slope drawn from its
    profile weight (free) or Gaussian prior (fixed).  Its limits are
    boundary-safe, which is what the metal-poor regime needs.

    method='bootstrap': resample the photometry ``n`` times and refit; read
    percentiles of the refits.  This reproduces the legacy paper pipeline
    exactly, but near the non-negativity boundary the refits can collapse to
    zero (an undetected line whose band fluctuated low returns an upper limit
    of exactly 0), so prefer the posterior unless you are reproducing those
    published numbers.

    ``fast`` (bootstrap only) pins the slope at the best fit instead of
    re-searching the grid per resample.  ``seed`` fixes the random stream;
    vary it across a catalogue if you stack results (a shared seed
    correlates the noise realisations)."""
    model_config = ConfigDict(extra="forbid")

    n: int = Field(300, ge=10, le=10000)
    seed: int = 9496
    fast: bool = False
    method: Literal["bootstrap", "posterior"] = "posterior"
    keep_draws: bool = Field(
        False, description="return the (thinned) MC draws of the free "
        "parameters in FitResult.posterior_draws, e.g. for corner plots")


class RatioConfig(BaseModel):
    """A derived line ratio to report, with upper-limit handling."""
    model_config = ConfigDict(extra="forbid")

    name: str = "R3"
    numerator: str = "OIII5007"
    denominator: str = "Hbeta"


def default_lines() -> List[LineConfig]:
    """The paper's default registry (see :mod:`lated.lines`)."""
    return [LineConfig(name=n, rest_wave=LINE_WAVELENGTHS[n], role=role,
                       tied_to=tied_to, ratio=ratio)
            for n, role, tied_to, ratio in DEFAULT_REGISTRY]


class FitConfig(BaseModel):
    """Complete, explicit specification of one fit."""
    model_config = ConfigDict(extra="forbid")

    z: float = Field(..., gt=0, description="Lya-slice redshift (fixed)")
    z_sigma: float = Field(0.0, ge=0)
    continuum: ContinuumConfig = Field(default_factory=ContinuumConfig)
    lines: List[LineConfig] = Field(default_factory=default_lines)
    dust: DustConfig = Field(default_factory=DustConfig)
    mc: MCConfig = Field(default_factory=MCConfig)
    ratios: List[RatioConfig] = Field(default_factory=lambda: [RatioConfig()])

    @model_validator(mode="after")
    def _check_lines(self) -> "FitConfig":
        names = [l.name for l in self.lines]
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"duplicate line names: {dupes}")
        enabled = {l.name: l for l in self.lines if l.role != "off"}
        if not any(l.role == "free" for l in enabled.values()):
            raise ValueError("at least one line must have role='free'")
        for l in enabled.values():
            if l.role != "tied":
                continue
            seen, cur = {l.name}, l
            while cur.role == "tied":
                target = enabled.get(cur.tied_to)
                if target is None:
                    raise ValueError(
                        f"line {cur.name!r} is tied to {cur.tied_to!r}, which "
                        "is off or undefined")
                if target.name in seen:
                    raise ValueError(f"tie cycle involving {target.name!r}")
                seen.add(target.name)
                cur = target
        for r in self.ratios:
            for side in (r.numerator, r.denominator):
                if side not in enabled:
                    raise ValueError(
                        f"ratio {r.name!r} references {side!r}, which is not "
                        "an enabled line")
        return self

    # ---- convenience constructors matching the paper's two modes ----------
    @classmethod
    def free_slope(cls, z: float, **kwargs) -> "FitConfig":
        """Slope fitted: beta is profiled over the grid, Halpha + [O III] free,
        Case B ties.  Needs enough bands to constrain it (one for the continuum
        amplitude, one for the slope, and one per free line)."""
        return cls(z=z, **kwargs)

    @classmethod
    def fixed_slope(cls, z: float, beta: float = -2.0, **kwargs) -> "FitConfig":
        """Slope assumed rather than fitted: fixed at ``beta`` (default -2, the
        metal-poor expectation) and marginalised over its 0.3 prior in the
        error budget.

        This is a statement about the *slope*, not about the number of bands.
        It is required when the bands cannot constrain the slope (with the
        three LATED selection bands there are three data and four unknowns),
        but it is equally valid with any larger band set whose slope you would
        rather assume than fit."""
        return cls(z=z, continuum=ContinuumConfig(beta_mode="fixed", beta=beta),
                   **kwargs)

    # -- aliases -----------------------------------------------------------
    # Kept permanently, and exactly equivalent to the names above: these are
    # the names LATED Paper I uses for the two modes.  ``fixed_slope`` /
    # ``free_slope`` are preferred in new code only because they say what the
    # constructor actually does (fixing the slope is equally valid with more
    # than three bands), not because these are going away.
    @classmethod
    def three_band(cls, z: float, beta: float = -2.0, **kwargs) -> "FitConfig":
        """The paper's selection-band mode: an exact alias of
        :meth:`fixed_slope`."""
        return cls.fixed_slope(z, beta=beta, **kwargs)

    @classmethod
    def paper_default(cls, z: float, **kwargs) -> "FitConfig":
        """The paper's multi-band mode: an exact alias of
        :meth:`free_slope`."""
        return cls.free_slope(z, **kwargs)

    def with_line_role(self, name: str, role: str,
                       tied_to: Optional[str] = None,
                       ratio: Optional[float] = None) -> "FitConfig":
        """Copy of this config with one line's role changed.  The copy is
        fully re-validated, so e.g. switching off a line that others are
        tied to raises immediately rather than failing inside fit()."""
        if name not in {l.name for l in self.lines}:
            raise KeyError(f"no line named {name!r}")
        data = self.model_dump()
        for l in data["lines"]:
            if l["name"] == name:
                l["role"] = role
                l["tied_to"] = tied_to if role == "tied" else None
                l["ratio"] = ratio if role == "tied" else None
        return FitConfig.model_validate(data)

    def with_contaminant_mode(self, frac: float = 0.35) -> "FitConfig":
        """Tie [N II]+[S II] to Halpha (metal-rich contaminant mode)."""
        cfg = self
        for name, ratio in contaminant_ties(frac).items():
            cfg = cfg.with_line_role(name, "tied", tied_to="Halpha", ratio=ratio)
        return cfg

    def with_balmer(self, case: str = "B", te: float = 10000.0,
                    ne: float = 100.0) -> "FitConfig":
        """Copy with the Balmer tie ratios set for the given recombination
        case at (T_e, n_e) (see :func:`lated.lines.balmer_ratios`).
        Only lines that are currently tied to their default parent
        (Hbeta -> Halpha, higher orders -> Hbeta) are rewritten; free/off
        lines and custom ties are left alone.  Case B at
        (1e4 K, 1e2 cm^-3) reproduces the paper defaults."""
        ratios = balmer_ratios(case, te, ne)
        parent = {"Hbeta": "Halpha"}
        data = self.model_dump()
        for l in data["lines"]:
            r = ratios.get(l["name"])
            if (r is not None and l["role"] == "tied"
                    and l["tied_to"] == parent.get(l["name"], "Hbeta")):
                l["ratio"] = r
        return FitConfig.model_validate(data)

    def with_case_b(self, te: float = 10000.0,
                    ne: float = 100.0) -> "FitConfig":
        """Backwards-compatible alias for :meth:`with_balmer` (case='B')."""
        return self.with_balmer("B", te, ne)
