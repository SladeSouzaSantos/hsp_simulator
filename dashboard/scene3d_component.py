"""Bridge bidirecional do editor 3D com o estado da sessão Streamlit.

O componente envia um snapshot válido após soltar o mouse. Nenhum dado
da cena é enviado à API HTTP do HSP Simulator.
"""
from pathlib import Path

import streamlit.components.v1 as components

_editor = components.declare_component(
    "hsp_solar3d_drag",
    path=str(Path(__file__).parent / "components" / "solar3d_drag"),
)


def interactive_scene(scene, elevation_deg, azimuth_deg, fractions, key="hsp3d_editor"):
    """Retorna None, ou {'revision': int, 'scene': dict, 'selection': list}."""
    return _editor(
        scene=scene,
        sun={
            "elevation_deg": float(elevation_deg),
            "azimuth_deg": float(azimuth_deg),
        },
        fractions=[float(v) for v in fractions],
        key=key,
        default=None,
    )
