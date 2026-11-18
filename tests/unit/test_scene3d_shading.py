"""Regressão: alturas a partir da borda, raycast óptico e contrato HSP."""
import math

import numpy as np
import pytest

from core.scene3d_shading import (
    center_height, hourly_direct_loss, module_corners, shade_by_panel,
    validate_scene,
)


def scene(*, obstacles=None, tilt=0, bottom=1, count=1, columns=1,
          length=2, width=2, azimuth=0):
    return {
        "module": {
            "length_m": length, "width_m": width,
            "bottom_height_m": bottom, "tilt_deg": tilt,
            "azimuth_deg": azimuth, "count": count, "columns": columns,
            "gap_m": .2,
        },
        "obstacles": obstacles if obstacles is not None else [],
    }


def wall(height=10, y=3, width=10, x=0):
    return dict(x_m=x, y_m=y, width_m=width, depth_m=.5, height_m=height)


def test_lowest_edge_is_exact_reference():
    data = scene(tilt=30, bottom=.15, length=2)
    vertices = module_corners(data)[0]
    assert np.min(vertices[:, 2]) == pytest.approx(.15)
    assert center_height(.15, 2, 30) == pytest.approx(.65)
    assert np.max(vertices[:, 2]) == pytest.approx(1.15)


def test_portrait_and_landscape_center_height_differs():
    portrait = center_height(.15, 2.278, 15)
    landscape = center_height(.15, 1.134, 15)
    assert portrait > landscape > .15


def test_north_sun_wall_shades_and_south_sun_does_not():
    config = scene(obstacles=[wall()])
    assert hourly_direct_loss(config, [45], [0])[0] == pytest.approx(1.)
    assert hourly_direct_loss(config, [45], [180])[0] == pytest.approx(0.)
    assert hourly_direct_loss(config, [0], [0])[0] == pytest.approx(0.)


def test_no_obstacles_and_low_obstacle_no_shadow():
    assert hourly_direct_loss(scene(), [25, 40], [0, 10]).tolist() == [0, 0]
    assert hourly_direct_loss(scene(obstacles=[wall(height=.5)]),
                              [45], [0])[0] == pytest.approx(0.)


def test_narrow_obstacle_shades_less_than_wide_obstacle():
    narrow = hourly_direct_loss(scene(obstacles=[wall(width=.3)]),
                                [45], [0])[0]
    wide = hourly_direct_loss(scene(obstacles=[wall(width=6)]),
                              [45], [0])[0]
    assert 0 < narrow < wide <= 1.


def test_more_than_one_obstacle_cannot_exceed_full_area():
    config = scene(obstacles=[wall(), wall(height=8, x=1)])
    value = hourly_direct_loss(config, np.array([20, 45, 70]),
                               np.array([0, 0, 0]))
    assert np.all((value >= 0) & (value <= 1))


def test_panels_in_multiple_rows_do_not_change_reference_height():
    data = scene(tilt=20, bottom=.15, count=5, columns=2)
    vertices = module_corners(data)
    assert vertices.shape == (5, 4, 3)
    assert np.min(vertices[:,:,2]) == pytest.approx(.15)
    fractions = shade_by_panel(data, [35, 45], [0, 180])
    assert fractions.shape == (2, 5)


def test_hourly_annual_length_and_night():
    config = scene(obstacles=[wall()])
    result = hourly_direct_loss(config, np.full(8760, 45.),
                                np.full(8760, 180.))
    assert result.shape == (8760,)
    assert not result.any()


@pytest.mark.parametrize("edit", [
    {"module": {"length_m": -1}},
    {"module": {"count": 1.5}},
    {"module": {"columns": 99}},
    {"obstacles": [wall(height=-1)]},
    {"obstacles": [wall(width=0)]},
])
def test_invalid_geometries_fail_explicitly(edit):
    original = scene()
    if "module" in edit:
        original["module"].update(edit["module"])
    else:
        original.update(edit)
    with pytest.raises(ValueError):
        validate_scene(original)


def test_scene_optical_perez_uses_same_hourly_reference():
    pytest.importorskip("pvlib")
    from core.perez_engines.perez_engine_pvlib import PerezEnginePVLib
    from tests.fixtures.hourly_weather import climate_fixture
    weather = climate_fixture(-5.8, -35.2)
    engine = PerezEnginePVLib(
        lat=-5.8, lon=-35.2, inclinacao_deg=0, azimute_deg=0,
        is_bifacial=False, altura_instalacao=1., comprimento_modulo=2.,
        largura_modulo=2.)
    base = engine.calcular_hsp_corrigido_inc_azi(weather)
    shaded = engine.calcular_hsp_corrigido_inc_azi(
        weather, scene3d=scene(obstacles=[wall(height=12)]))
    assert shaded["media"] <= base["media"]
    assert shaded["media_sem_sombra"] == base["media_sem_sombra"]
    assert shaded["hsp_frontal_media"] < base["hsp_frontal_media"]
    assert shaded["sombra_geometria"]["referencia_altura"] == "borda_inferior_do_plano"


def test_reject_poa_geometry_mismatch():
    pytest.importorskip("pvlib")
    from core.perez_engines.perez_engine_pvlib import PerezEnginePVLib
    from tests.fixtures.hourly_weather import climate_fixture
    engine = PerezEnginePVLib(
        lat=-5.8, lon=-35.2, inclinacao_deg=10, azimute_deg=0,
        comprimento_modulo=2, largura_modulo=2)
    with pytest.raises(ValueError, match="Geometria 3D diferente"):
        engine.calcular_hsp_corrigido_inc_azi(
            climate_fixture(-5.8, -35.2), scene3d=scene())
