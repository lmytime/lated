# Changelog

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
