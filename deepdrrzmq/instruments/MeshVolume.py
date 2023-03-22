#!/usr/bin/env python3
from imp import source_from_cache
import logging
from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import numpy as np
import pyvista as pv
from deepdrr import geo

from deepdrr.vol import Volume
from deepdrr import utils
from deepdrr.utils import data_utils

from deepdrr.projector.material_coefficients import material_coefficients

from collections import defaultdict


log = logging.getLogger(__name__)


class MeshVolume(Volume, ABC):
    _default_densities = {
        "polyethylene": 1.05,  # polyethyelene is 0.97, but ABS plastic is 1.05
        "concrete": 1.5,
        "iron": 7.5,
        "titanium": 7,
        "bone": 1.5,
    }

    def __init__(
        self,
        voxel_size: float = 0.1,
        world_from_anatomical: Optional[geo.FrameTransform] = None,
        surfaces: List[Tuple[str, float, pv.PolyData]] = [], # material, density, surface
    ):
        self.voxel_size = voxel_size

        bounds = []
        for material, density, surface in surfaces:
            bounds.append(surface.bounds)

        bounds = np.array(bounds)
        x_min, y_min, z_min = bounds[:, [0, 2, 4]].min(0)
        x_max, y_max, z_max = bounds[:, [1, 3, 5]].max(0)
        bounds = [x_min, x_max, y_min, y_max, z_min, z_max]

        # combine surfaces wiht same material and approx same density
        surface_dict = defaultdict(list)
        for material, density, surface in surfaces:
            surface_dict[(material, int(density * 100))].append((material, density, surface))
        
        combined_surfaces = []
        for _, surfaces in surface_dict.items():
            combined_surfaces.append((surfaces[0][0], surfaces[0][1], sum([s[2] for s in surfaces], pv.PolyData())))
        surfaces = combined_surfaces

        segmentations = []
        for material, density, surface in surfaces:
            segmentation, anatomical_from_ijk = utils.mesh_utils.voxelize(
                surface,
                density=self.voxel_size,
                bounds=bounds,
            )
            segmentations.append(segmentation)

        material_segmentations = defaultdict(list)
        for (material, _, _), segmentation in zip(surfaces, segmentations):
            material_segmentations[material].append(segmentation)

        material_segmentations_combined = {}
        for material, seg in material_segmentations.items():
            material_segmentations_combined[material] = np.logical_or.reduce(seg).astype(np.uint8)

        data = np.zeros_like(list(material_segmentations_combined.values())[0], dtype=np.float64)
        for (material, density, _), segmentation in zip(surfaces, segmentations):
            # if density is negative, use the default density
            if density < -0.01:
                if material not in self._default_densities:
                    raise ValueError(f"Material {material} not found in default densities")
                density = self._default_densities[material]
            data += segmentation * density

        super().__init__(
            data,
            material_segmentations_combined,
            anatomical_from_ijk,
            world_from_anatomical,
            anatomical_coordinate_system=None,
        )

    # def get_mesh_in_world(self, full: bool = True, use_cached: bool = True):
    #     mesh = sum(self.surfaces.values(), pv.PolyData())
    #     mesh.transform(geo.get_data(self.world_from_anatomical), inplace=True)
    #     # meshh += pv.Sphere(
    #     #     center=list(self.world_from_ijk @ geo.point(0, 0, 0)), radius=5
    #     # )

    #     x, y, z = np.array(self.shape) - 1
    #     points = [
    #         [0, 0, 0],
    #         [0, 0, z],
    #         [0, y, 0],
    #         [0, y, z],
    #         [x, 0, 0],
    #         [x, 0, z],
    #         [x, y, 0],
    #         [x, y, z],
    #     ]

    #     points = [list(self.world_from_ijk @ geo.point(p)) for p in points]
    #     mesh += pv.Line(points[0], points[1])
    #     mesh += pv.Line(points[0], points[2])
    #     mesh += pv.Line(points[3], points[1])
    #     mesh += pv.Line(points[3], points[2])
    #     mesh += pv.Line(points[4], points[5])
    #     mesh += pv.Line(points[4], points[6])
    #     mesh += pv.Line(points[7], points[5])
    #     mesh += pv.Line(points[7], points[6])
    #     mesh += pv.Line(points[0], points[4])
    #     mesh += pv.Line(points[1], points[5])
    #     mesh += pv.Line(points[2], points[6])
    #     mesh += pv.Line(points[3], points[7])

    #     return mesh
