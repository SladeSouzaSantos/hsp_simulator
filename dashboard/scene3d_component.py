"""Bridge bidirecional do editor 3D com o estado da sessão Streamlit.

O componente envia um snapshot válido após soltar o mouse. Nenhum dado
da cena é enviado à API HTTP do HSP Simulator.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_ASSET_DIR = Path(__file__).resolve().parent / "components" / "solar3d_drag"
_BUNDLE = _ASSET_DIR / "editor.bundle.js"

_editor = components.declare_component(
    "hsp_solar3d_drag",
    path=str(_ASSET_DIR),
)


def interactive_scene(scene, elevation_deg, azimuth_deg, fractions, key="hsp3d_editor"):
    """Retorna None, ou {'revision': int, 'scene': dict, 'selection': list}."""
    if not _BUNDLE.is_file():
        st.error(
            "Os arquivos do visualizador 3D não foram compilados. "
            "Instale Node.js e execute 'npm install' e 'npm run build' "
            "em dashboard/components/solar3d_drag/. "
            "No Docker, o bundle é gerado automaticamente no build."
        )
        return None
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
