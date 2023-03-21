
from typing import Dict, Optional
from deepdrr.instruments import Instrument
from deepdrr import geo


class KWire450mm(Instrument):

    def __init__(
        self,
        density: float = 0.1,
        world_from_anatomical: Optional[geo.FrameTransform] = None,
        densities: Dict[str, float] = {},
    ):
        super().__init__(density, world_from_anatomical, densities)

