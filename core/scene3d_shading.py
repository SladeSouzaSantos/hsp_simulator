"""Modelo de sombreamento geométrico 3D exclusivo do dashboard HSP.

Coordenadas métricas ENU: x=Leste, y=Norte, z=altura. O azimute solar
segue pvlib (0=N, 90=L). A altura informada é a borda MAIS BAIXA do
plano do módulo, não seu centro. A sombra é amostrada na face do módulo
e afeta somente o POA direto; não estima perdas elétricas.
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np


def _number(value, name, low=None, high=None):
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser numérico") from exc
    if not math.isfinite(n) or (low is not None and n < low) or (high is not None and n > high):
        raise ValueError(f"{name} está fora dos limites permitidos")
    return n


def validate_scene(scene: Mapping) -> dict:
    """Validação estrita; não reinterpreta campos da API HSP legada."""
    if not isinstance(scene, Mapping) or not isinstance(scene.get("module"), Mapping):
        raise ValueError("Cena 3D exige configuração de módulo")
    m = scene["module"]
    module = {
        "length_m": _number(m.get("length_m"), "Comprimento", 0.1, 10),
        "width_m": _number(m.get("width_m"), "Largura", 0.1, 10),
        "bottom_height_m": _number(m.get("bottom_height_m"), "Borda inferior", 0, 500),
        "tilt_deg": _number(m.get("tilt_deg"), "Inclinação", 0, 90),
        "azimuth_deg": _number(m.get("azimuth_deg"), "Azimute", 0, 360),
        "count": int(_number(m.get("count", 1), "Quantidade", 1, 24)),
        "columns": int(_number(m.get("columns", 1), "Colunas", 1, 24)),
        "gap_m": _number(m.get("gap_m", 0.15), "Espaçamento", 0, 10),
    }
    if module["columns"] > module["count"]:
        raise ValueError("Colunas não podem exceder número de módulos")
    for field in ("count", "columns"):
        if float(m.get(field, 1)) != module[field]:
            raise ValueError(f"{field} deve ser inteiro")
    raw_obstacles = scene.get("obstacles", [])
    if not isinstance(raw_obstacles, list) or len(raw_obstacles) > 12:
        raise ValueError("Cena permite no máximo 12 obstáculos")
    obstacles = []
    for i, raw in enumerate(raw_obstacles):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Obstáculo {i+1} inválido")
        obstacles.append({
            "x_m": _number(raw.get("x_m"), "X obstáculo", -1000, 1000),
            "y_m": _number(raw.get("y_m"), "Y obstáculo", -1000, 1000),
            "width_m": _number(raw.get("width_m"), "Largura obstáculo", 0.01, 1000),
            "depth_m": _number(raw.get("depth_m"), "Profundidade obstáculo", 0.01, 1000),
            "height_m": _number(raw.get("height_m"), "Altura obstáculo", 0.01, 500),
        })
    return {"module": module, "obstacles": obstacles}


def center_height(bottom_height_m, length_m, tilt_deg):
    """Altura do centro do PLANO (sem espessura) a partir da borda baixa."""
    return _number(bottom_height_m, "Borda inferior", 0) + (
        _number(length_m, "Comprimento", 0.1) * math.sin(math.radians(
            _number(tilt_deg, "Inclinação", 0, 90))) / 2)


def module_corners(scene):
    """Vértices (n, 4, 3) na ordem da face: (Leste, Norte, Cima)."""
    return _panel_points(validate_scene(scene)["module"], rows=2, cols=2,
                         corners=True)


def _panel_points(m, rows=5, cols=5, corners=False):
    az = math.radians(m["azimuth_deg"])
    beta = math.radians(m["tilt_deg"])
    length, width = m["length_m"], m["width_m"]
    # s positivo = borda elevada, voltada contra o azimute frontal.
    along = np.array([-math.sin(az) * math.cos(beta),
                      -math.cos(az) * math.cos(beta), math.sin(beta)])
    across = np.array([math.cos(az), -math.sin(az), 0.])
    front = np.array([math.sin(az), math.cos(az), 0.])
    if corners:
        s_values = np.array([-.5, -.5, .5, .5]) * length
        w_values = np.array([-.5, .5, .5, -.5]) * width
    else:
        ss = (np.arange(rows) + .5) / rows - .5
        ww = (np.arange(cols) + .5) / cols - .5
        s_values, w_values = np.meshgrid(ss * length, ww * width, indexing="ij")
        s_values, w_values = s_values.ravel(), w_values.ravel()
    side_pitch = width + m["gap_m"]
    row_pitch = length * math.cos(beta) + m["gap_m"]
    base_center = np.array([0., 0., center_height(
        m["bottom_height_m"], length, m["tilt_deg"])])
    panels = []
    for index in range(m["count"]):
        row, col = divmod(index, m["columns"])
        pos = base_center + ((col - (m["columns"] - 1) / 2.) * side_pitch * across
                             - row * row_pitch * front)
        panels.append(pos + s_values[:, None] * along + w_values[:, None] * across)
    return np.stack(panels, axis=0)


def _ray_blocked(points, directions, obstacles):
    """Intersecção raio/AABB por slab, vetorizada em instantes/amostras."""
    n_times, n_points = len(directions), len(points)
    hit = np.zeros((n_times, n_points), dtype=bool)
    if not obstacles:
        return hit
    for obs in obstacles:
        low = np.array([obs["x_m"] - obs["width_m"] / 2,
                        obs["y_m"] - obs["depth_m"] / 2, 0.])
        high = np.array([obs["x_m"] + obs["width_m"] / 2,
                         obs["y_m"] + obs["depth_m"] / 2, obs["height_m"]])
        near = np.full((n_times, n_points), -np.inf)
        far = np.full((n_times, n_points), np.inf)
        valid = np.ones((n_times, n_points), dtype=bool)
        for axis in range(3):
            ray = directions[:, axis, None]
            is_parallel = np.abs(ray) < 1e-10
            outside = (points[:, axis] < low[axis]) | (points[:, axis] > high[axis])
            valid &= ~(is_parallel & outside[None, :])
            divisor = np.where(is_parallel, 1., ray)
            a = (low[axis] - points[None, :, axis]) / divisor
            b = (high[axis] - points[None, :, axis]) / divisor
            near = np.maximum(near, np.where(is_parallel, -np.inf, np.minimum(a, b)))
            far = np.minimum(far, np.where(is_parallel, np.inf, np.maximum(a, b)))
        hit |= valid & (far >= np.maximum(near, 1e-7))
    return hit


def shade_by_panel(scene, solar_elevation_deg, solar_azimuth_deg, rows=5, cols=5):
    """Retorna matriz (horas, placas) das frações frontalmente bloqueadas.

    Aproximação espacial por amostras centrais; estimativas variam com a
    resolução. A mesma cena e a mesma amostragem são usadas em toda a série.
    """
    clean = validate_scene(scene)
    if not (1 <= rows <= 16 and 1 <= cols <= 16):
        raise ValueError("Grade de amostragem inválida")
    alt, azi = np.broadcast_arrays(np.asarray(solar_elevation_deg, dtype=float),
                                   np.asarray(solar_azimuth_deg, dtype=float))
    if not np.isfinite(alt).all() or not np.isfinite(azi).all():
        raise ValueError("Posição solar não finita")
    flat_alt, flat_azi = alt.ravel(), azi.ravel()
    points = _panel_points(clean["module"], rows=rows, cols=cols)
    n_panels, n_points = points.shape[:2]
    samples = points.reshape((-1, 3))
    out = np.zeros((len(flat_alt), n_panels), dtype=float)
    if not clean["obstacles"]:
        return out.reshape(alt.shape + (n_panels,))
    # Blocos mantêm uso de memória constante para 8760/8784 horas.
    for start in range(0, len(flat_alt), 168):
        stop = min(start + 168, len(flat_alt))
        elevation = flat_alt[start:stop]
        azimuth = flat_azi[start:stop]
        er, ar = np.deg2rad(elevation), np.deg2rad(azimuth)
        directions = np.stack([
            np.cos(er) * np.sin(ar),
            np.cos(er) * np.cos(ar),
            np.sin(er),
        ], axis=1)
        blocked = _ray_blocked(samples, directions, clean["obstacles"])
        blocked[elevation <= 0, :] = False
        out[start:stop] = blocked.reshape((stop-start, n_panels, n_points)).mean(axis=2)
    return out.reshape(alt.shape + (n_panels,))


def hourly_direct_loss(scene, solar_elevation_deg, solar_azimuth_deg, rows=5, cols=5):
    """Fração média [0,1] da área frontal bloqueada entre as placas da cena."""
    return shade_by_panel(scene, solar_elevation_deg, solar_azimuth_deg, rows, cols).mean(axis=-1)
