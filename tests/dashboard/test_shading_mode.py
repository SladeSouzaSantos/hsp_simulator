"""Modo sem sombra não cria o editor nem modifica entradas do HSP."""
from unittest.mock import Mock

from dashboard.shading_mode import optional_shading_scene


def test_3d_off_by_default_does_not_construct_scene():
    renderer = Mock(side_effect=AssertionError("Editor não deve ser construído"))
    assert optional_shading_scene(False, renderer, 1, 2, azimuth=90) is None
    renderer.assert_not_called()


def test_enabling_3d_constructs_scene_with_original_parameters():
    scene = {"module": {"length_m": 2.278}, "obstacles": []}
    renderer = Mock(return_value=scene)
    result = optional_shading_scene(True, renderer, -5.8, -35.2, 15)
    assert result is scene
    renderer.assert_called_once_with(-5.8, -35.2, 15)


def test_disabling_after_enabling_does_not_reuse_old_shadows():
    scene = {"obstacles": [{"height_m": 3}]}
    renderer = Mock(return_value=scene)
    assert optional_shading_scene(True, renderer) == scene
    assert optional_shading_scene(False, renderer) is None
    assert renderer.call_count == 1
