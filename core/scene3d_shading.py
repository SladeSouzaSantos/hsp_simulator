"""Modelo de sombreamento geométrico 3D exclusivo do dashboard HSP.

Coordenadas métricas ENU: x=Leste, y=Norte, z=altura. O azimute solar
segue pvlib (0=N, 90=L). A altura informada é a borda MAIS BAIXA do
plano do módulo, não seu centro. A sombra é amostrada na face do módulo
e afeta somente o POA direto; não estima perdas elétricas.
"""
from __future__ import annotations

import math
import re
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


def _identifier(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError(f"{name} deve possuir ID alfanumérico estável")
    return value


def validate_scene(scene: Mapping) -> dict:
    """Valida a cena óptica; MPPTs são grupos VISUAIS, não circuitos elétricos.

    Mantém compatibilidade com cenas antigas (count/columns sem panels).
    Posições explícitas são ENU, em metros; os arrastes só alteram X e Y.
    """
    if not isinstance(scene, Mapping) or not isinstance(scene.get("module"), Mapping):
        raise ValueError("Cena 3D exige configuração de módulo")
    m = scene["module"]
    module = {
        "length_m": _number(m.get("length_m"), "Comprimento", 0.1, 10),
        "width_m": _number(m.get("width_m"), "Largura", 0.1, 10),
        "bottom_height_m": _number(m.get("bottom_height_m"), "Borda inferior", 0, 500),
        "tilt_deg": _number(m.get("tilt_deg"), "Inclinação", 0, 90),
        "azimuth_deg": _number(m.get("azimuth_deg"), "Azimute", 0, 360),
        "count": int(_number(m.get("count", 1), "Quantidade", 1, 48)),
        "columns": int(_number(m.get("columns", 1), "Colunas", 1, 48)),
        "gap_m": _number(m.get("gap_m", 0.15), "Espaçamento", 0, 10),
    }
    if module["columns"] > module["count"]:
        raise ValueError("Colunas não podem exceder número de módulos")
    for field in ("count", "columns"):
        if float(m.get(field, 1)) != module[field]:
            raise ValueError(f"{field} deve ser inteiro")

    raw_groups = scene.get("groups", [{"id": "mppt-1", "name": "MPPT 1"}])
    if not isinstance(raw_groups, list) or not 1 <= len(raw_groups) <= 16:
        raise ValueError("Cena precisa de 1 a 16 grupos MPPT")
    groups = []
    for idx, raw in enumerate(raw_groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Grupo {idx + 1} inválido")
        ident = _identifier(raw.get("id"), "ID de MPPT")
        label = raw.get("name", ident)
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80:
            raise ValueError("Nome de MPPT inválido")
        groups.append({"id": ident, "name": label.strip()})
    group_ids = {g["id"] for g in groups}
    if len(group_ids) != len(groups):
        raise ValueError("IDs de MPPT duplicados")

    raw_panels = scene.get("panels")
    panels = []
    if raw_panels is None:
        # Layout legado: centralizado, em múltiplas fileiras, sem deslocamentos.
        az = math.radians(module["azimuth_deg"])
        beta = math.radians(module["tilt_deg"])
        across = (math.cos(az), -math.sin(az))
        side_pitch = module["width_m"] + module["gap_m"]
        row_pitch = module["length_m"] * math.cos(beta) + module["gap_m"]
        for idx in range(module["count"]):
            row, col = divmod(idx, module["columns"])
            side = (col - (module["columns"] - 1) / 2) * side_pitch
            panels.append({
                "id": f"pv-{idx + 1}", "mppt_id": groups[0]["id"],
                "x_m": side * across[0] - row * row_pitch * math.sin(az),
                "y_m": side * across[1] - row * row_pitch * math.cos(az),
                "bottom_height_m": module["bottom_height_m"],
            })
    else:
        if not isinstance(raw_panels, list) or not 1 <= len(raw_panels) <= 48:
            raise ValueError("Cena permite de 1 a 48 placas")
        for idx, raw in enumerate(raw_panels):
            if not isinstance(raw, Mapping):
                raise ValueError(f"Placa {idx + 1} inválida")
            mppt = _identifier(raw.get("mppt_id"), "Grupo MPPT da placa")
            if mppt not in group_ids:
                raise ValueError(f"Placa {idx + 1} aponta para MPPT inexistente")
            panels.append({
                "id": _identifier(raw.get("id"), "ID da placa"),
                "mppt_id": mppt,
                "x_m": _number(raw.get("x_m"), "X da placa", -1000, 1000),
                "y_m": _number(raw.get("y_m"), "Y da placa", -1000, 1000),
                "bottom_height_m": _number(
                    raw.get("bottom_height_m", module["bottom_height_m"]),
                    "Altura inferior da placa", 0, 500),
            })
        module["count"] = len(panels)
        module["columns"] = min(module["columns"], len(panels))
    if len({p["id"] for p in panels}) != len(panels):
        raise ValueError("IDs de placas duplicados")

    raw_obstacles = scene.get("obstacles", [])
    if not isinstance(raw_obstacles, list) or len(raw_obstacles) > 32:
        raise ValueError("Cena permite no máximo 32 obstáculos")
    obstacles = []
    for idx, raw in enumerate(raw_obstacles):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Obstáculo {idx + 1} inválido")
        obstacles.append({
            "id": _identifier(raw.get("id", f"obs-{idx + 1}"),
                              "ID do obstáculo"),
            "x_m": _number(raw.get("x_m"), "X obstáculo", -1000, 1000),
            "y_m": _number(raw.get("y_m"), "Y obstáculo", -1000, 1000),
            "width_m": _number(raw.get("width_m"), "Largura obstáculo", 0.01, 1000),
            "depth_m": _number(raw.get("depth_m"), "Profundidade obstáculo", 0.01, 1000),
            "height_m": _number(raw.get("height_m"), "Altura obstáculo", 0.01, 500),
        })
    if len({o["id"] for o in obstacles}) != len(obstacles):
        raise ValueError("IDs de obstáculos duplicados")
    return {"module": module, "panels": panels, "groups": groups,
            "obstacles": obstacles}


def center_height(bottom_height_m, length_m, tilt_deg):
    """Altura do centro do PLANO (sem espessura) a partir da borda baixa."""
    return _number(bottom_height_m, "Borda inferior", 0) + (
        _number(length_m, "Comprimento", 0.1) * math.sin(math.radians(
            _number(tilt_deg, "Inclinação", 0, 90))) / 2)


def module_corners(scene):
    """Vértices (n,4,3) ENU, com altura inferior própria de cada placa."""
    return _panel_points(validate_scene(scene), rows=2, cols=2, corners=True)


def _panel_points(clean, rows=5, cols=5, corners=False):
    m = clean["module"]
    az = math.radians(m["azimuth_deg"])
    beta = math.radians(m["tilt_deg"])
    length, width = m["length_m"], m["width_m"]
    along = np.array([-math.sin(az) * math.cos(beta),
                      -math.cos(az) * math.cos(beta), math.sin(beta)])
    across = np.array([math.cos(az), -math.sin(az), 0.])
    if corners:
        s_values = np.array([-.5, -.5, .5, .5]) * length
        w_values = np.array([-.5, .5, .5, -.5]) * width
    else:
        ss = (np.arange(rows) + .5) / rows - .5
        ww = (np.arange(cols) + .5) / cols - .5
        s_values, w_values = np.meshgrid(ss * length, ww * width, indexing="ij")
        s_values, w_values = s_values.ravel(), w_values.ravel()
    points = []
    for panel in clean["panels"]:
        center = np.array([
            panel["x_m"], panel["y_m"],
            center_height(panel["bottom_height_m"], length, m["tilt_deg"]),
        ])
        points.append(center + s_values[:, None] * along +
                      w_values[:, None] * across)
    return np.stack(points, axis=0)


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
    points = _panel_points(clean, rows=rows, cols=cols)
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
