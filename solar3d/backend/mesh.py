"""Opaque triangular obstacles for experimental 3D ray shadowing.

Vertices use the same local metres as Three.js and the F3 box engine:
[x=east, y=up, z=north]. Faces are double-sided; no tree porosity or horizon.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
import numpy as np


class MeshObstacle(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=0, max_length=120)
    vertices: list[tuple[float, float, float]] = Field(min_length=3, max_length=500)
    triangles: list[tuple[int, int, int]] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_mesh(self):
        vertices = np.asarray(self.vertices, dtype=float)
        if not np.isfinite(vertices).all() or np.max(np.abs(vertices)) > 10000:
            raise ValueError("Coordenadas de vértices inválidas")
        for i, j, k in self.triangles:
            if min(i, j, k) < 0 or max(i, j, k) >= len(vertices):
                raise ValueError("Índices de faces fora dos vértices")
            a, b, c = vertices[[i, j, k]]
            if np.linalg.norm(np.cross(b - a, c - a)) <= 1e-8:
                raise ValueError("Face triangular degenerada")
        return self


def ray_mesh_mask(origins: np.ndarray, direction: np.ndarray, mesh: MeshObstacle) -> np.ndarray:
    """Two-sided Möller–Trumbore ray/triangle intersections (t>1e-5)."""
    result = np.zeros(len(origins), dtype=bool)
    xyz = np.asarray(mesh.vertices, dtype=float)
    d = np.asarray(direction, dtype=float)
    if d.shape != (3,) or not np.isfinite(d).all():
        raise ValueError("Raio solar inválido")
    for i, j, k in mesh.triangles:
        v0, v1, v2 = xyz[[i, j, k]]
        e1 = v1 - v0
        e2 = v2 - v0
        p = np.cross(d, e2)
        det = float(e1 @ p)
        if abs(det) <= 1e-12:
            continue
        inv = 1.0 / det
        todo = np.flatnonzero(~result)
        if len(todo) == 0:
            break
        rel = origins[todo] - v0
        u = (rel @ p) * inv
        q = np.cross(rel, e1)
        v = (q @ d) * inv
        t = (q @ e2) * inv
        hit = (u >= -1e-10) & (v >= -1e-10) & (u + v <= 1 + 1e-10) & (t > 1e-5)
        result[todo] |= hit
    return result
