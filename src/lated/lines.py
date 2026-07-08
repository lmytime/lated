"""Emission-line rest wavelengths and the default line registry.

Wavelengths [AA] are SDSS/NIST vacuum values (the paper pipeline tabulates
the conventional air values; the < 2 AA rest-frame difference is negligible
for band photometry).  The default registry encodes the paper's model:

- Halpha free; the Case B Balmer series Hbeta..H10 tied to it
  (Hbeta = Halpha / 2.86, higher orders tied to Hbeta with the
  Osterbrock & Ferland 2006 T_e = 1e4 K, n_e ~ 1e2 cm^-3 intensities);
- [O III] 5007 free with 4959 tied at 1/2.98;
- He II 4686, [O II] 3727, [Ne III] 3869 and He I 10830 present but
  switched off;
- [N II] + [S II] present but off (the metal-rich contaminant mode ties
  them to Halpha; see :func:`contaminant_ties`).

Every entry is user-editable: roles can be switched between ``free``,
``tied`` and ``off``, tie ratios changed, and custom lines added.
"""

from typing import Dict, List, Tuple

# VACUUM rest wavelengths [AA] (SDSS/NIST vacuum values; [O II] is the
# doublet-mean 3727.09/3729.86).  NOTE: the paper pipeline's table
# (photometry/line_excess.LINES) quotes the conventional AIR values for the
# optical lines; the shift (< 2 AA rest, i.e. < 1e-4 of any band width) is
# negligible for band photometry but the parity tests control for it
# explicitly.  Line names keep their conventional air labels (OIII5007 etc.).
LINE_WAVELENGTHS: Dict[str, float] = {
    "Lya": 1215.67,
    "HeII1640": 1640.42,
    "HeII4686": 4686.99,
    "OII3727": 3728.48,
    "NeIII3869": 3869.86,
    "H10": 3798.98,
    "H9": 3836.48,
    "H8": 3890.15,
    "Hepsilon": 3971.20,
    "Hdelta": 4102.89,
    "Hgamma": 4341.68,
    "Hbeta": 4862.68,
    "OIII4959": 4960.30,
    "OIII5007": 5008.24,
    "Halpha": 6564.61,
    "NII6584": 6585.27,
    "SII6717": 6718.29,
    "SII6731": 6732.67,
    "HeI10830": 10833.30,
    "PaBeta": 12821.60,
}

CASE_B_HA_HB = 2.86     # Halpha/Hbeta, Case B, T_e = 1e4 K
OIII_5007_4959 = 2.98   # [O III] 5007/4959 (fixed atomic ratio)

# Case B intensities relative to Hbeta (Osterbrock & Ferland 2006),
# T_e = 1e4 K, n_e ~ 1e2 cm^-3: the default row of BALMER_TABLE below.
BALMER_VS_HBETA: List[Tuple[str, float]] = [
    ("Hgamma", 0.468),
    ("Hdelta", 0.259),
    ("Hepsilon", 0.159),
    ("H8", 0.105),
    ("H9", 0.0731),
    ("H10", 0.0530),
]

# Balmer-line intensity ratios vs recombination case, electron temperature
# and density, from Osterbrock & Ferland (2006): Case A (low-density limit,
# their p.72 table) and Case B (their p.78 table, n_e = 1e2/1e4/1e6 cm^-3).
# 'ha_hb' is Halpha/Hbeta; the other entries are line/Hbeta.
#
# Two documented adjustments:
# - The Case B (1e4 K, 1e2 cm^-3) row keeps the paper pipeline's
#   3-significant-figure values exactly (2.86 vs OF06's 2.863, etc.) so the
#   default configuration reproduces the published fits bit-for-bit.
# - OF06's Case B table does not list Hepsilon/H8/H9; they are scaled from
#   the (1e4 K, 1e2) values with a factor interpolated linearly in the upper
#   level n between the tabulated Hdelta (n=6) and H10 (n=10) trends
#   (interpolation error well below 1 per cent).
BALMER_CASES = ("A", "B")
CASE_A_TEMPERATURES = (2500.0, 5000.0, 10000.0, 20000.0)  # K
CASE_B_TEMPERATURES = (5000.0, 10000.0, 20000.0)          # K
CASE_B_DENSITIES = (100.0, 10000.0, 1000000.0)            # cm^-3

_CASE_A = {
    2500.0: {"ha_hb": 3.42, "Hgamma": 0.439, "Hdelta": 0.237,
             "Hepsilon": 0.143, "H8": 0.0957, "H9": 0.0671, "H10": 0.0488},
    5000.0: {"ha_hb": 3.10, "Hgamma": 0.458, "Hdelta": 0.250,
             "Hepsilon": 0.153, "H8": 0.102, "H9": 0.0717, "H10": 0.0522},
    10000.0: {"ha_hb": 2.86, "Hgamma": 0.470, "Hdelta": 0.262,
              "Hepsilon": 0.159, "H8": 0.107, "H9": 0.0748, "H10": 0.0544},
    20000.0: {"ha_hb": 2.69, "Hgamma": 0.485, "Hdelta": 0.271,
              "Hepsilon": 0.167, "H8": 0.112, "H9": 0.0785, "H10": 0.0571},
}

