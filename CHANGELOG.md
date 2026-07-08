# Changelog

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
