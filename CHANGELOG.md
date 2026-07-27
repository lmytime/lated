# Changelog

## Unreleased

### Changed
### Added
- `FitConfig.fixed_slope` and `FitConfig.free_slope`, clearer names for what
  `FitConfig.three_band` and `FitConfig.paper_default` do.  "Three band" said
  nothing about what the constructor actually configures: it fixes the
  continuum slope, which is required at three bands (three data, four
  unknowns) but equally valid with four, five or more bands whose slope you
  would rather assume than fit (the bundled GLIMPSE-16043 example uses it with
  four).  `three_band` and `paper_default` remain as permanent, exact,
  warning-free aliases: they are the names LATED Paper I uses, and existing
  code needs no change.
- **The default Monte-Carlo method is now `posterior`, matching the web
  application.**  Previously the Python API defaulted to `bootstrap` while the
  web app used the posterior, so the same photometry could come back with a
  different error budget (and, near the detection threshold, a different ratio
  status) depending on which interface you used.  Every other default already
  agreed (300 draws, seed 9496, A_V jitter 0.01, free slope), so `method` was
  the last divergence.  Pass `mc={"method": "bootstrap"}` explicitly to
  reproduce the legacy paper pipeline; the parity suite now does so.
- `RatioResult.is_limit` is method-aware.  It was the bootstrap-only test
  "numerator's 16th percentile <= 0", which can never fire on the posterior's
  strictly positive draws, so under the posterior it silently reported `False`
  for genuine upper limits.  It now follows the reported status there, while
  the bootstrap path keeps the legacy formula that parity pins.

### Fixed
- Ratio status no longer depends on the Monte-Carlo seed for weak sources.
  When neither line cleared its own detection threshold the ratio was reported
  as `unconstrained`, even though its posterior still bounded the ratio from
  above.  Because that threshold was a hard cut on noisy percentile estimates,
  a source sitting near it flipped between `upper_limit` and `unconstrained`
  from one random stream to the next (observed: 14 of 40 seeds on a real
  faint source).  The engine now quotes the limit whenever the ratio's own
  posterior carries information, and reserves `unconstrained` for a bound that
  has run into the ratio clip, which is both stable and strictly more
  informative.  Such limits are flagged in `warnings` as denominator-driven.
  Bootstrap results are unchanged (their upper percentile is clip-pinned).

## 0.1.1 (2026-07-09)

Compatibility fixes for newer NumPy and SciPy, plus web-app refinements.

### Fixed
- NumPy 2.x compatibility: `import lated` failed on NumPy >= 2.1 (which removed
  `np.trapz`).  The integration helper now uses `np.trapezoid` where available
  and falls back to `np.trapz` on NumPy < 2.
- SciPy NNLS robustness: a fit with two free lines that respond only in the same
  band (a rank-deficient design) raised `LinAlgError` or `ValueError` on
  SciPy's rewritten `nnls` (>= 1.15) instead of returning a result.  The solver
  now falls back to a negligibly regularised non-negative least squares in that
  case; the ordinary full-rank fit, and exact parity with the paper pipeline,
  are unchanged.

### Web app
- The window-preset buttons (WZ2.1 through CUSTOM) now stay on a single
  segmented row instead of wrapping.
- Removed the clipboard "paste" button from the photometry panel.
- The delete control on a reported ratio no longer wraps onto its own line.
- Added a GLIMPSE-16043 (Fujimoto et al. 2025a) literature example whose
  undetermined redshift is fitted over its photometric-redshift range; examples
  can now carry a redshift range.  The existing GLIMPSE-16043 example is
  relabelled Fujimoto 2025b to distinguish the two sets of fluxes.

## 0.1.0 (2026-07-08)

Initial public release, accompanying LATED Paper I.

- Transparent fitting engine: power-law continuum + emission lines fitted
  through real filter transmission curves, with every parameter's role
  (free / fixed / tied) explicit and user-configurable.
- Exact numerical parity with the LATED paper pipeline in bootstrap mode;
  a posterior (truncated-Gaussian Gibbs) sampler as the statistically
  preferred alternative for upper/lower limits.
- Balmer-ratio ties from Osterbrock & Ferland (2006) Case A/B tables,
  selectable by (T_e, n_e); dust via Calzetti or SMC with A_V uncertainty
  propagation.
- 46 bundled JWST NIRCam + MIRI and Roman WFI filter curves (SVO).
- Line-ratio verdicts (measured / 2-sigma upper / lower limit /
  unconstrained) with per-line flux sensitivities and depth warnings.
- FastAPI + vanilla-JS web application (`lated serve`): SED and corner
  plots as publication-ready SVG/PDF, literature one-click examples,
  full parameter-role controls.
- Python API quickstart notebook in `examples/`.
