import collections
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
import scipy
import scipy.stats as st

import numpy as np
import pyvista as pv
from deepdrr import geo
import deepdrr
import time

from deepdrr.vol import Volume
from deepdrr.utils import listify
from deepdrr.projector.material_coefficients import material_coefficients

from collections import defaultdict


_default_densities = {
    "polyethylene": 1.05,  # polyethyelene is 0.97, but ABS plastic is 1.05
    "concrete": 1.5,
    "iron": 7.5,
    "titanium": 7,
    "bone": 1.5,
}

def voxelize_on_grid(
    mesh: pv.PolyData,
    grid: pv.PointSet,
    shape: Tuple[int, int, int],
) -> Tuple[np.ndarray, geo.FrameTransform]:

    surface = mesh.extract_geometry()
    if not surface.is_all_triangles:
        surface.triangulate(inplace=True)

    selection = grid.select_enclosed_points(surface, tolerance=0.0, check_surface=False)
    voxels = selection.point_data['SelectedPoints'].reshape(shape)

    kernlen = 3
    kern3d = np.ones((kernlen, kernlen, kernlen))
    voxels = scipy.signal.convolve(voxels, kern3d, mode='same')
    voxels = voxels > 0.5

    return voxels

def from_meshes(
    voxel_size: float = 0.1,
    world_from_anatomical: Optional[geo.FrameTransform] = None,
    surfaces: List[Tuple[str, float, pv.PolyData]] = [], # material, density, surface
):
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

    voxel_size = listify(voxel_size, 3)
    density_x, density_y, density_z = voxel_size

    spacing = np.array(voxel_size)
    if bounds is None:
        bounds = surface.bounds

    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    origin = np.array([x_min, y_min, z_min])
    anatomical_from_ijk = geo.FrameTransform.from_rt(np.diag(spacing), origin)

    x_b = np.arange(x_min, x_max, density_x)
    y_b = np.arange(y_min, y_max, density_y)
    z_b = np.arange(z_min, z_max, density_z)
    x, y, z = np.meshgrid(x_b, y_b, z_b, indexing='ij')

    grid = pv.PointSet(np.c_[x.ravel(), y.ravel(), z.ravel()])

    segmentations = []
    for material, density, surface in surfaces:
        segmentations.append(voxelize_on_grid(surface, grid, x.shape))

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
            if material not in _default_densities:
                raise ValueError(f"Material {material} not found in default densities")
            density = _default_densities[material]
        data += segmentation * density

    return Volume(
        data,
        material_segmentations_combined,
        anatomical_from_ijk,
        world_from_anatomical,
        anatomical_coordinate_system=None,
    )
