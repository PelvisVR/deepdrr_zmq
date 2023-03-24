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
import pyvista as pv
from deepdrr import geo

from deepdrr.vol import Volume
from deepdrr.utils import listify
from deepdrr.projector.material_coefficients import material_coefficients

from collections import defaultdict


log = logging.getLogger(__name__)


def voxelize_inner(mesh, density=None, check_surface=True):
    """Voxelize mesh to UnstructuredGrid.

    Parameters
    ----------
    density : float, np.ndarray or collections.abc.Sequence
        The uniform size of the voxels when single float passed.
        A list of densities along x,y,z directions.
        Defaults to 1/100th of the mesh length.

    check_surface : bool
        Specify whether to check the surface for closure. If on, then the
        algorithm first checks to see if the surface is closed and
        manifold. If the surface is not closed and manifold, a runtime
        error is raised.

    Returns
    -------
    pyvista.UnstructuredGrid
        Voxelized unstructured grid of the original mesh.

    Examples
    --------
    Create an equal density voxelized mesh.

    >>> import pyvista as pv
    >>> from pyvista import examples
    >>> mesh = examples.download_bunny_coarse().clean()
    >>> vox = pv.voxelize(mesh, density=0.01)
    >>> vox.plot(show_edges=True)

    Create a voxelized mesh using unequal density dimensions.

    >>> vox = pv.voxelize(mesh, density=[0.01, 0.005, 0.002])
    >>> vox.plot(show_edges=True)

    """
    if not pv.is_pyvista_dataset(mesh):
        mesh = pv.wrap(mesh)
    if density is None:
        density = mesh.length / 100
    if isinstance(density, (int, float, np.number)):
        density_x, density_y, density_z = [density] * 3
    elif isinstance(density, (collections.abc.Sequence, np.ndarray)):
        density_x, density_y, density_z = density
    else:
        raise TypeError(f'Invalid density {density!r}, expected number or array-like.')

    # check and pre-process input mesh
    surface = mesh.extract_geometry()  # filter preserves topology
    if not surface.faces.size:
        # we have a point cloud or an empty mesh
        raise ValueError('Input mesh must have faces for voxelization.')
    if not surface.is_all_triangles:
        # reduce chance for artifacts, see gh-1743
        surface.triangulate(inplace=True)

    x_min, x_max, y_min, y_max, z_min, z_max = mesh.bounds
    x = np.arange(x_min, x_max, density_x)
    y = np.arange(y_min, y_max, density_y)
    z = np.arange(z_min, z_max, density_z)
    x, y, z = np.meshgrid(x, y, z)

    # Create unstructured grid from the structured grid
    grid = pv.StructuredGrid(x, y, z)
    ugrid = pv.UnstructuredGrid(grid)

    # get part of the mesh within the mesh's bounding surface.
    selection = ugrid.select_enclosed_points(surface, tolerance=0.0, check_surface=check_surface)
    mask = selection.point_data['SelectedPoints'].view(np.bool_)

    # extract cells from point indices
    vox = ugrid.extract_points(mask)
    return vox

def voxelize(
    surface: pv.PolyData,
    density: float = 0.2,
    bounds: Optional[List[float]] = None,
) -> Tuple[np.ndarray, geo.FrameTransform]:
    """Voxelize the surface mesh with the given density.

    Args:
        surface (pv.PolyData): The surface.
        density (Union[float, Tuple[float, float, float]]): Either a single float or a
            list of floats giving the size of a voxel in x, y, z.
            (This is really a spacing, but it's misnamed in pyvista.)

    Returns:
        Tuple[np.ndarray, geo.FrameTransform]: The voxelized segmentation of the surface as np.uint8 and the associated world_from_ijk transform.
    """
    density = listify(density, 3)
    voxels = voxelize_inner(surface, density=density, check_surface=False)

    spacing = np.array(density)
    if bounds is None:
        bounds = surface.bounds

    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    size = np.array([(x_max - x_min), (y_max - y_min), (z_max - z_min)])
    if np.any(size) < 0:
        raise ValueError(f"invalid bounds: {bounds}")
    x, y, z = np.ceil(size / spacing).astype(int) + 1
    origin = np.array([x_min, y_min, z_min])
    world_from_ijk = geo.FrameTransform.from_rt(np.diag(spacing), origin)
    ijk_from_world = world_from_ijk.inv

    data = np.zeros((x, y, z), dtype=np.uint8)
    vectors = np.array(voxels.points)
    A_h = np.hstack((vectors, np.ones((vectors.shape[0], 1))))
    transform = np.array(ijk_from_world)
    B = (transform @ A_h.T).T[:, :3]
    B = np.round(B).astype(int)
    data[B[:, 0], B[:, 1], B[:, 2]] = 1

    return data, world_from_ijk


_default_densities = {
    "polyethylene": 1.05,  # polyethyelene is 0.97, but ABS plastic is 1.05
    "concrete": 1.5,
    "iron": 7.5,
    "titanium": 7,
    "bone": 1.5,
}

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

    segmentations = []
    for material, density, surface in surfaces:
        segmentation, anatomical_from_ijk = voxelize(
            surface,
            density=voxel_size,
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
