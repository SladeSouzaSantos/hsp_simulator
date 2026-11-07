import numpy as np
import pytest
from solar3d.backend.mesh import MeshObstacle, ray_mesh_mask
from solar3d.backend.shading import SceneObject, direction_towards_sun, fraction_blocked


def mesh():
    return MeshObstacle(
        id="roof", name="Cobertura triangular",
        vertices=[(-2, 2, -2), (2, 2, -2), (2, 2, 2), (-2, 2, 2)],
        triangles=[(0, 1, 2), (0, 2, 3)],
    )


def panel():
    return SceneObject(
        id="p1", name="PV", kind="panel",
        position={"east": 0, "north": 0, "elevation": 1},
        width=1, depth=1, height=0.05, azimuth=0, tilt=0,
    )


def test_two_triangles_block_overhead_sun():
    p = panel()
    direction = direction_towards_sun(90, 90)
    fraction, mask = fraction_blocked(p, [p], direction, columns=4, rows=4, meshes=[mesh()])
    assert fraction == 1
    assert sum(mask) == 16


def test_mesh_do_not_block_from_wrong_direction():
    origins = np.asarray([[0, 1, 0]], dtype=float)
    assert ray_mesh_mask(origins, np.asarray([0, -1, 0]), mesh()).tolist() == [False]


def test_mesh_does_not_block_clear_sun_from_low_angle():
    p = panel()
    direction = direction_towards_sun(90, 10)
    fraction, _ = fraction_blocked(p, [p], direction, columns=4, rows=4, meshes=[mesh()])
    assert fraction == 0


def test_bad_triangles_are_rejected():
    with pytest.raises(ValueError):
        MeshObstacle(id="bad", name="bad",
                     vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
                     triangles=[(0, 1, 9)])
    with pytest.raises(ValueError):
        MeshObstacle(id="flat", name="bad",
                     vertices=[(0, 0, 0), (1, 0, 0), (2, 0, 0)],
                     triangles=[(0, 1, 2)])
