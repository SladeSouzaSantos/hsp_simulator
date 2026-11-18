"""Contrato de edição geométrica: placas individuais, grupos MPPT e XY only."""
from copy import deepcopy
import math
import numpy as np
import pytest

from core.scene3d_shading import (
    validate_scene, module_corners, shade_by_panel, hourly_direct_loss,
)
from dashboard.scene3d import _initial_scene, _apply_drag


def sample_scene():
    scene = _initial_scene(15, 0, .15, 2., 1.)
    scene["groups"].append({"id": "mppt-2", "name": "MPPT 2"})
    scene["panels"].extend([
        {"id": "pv-2", "mppt_id": "mppt-1", "x_m": 1.2, "y_m": 0,
         "bottom_height_m": .15},
        {"id": "pv-3", "mppt_id": "mppt-2", "x_m": 8, "y_m": 0,
         "bottom_height_m": 2.},
    ])
    scene["module"]["count"] = 3
    scene["module"]["columns"] = 2
    return scene


def test_group_assignment_and_positions_are_preserved_by_validation():
    clean = validate_scene(sample_scene())
    assert [p["id"] for p in clean["panels"]] == ["pv-1", "pv-2", "pv-3"]
    assert clean["panels"][1]["mppt_id"] == "mppt-1"
    assert clean["panels"][2]["mppt_id"] == "mppt-2"
    corners = module_corners(clean)
    assert corners.shape == (3, 4, 3)
    assert corners[0, 0, 0] != pytest.approx(corners[1, 0, 0])
    assert corners[0, :, 2].min() == pytest.approx(.15)
    assert corners[2, :, 2].min() == pytest.approx(2.)


def test_individual_panel_shift_affects_shadow_but_not_other_panel():
    sc = sample_scene()
    sc["module"]["tilt_deg"] = 0
    sc["panels"][0]["x_m"] = 0
    sc["panels"][0]["y_m"] = 0
    sc["panels"][1]["x_m"] = 1.2
    sc["panels"][1]["y_m"] = 0
    sc["panels"][2]["x_m"] = 10
    sc["panels"][2]["y_m"] = 0
    sc["obstacles"][0]["height_m"] = 10
    sc["obstacles"][0]["width_m"] = 2.
    first = shade_by_panel(sc, [45], [0], rows=7, cols=7)[0]
    assert first[0] > 0.
    assert first[2] == 0.
    sc["panels"][0]["x_m"] = 100
    moved = shade_by_panel(sc, [45], [0], rows=7, cols=7)[0]
    assert moved[0] == 0.
    assert moved[1] == pytest.approx(first[1])


def test_mppt_labels_do_not_affect_radiometric_results():
    scene = sample_scene()
    before = hourly_direct_loss(scene, [20, 45], [0, 0])
    scene["panels"][2]["mppt_id"] = "mppt-1"
    scene["groups"][1]["name"] = "Outro grupo"
    after = hourly_direct_loss(scene, [20, 45], [0, 0])
    assert np.allclose(before, after)


def test_drag_import_changes_only_xy_preserves_z_and_mppt():
    initial = validate_scene(sample_scene())
    incoming = deepcopy(initial)
    incoming["panels"][0].update({
        "x_m": 7.25, "y_m": -4.5,
        "bottom_height_m": 155, "mppt_id": "mppt-2",
    })
    incoming["obstacles"][0].update({
        "x_m": 11, "y_m": 4, "height_m": 500,
    })
    changed = _apply_drag(initial, {"scene": incoming})
    assert changed
    assert initial["panels"][0]["x_m"] == pytest.approx(7.25)
    assert initial["panels"][0]["y_m"] == pytest.approx(-4.5)
    assert initial["panels"][0]["bottom_height_m"] == pytest.approx(.15)
    assert initial["panels"][0]["mppt_id"] == "mppt-1"
    assert initial["obstacles"][0]["height_m"] == pytest.approx(3)
    assert initial["obstacles"][0]["x_m"] == pytest.approx(11)


def test_stale_client_snapshot_rejected_after_panel_deleted():
    initial = validate_scene(sample_scene())
    stale = deepcopy(initial)
    initial["panels"].pop()
    assert not _apply_drag(initial, {"scene": stale})


def test_legacy_layout_has_original_physical_spacing():
    s = sample_scene()
    del s["panels"]
    del s["groups"]
    old = validate_scene(s)
    m = old["module"]
    pitch = m["length_m"] * math.cos(math.radians(15)) + m["gap_m"]
    assert old["panels"][2]["y_m"] == pytest.approx(-pitch)
    assert len(module_corners(s)) == m["count"]


def test_more_obstacles_supported_and_bad_groups_blocked():
    s = sample_scene()
    s["obstacles"] = [
        {"id": f"obs-{i}", "x_m": i, "y_m": 3, "width_m": 2.,
         "depth_m": .5, "height_m": 3.}
        for i in range(1, 33)
    ]
    assert len(validate_scene(s)["obstacles"]) == 32
    s["obstacles"].append({
        "id": "obs-33", "x_m": 33, "y_m": 3, "width_m": 2.,
        "depth_m": .5, "height_m": 3.,
    })
    with pytest.raises(ValueError, match="32 obstáculos"):
        validate_scene(s)
    s = sample_scene()
    s["panels"][0]["mppt_id"] = "mppt-desconhecido"
    with pytest.raises(ValueError, match="MPPT inexistente"):
        validate_scene(s)
