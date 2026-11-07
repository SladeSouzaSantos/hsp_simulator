"""Geometric DIRECT-beam shadow fractions for the experimental Solar 3D scene.

Coordinate frame matches the React Three.js editor: X=east, Y=up, Z=north.
Scene shapes are oriented *solid boxes*; panels have a tilted top surface.
The ray directions are toward the Sun and the sample points lie on the
front face of each module, avoiding the module's own body.

This is deterministic geometric area sampling, NOT a POA, kWh, or electrical
loss model. The scene has no terrain, vegetation transparency, sky-view
factor, or diffuse-radiation occlusion. All surfaces are opaque.
"""
from __future__ import annotations

from typing import Literal
import math

import numpy as np
from pydantic import BaseModel, Field
from solar3d.backend.mesh import MeshObstacle, ray_mesh_mask

EPSILON = 1e-5


class Position3D(BaseModel):
    east: float = Field(ge=-10000, le=10000, allow_inf_nan=False)
    north: float = Field(ge=-10000, le=10000, allow_inf_nan=False)
    elevation: float = Field(ge=-10000, le=10000, allow_inf_nan=False)


class SceneObject(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=0, max_length=120)
    kind: Literal["building", "obstacle", "panel"]
    position: Position3D
    width: float = Field(gt=0, le=1000, allow_inf_nan=False)
    depth: float = Field(gt=0, le=1000, allow_inf_nan=False)
    height: float = Field(gt=0, le=1000, allow_inf_nan=False)
    azimuth: float = Field(ge=0, lt=360, allow_inf_nan=False)
    tilt: float = Field(ge=0, le=90, allow_inf_nan=False)


def direction_towards_sun(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """Return unit sun vector [E, Up, N] from geographic angles."""
    a, h = math.radians(azimuth_deg), math.radians(elevation_deg)
    return np.array([math.sin(a) * math.cos(h), math.sin(h),
                     math.cos(a) * math.cos(h)], dtype=float)


def rotation_matrix(obj: SceneObject) -> np.ndarray:
    """Match Three.js group.rotation.y and child mesh.rotation.x.

    R = Ry(azimuth) @ Rx(tilt) for panels; solids have only Ry(azimuth).
    Using the right-handed Three.js matrix gives an east-facing panel for
    azimuth=90 degrees and a north-facing one for azimuth=0 degrees.
    """
    a = math.radians(obj.azimuth)
    b = math.radians(obj.tilt if obj.kind == "panel" else 0.0)
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    return np.array([
        [ca, sa * sb, sa * cb],
        [0, cb, -sb],
        [-sa, ca * sb, ca * cb],
    ], dtype=float)


def center(obj: SceneObject) -> np.ndarray:
    return np.array([obj.position.east, obj.position.elevation,
                     obj.position.north], dtype=float)


def sample_panel_face(obj: SceneObject, columns: int, rows: int) -> tuple[np.ndarray, np.ndarray]:
    """Uniform cell-center quadrature of the FRONT (+local Y) module face.

    Local row varies Z (length), column varies X (width). Return 3D
    points and outward face normal in world coordinates.
    """
    if obj.kind != "panel":
        raise ValueError("Object must be a panel")
    x = (np.arange(columns, dtype=float) + 0.5) / columns * obj.width - obj.width / 2
    z = (np.arange(rows, dtype=float) + 0.5) / rows * obj.depth - obj.depth / 2
    xx, zz = np.meshgrid(x, z)
    local = np.column_stack([
        xx.ravel(),
        np.full(xx.size, obj.height / 2 + EPSILON),
        zz.ravel(),
    ])
    rot = rotation_matrix(obj)
    world = local @ rot.T + center(obj)
    normal = rot[:, 1].copy()
    return world, normal


def ray_intersections_with_box(
    origins: np.ndarray, direction: np.ndarray,
    obj: SceneObject,
) -> np.ndarray:
    """Vectorized ray/oriented-solid-box slab intersections.

    Intersections for ray t >= EPSILON, with world/local rotations
    applied consistently with the frontend. Points inside solids count
    as blocked: a colliding scene is physically invalid, not clear.
    """
    rot = rotation_matrix(obj)
    local_origins = (origins - center(obj)) @ rot
    local_dir = direction @ rot
    half = np.array([obj.width, obj.height, obj.depth]) / 2
    near = np.full(len(origins), -np.inf, dtype=float)
    far = np.full(len(origins), np.inf, dtype=float)
    valid = np.ones(len(origins), dtype=bool)
    for axis in range(3):
        d = float(local_dir[axis])
        coordinate = local_origins[:, axis]
        if abs(d) < 1e-12:
            valid &= (coordinate >= -half[axis]) & (coordinate <= half[axis])
            continue
        t1 = (-half[axis] - coordinate) / d
        t2 = (+half[axis] - coordinate) / d
        near = np.maximum(near, np.minimum(t1, t2))
        far = np.minimum(far, np.maximum(t1, t2))
    return valid & (far >= np.maximum(near, EPSILON))


def fraction_blocked(
    panel: SceneObject,
    objects: list[SceneObject],
    sun_direction: np.ndarray,
    columns: int = 4,
    rows: int = 6,
    meshes: list[MeshObstacle] | None = None,
) -> tuple[float | None, list[int] | None]:
    """Area blocked by opaque boxes along rays toward a given sun position.

    None means no FRONT-side direct-beam incidence (night or sun behind panel),
    not 0% shading. A returned 0.0 means eligible and unblocked.
    The mask is row-major Z then X, 1 blocked / 0 unblocked.
    """
    if sun_direction.shape != (3,) or not np.isfinite(sun_direction).all():
        raise ValueError("Invalid sun direction")
    magnitude = float(np.linalg.norm(sun_direction))
    if magnitude < 1e-12:
        raise ValueError("Sun direction must be non-zero")
    sun = sun_direction / magnitude
    points, normal = sample_panel_face(panel, columns, rows)
    if sun[1] <= 0 or float(np.dot(normal, sun)) <= 1e-12:
        return None, None
    blocked = np.zeros(len(points), dtype=bool)
    for obj in objects:
        if obj.id == panel.id:
            continue
        # Restrict rays to points not yet shadowed.
        remaining = np.flatnonzero(~blocked)
        if remaining.size == 0:
            break
        blocked[remaining] |= ray_intersections_with_box(
            points[remaining], sun, obj,
        )
    for mesh in meshes or []:
        remaining = np.flatnonzero(~blocked)
        if len(remaining) == 0:
            break
        blocked[remaining] |= ray_mesh_mask(points[remaining], sun, mesh)
    return float(np.mean(blocked)), blocked.astype(int).tolist()
