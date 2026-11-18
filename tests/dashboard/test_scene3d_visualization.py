"""Prévia 3D é puramente local e reproduzível, sem consulta meteorológica."""
from datetime import date

import numpy as np
import pytest

pytest.importorskip("plotly")
pytest.importorskip("streamlit")

from dashboard.scene3d import make_scene_figure, preview_sun


def example_scene():
    return {
        "module": {
            "length_m": 2.278, "width_m": 1.134, "tilt_deg": 15,
            "azimuth_deg": 0, "bottom_height_m": .15,
            "count": 2, "columns": 2, "gap_m": .15,
        },
        "obstacles": [
            dict(x_m=0, y_m=3, width_m=4, depth_m=.5, height_m=3),
        ],
    }


def test_preview_scene_with_sun_and_obstacle():
    fig, ratios = make_scene_figure(example_scene(), 35, 0)
    assert ratios.shape == (2,)
    assert np.all((ratios >= 0) & (ratios <= 1))
    assert any(trace.name == "Solo" for trace in fig.data)
    assert any(trace.name == "Obstáculo 1" for trace in fig.data)
    assert any(trace.name == "Direção solar" for trace in fig.data)


def test_night_preview_has_no_sun():
    fig, ratios = make_scene_figure(example_scene(), -15, 90)
    assert not ratios.any()
    assert not any(trace.name == "Direção solar" for trace in fig.data)


def test_solar_preview_explicit_timezone():
    elevation, azimuth = preview_sun(-5.79448, -35.21101,
                                     date(2026, 6, 21), 12., -3)
    assert -90 <= elevation <= 90
    assert 0 <= azimuth <= 360
    assert elevation > 0