# OF06 p.78 exact entries (ha_hb, Hgamma, Hdelta, H10) per (T_e, n_e).
_CASE_B_EXACT = {
    (5000.0, 100.0): (3.041, 0.458, 0.251, 0.0515),
    (5000.0, 10000.0): (3.001, 0.460, 0.253, 0.0520),
    (5000.0, 1000000.0): (2.918, 0.465, 0.258, 0.0616),
    (10000.0, 100.0): (2.86, 0.468, 0.259, 0.0530),   # paper row (see note)
    (10000.0, 10000.0): (2.847, 0.469, 0.260, 0.0533),
    (10000.0, 1000000.0): (2.806, 0.471, 0.262, 0.0591),
    (20000.0, 100.0): (2.747, 0.475, 0.264, 0.0540),
    (20000.0, 10000.0): (2.739, 0.476, 0.264, 0.0541),
    (20000.0, 1000000.0): (2.725, 0.476, 0.266, 0.0575),
}
_REF_HD, _REF_H10 = 0.259, 0.0530          # the (1e4, 1e2) anchors
_REF_MID = {"Hepsilon": (7, 0.159), "H8": (8, 0.105), "H9": (9, 0.0731)}


def _case_b_row(te, ne):
    ha_hb, hg, hd, h10 = _CASE_B_EXACT[(te, ne)]
    row = {"ha_hb": ha_hb, "Hgamma": hg, "Hdelta": hd, "H10": h10}
    f6, f10 = hd / _REF_HD, h10 / _REF_H10
    for name, (n, ref) in _REF_MID.items():
        row[name] = round(ref * (f6 + (f10 - f6) * (n - 6) / 4.0), 4)
    return row


BALMER_TABLE = {
    "A": {te: dict(row) for te, row in _CASE_A.items()},
    "B": {te: {ne: _case_b_row(te, ne) for ne in CASE_B_DENSITIES}
          for te in CASE_B_TEMPERATURES},
}


def balmer_ratios(case: str = "B", te: float = 10000.0,
                  ne: float = 100.0) -> Dict[str, float]:
    """Balmer tie ratios for the given recombination case and (T_e, n_e).

    Returns {'Hbeta': F_Hbeta/F_Halpha, 'Hgamma': F_Hgamma/F_Hbeta, ...}
    ready to write into the line registry.  Case A (optically thin Lyman
    lines) is tabulated in the low-density limit only, so ``ne`` is ignored
    there; Case B (optically thick, the nebular standard) supports
    n_e = 1e2, 1e4 and 1e6 cm^-3."""
    if case not in BALMER_TABLE:
        raise ValueError(f"case must be one of {BALMER_CASES}, got {case!r}")
    temps = CASE_A_TEMPERATURES if case == "A" else CASE_B_TEMPERATURES
    if te not in temps:
        raise ValueError(f"Case {case} T_e must be one of {temps} K, "
                         f"got {te!r}")
    if case == "A":
        row = BALMER_TABLE["A"][te]
    else:
        if ne not in CASE_B_DENSITIES:
            raise ValueError(f"n_e must be one of {CASE_B_DENSITIES} cm^-3, "
                             f"got {ne!r}")
        row = BALMER_TABLE["B"][te][ne]
    out = {"Hbeta": 1.0 / row["ha_hb"]}
    out.update({k: v for k, v in row.items() if k != "ha_hb"})
    return out


def case_b_ratios(te: float = 10000.0, ne: float = 100.0) -> Dict[str, float]:
    """Backwards-compatible alias for :func:`balmer_ratios` with case='B'."""
    return balmer_ratios("B", te, ne)

# (name, role, tied_to, ratio) rows for the default registry; ``ratio`` is the
# intrinsic flux ratio F_line / F_tied_to (dust differentials are applied by
# the engine on top of these).
DEFAULT_REGISTRY: List[Tuple[str, str, str, float]] = (
    [("Halpha", "free", None, None),
     ("Hbeta", "tied", "Halpha", 1.0 / CASE_B_HA_HB)]
    + [(name, "tied", "Hbeta", ratio) for name, ratio in BALMER_VS_HBETA]
    + [("OIII5007", "free", None, None),
       ("OIII4959", "tied", "OIII5007", 1.0 / OIII_5007_4959),
       # He II 4686 sits inside the [O III]+Hbeta band in every LATED window;
       # off by default (paper parity), switch free for He II-strong sources
       # so its flux is not absorbed by the [O III] amplitude.
       ("HeII4686", "off", None, None),
       ("OII3727", "off", None, None),
       ("NeIII3869", "off", None, None),
       ("HeI10830", "off", None, None),
       ("NII6584", "off", None, None),
       ("SII6717", "off", None, None),
       ("SII6731", "off", None, None)]
)


def contaminant_ties(frac: float = 0.35) -> Dict[str, float]:
    """[N II]+[S II] tie ratios to Halpha for the metal-rich contaminant
    mode: a total of ``frac`` x F(Halpha) split equally over the three
    lines, as in the paper engine."""
    return {name: frac / 3.0 for name in ("NII6584", "SII6717", "SII6731")}
