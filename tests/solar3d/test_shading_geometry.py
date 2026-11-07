"""Analytical reference cases for the F3 geometric shading engine."""
import numpy as np
import pytest

from solar3d.backend.shading import (
    SceneObject, direction_towards_sun, fraction_blocked,
    sample_panel_face, rotation_matrix,
)


def panel(**changes):
    obj = {
        "id": "M01", "name": "Solar module", "kind": "panel",
        "position": {"east": 0, "north": 0, "elevation": 1},
        "width": 2, "height": 0.04, "depth": 2,
        "tilt": 0, "azimuth": 0,
    }
    obj.update(changes)
    return SceneObject.model_validate(obj)


def box(**changes):
    obj = {
        "id": "W01", "name": "Wall", "kind": "obstacle",
        "position": {"east": 0, "north": 2, "elevation": 1.5},
        "width": 4, "height": 3, "depth": .1,
        "tilt": 0, "azimuth": 0,
    }
    obj.update(changes)
    return SceneObject.model_validate(obj)


def test_true_north_and_east_convention():
    assert np.allclose(direction_towards_sun(0, 0), [0, 0, 1], atol=1e-10)
    assert np.allclose(direction_towards_sun(90, 0), [1, 0, 0], atol=1e-10)
    assert np.allclose(direction_towards_sun(10, 90), [0, 1, 0], atol=1e-10)


def test_no_obstacles_and_no_front_direct_at_night():
    mod = panel()
    fraction, mask = fraction_blocked(mod, [mod], direction_towards_sun(0, 55))
    assert fraction == 0
    assert sum(mask) == 0
    assert fraction_blocked(mod, [mod], direction_towards_sun(0, -4)) == (None, None)


def test_wall_blocks_exactly_half_of_horizontal_panel():
    # North-facing ray at 45 degrees intersects north wall at z=1.95.
    # Panel top is y=1.02001, wall top y=3.0.
    # Wall obstructs roughly the panel's northern half (z > -0.03).
    mod = panel()
    fraction, mask = fraction_blocked(
        mod, [mod, box()], direction_towards_sun(0, 45),
        columns=8, rows=8,
    )
    assert fraction == pytest.approx(0.5)
    assert sum(mask) == 32


def test_opposite_azimuth_clears_wall():
    mod = panel()
    fraction, _ = fraction_blocked(
        mod, [mod, box()], direction_towards_sun(180, 45),
        columns=8, rows=8,
    )
    assert fraction == 0


def test_full_occlusion_from_large_overhead_slab():
    mod = panel()
    roof_above = box(position={"east": 0, "north": 0, "elevation": 3},
                     width=8, depth=8, height=0.2)
    fraction, mask = fraction_blocked(
        mod, [mod, roof_above], direction_towards_sun(0, 90),
    )
    assert fraction == 1
    assert all(mask)


def test_rotated_panel_normal_and_front_back():
    mod = panel(tilt=60, azimuth=90)
    _, normal = sample_panel_face(mod, columns=2, rows=2)
    assert normal[0] == pytest.approx(np.sin(np.deg2rad(60)))
    assert normal[1] == pytest.approx(np.cos(np.deg2rad(60)))
    assert normal[2] == pytest.approx(0, abs=1e-10)
    assert np.allclose(rotation_matrix(mod).T @ rotation_matrix(mod),
                       np.eye(3), atol=1e-10)
    assert fraction_blocked(mod, [mod], direction_towards_sun(270, 10)) == (None, None)


def test_shading_is_monotonic_with_additional_occluders():
    mod = panel()
    wall = box()
    overhead = box(id="O2", position={"east": 0, "north": 0, "elevation": 3},
                   width=8, depth=8, height=0.2)
    direct = direction_towards_sun(0, 45)
    f1, _ = fraction_blocked(mod, [mod, wall], direct, rows=8, columns=8)
    f2, _ = fraction_blocked(mod, [mod, wall, overhead], direct, rows=8, columns=8)
    assert f2 >= f1


def test_invalid_dimensions_and_non_finite_numbers_rejected():
    with pytest.raises(ValueError):
        panel(width=-1)
    with pytest.raises(ValueError):
        panel(azimuth=360)
    with pytest.raises(ValueError):
        panel(width=float("nan"))
