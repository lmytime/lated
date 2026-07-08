"""LATED window presets: redshift + the three selection bands
([O III]+Hbeta band, Halpha band, red continuum band), fitted in the
paper's three-band mode (continuum slope fixed at beta = -2)."""

from typing import Dict, List

from pydantic import BaseModel

class WindowPreset(BaseModel):
    id: str
    label: str
    z: float
    bands: List[str]      # [OIII band, Halpha band, continuum band]
    fix_beta: float = -2.0


WINDOW_PRESETS: Dict[str, WindowPreset] = {p.id: p for p in [
    WindowPreset(id="Wz2.1", label="Wz2.1 (z = 2.1)", z=2.12,
                 bands=["F150W", "F200W", "F277W"]),
    WindowPreset(id="Wz3.1", label="Wz3.1 (z = 3.1)", z=3.05,
                 bands=["F200W", "F277W", "F356W"]),
    WindowPreset(id="Wz4.4", label="Wz4.4 (z = 4.4)", z=4.40,
                 bands=["F277W", "F356W", "F444W"]),
    WindowPreset(id="Wz6.1", label="Wz6.1 (z = 6.1)", z=6.10,
                 bands=["F356W", "F444W", "F410M"]),
]}
