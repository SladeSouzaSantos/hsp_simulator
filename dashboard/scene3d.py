"""Editor/visualizador 3D do dashboard Streamlit (apenas perdas ópticas).

Plotly usa WebGL e permite girar, aproximar e pan. Posições dos obstáculos
são editadas por campos métricos; não são redesenhadas automaticamente
no CAD nem alteram string, MPPT ou energia DC/AC.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.scene3d_shading import (
    center_height, module_corners, shade_by_panel, validate_scene,
)
from dashboard.scene3d_component import interactive_scene


def _box_vertices(obs):
    x, y, w, d, h = (obs[k] for k in
                     ("x_m", "y_m", "width_m", "depth_m", "height_m"))
    x0, x1, y0, y1 = x-w/2, x+w/2, y-d/2, y+d/2
    return np.array([
        [x0,y0,0], [x1,y0,0], [x1,y1,0], [x0,y1,0],
        [x0,y0,h], [x1,y0,h], [x1,y1,h], [x0,y1,h],
    ], dtype=float)


def _hull(points):
    """Casco convexo 2D para desenhar a projeção no solo, sem SciPy."""
    pts = sorted(set(tuple(v) for v in points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    low, high = [], []
    for p in pts:
        while len(low) >= 2 and cross(low[-2], low[-1], p) <= 0:
            low.pop()
        low.append(p)
    for p in reversed(pts):
        while len(high) >= 2 and cross(high[-2], high[-1], p) <= 0:
            high.pop()
        high.append(p)
    return low[:-1] + high[:-1]


def _mesh(fig, vertices, triangles, color, opacity, name, hover):
    x, y, z = np.asarray(vertices).T
    i, j, k = np.asarray(triangles, dtype=int).T
    fig.add_trace(go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k, color=color,
        opacity=opacity, flatshading=True, name=name,
        hovertemplate=hover + "<extra></extra>", showscale=False,
    ))


def preview_sun(latitude, longitude, day, local_hour, utc_offset):
    """Efeméride pvlib com offset explícito, nunca fuso implícito do servidor."""
    from pvlib.location import Location
    hr = int(local_hour)
    minute = int(round((local_hour-hr)*60))
    local = datetime.combine(day, time(hr, minute),
                             tzinfo=timezone(timedelta(hours=utc_offset)))
    instant = pd.DatetimeIndex([pd.Timestamp(local).tz_convert("UTC")])
    solar = Location(latitude, longitude, tz="UTC").get_solarposition(instant)
    return (float(solar["apparent_elevation"].iloc[0]),
            float(solar["azimuth"].iloc[0]))


def make_scene_figure(scene, elevation, solar_azimuth):
    clean = validate_scene(scene)
    corners = module_corners(clean)
    shade = shade_by_panel(clean, [elevation], [solar_azimuth],
                           rows=8, cols=6)[0]
    fig = go.Figure()
    spots = [corners.reshape(-1, 3)]
    boxes = [_box_vertices(ob) for ob in clean["obstacles"]]
    spots.extend(boxes)
    merged = np.concatenate(spots)
    extent = max(4., float(np.max(np.abs(merged[:, :2]))) + 2.)
    ground = [[-extent,-extent,0], [extent,-extent,0],
              [extent,extent,0], [-extent,extent,0]]
    _mesh(fig, ground, [[0,1,2], [0,2,3]],
          "#d7e8dc", .35, "Solo", "Plano do solo")
    for index, (vertices, masked) in enumerate(zip(corners, shade)):
        _mesh(fig, vertices, [[0,1,2],[0,2,3]],
              "#ec9d2b" if masked > .1 else "#185c91", .94,
              f"Módulo {index+1}", f"Módulo {index+1}: {masked*100:.1f}% de área bloqueada")
        path = np.vstack([vertices, vertices[:1]])
        fig.add_trace(go.Scatter3d(
            x=path[:,0], y=path[:,1], z=path[:,2], mode="lines",
            line=dict(color="#123450", width=5), hoverinfo="skip", showlegend=False,
        ))
    faces = [
        [0,2,1],[0,3,2],[4,5,6],[4,6,7],
        [0,1,5],[0,5,4],[1,2,6],[1,6,5],
        [2,3,7],[2,7,6],[3,0,4],[3,4,7],
    ]
    for index, vertices in enumerate(boxes):
        _mesh(fig, vertices, faces, "#828e9b", .88,
              f"Obstáculo {index+1}", f"Obstáculo {index+1}")
    if elevation > 0:
        er, ar = np.deg2rad([elevation, solar_azimuth])
        direction = np.array([
            np.cos(er) * np.sin(ar),
            np.cos(er) * np.cos(ar),
            np.sin(er),
        ])
        for vertices in boxes:
            # Apenas visual: limitação do alcance desenhado a 25m, para
            # não destruir o enquadramento com Sol muito baixo.
            travel = np.minimum(vertices[:,2] / max(direction[2], 1e-8), 25.)
            projected = vertices[:,:2] - travel[:,None] * direction[:2]
            hull = _hull(projected)
            if len(hull) >= 3:
                _mesh(fig, [[x,y,.015] for x,y in hull],
                      [[0,j,j+1] for j in range(1,len(hull)-1)],
                      "#485360", .28, "Sombra projetada",
                      "Projeção visual da sombra sobre o terreno")
        p = corners[0].mean(axis=0)
        tip = p + direction * 4
        fig.add_trace(go.Scatter3d(
            x=[p[0],tip[0]], y=[p[1],tip[1]], z=[p[2],tip[2]],
            mode="lines+markers", line=dict(color="#f5b217",width=8),
            marker=dict(color="#f5b217",size=[2,8]), name="Direção solar",
            hovertemplate="Direção do Sol<extra></extra>",
        ))
    fig.update_layout(
        height=540, margin=dict(l=0,r=0,t=8,b=0),
        scene=dict(
            xaxis=dict(title="Leste / Oeste (m)", backgroundcolor="#eef4f5"),
            yaxis=dict(title="Norte / Sul (m)", backgroundcolor="#eef4f5"),
            zaxis=dict(title="Altura (m)", rangemode="tozero"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.4,y=-1.6,z=1.15)),
        ),
        legend=dict(orientation="h", y=-.05),
    )
    return fig, shade


def _initial_scene(tilt, azimuth, bottom_height, panel_length, panel_width):
    return {
        "module": {
            "length_m": panel_length, "width_m": panel_width,
            "bottom_height_m": bottom_height, "tilt_deg": tilt,
            "azimuth_deg": azimuth, "count": 1, "columns": 1,
            "gap_m": 0.15,
        },
        "groups": [{"id": "mppt-1", "name": "MPPT 1"}],
        "panels": [{
            "id": "pv-1", "mppt_id": "mppt-1", "x_m": 0., "y_m": 0.,
            "bottom_height_m": bottom_height,
        }],
        "obstacles": [{
            "id": "obs-1", "x_m": 0., "y_m": 3., "width_m": 3.,
            "depth_m": .5, "height_m": 3.,
        }],
    }


def _add_panel(scene, group_id):
    if len(scene["panels"]) >= 48:
        raise ValueError("O editor suporta no máximo 48 placas")
    number = st.session_state["hsp3d_next_panel_id"]
    st.session_state["hsp3d_next_panel_id"] += 1
    preceding = [p for p in scene["panels"] if p["mppt_id"] == group_id]
    last = preceding[-1] if preceding else None
    scene["panels"].append({
        "id": f"pv-{number}", "mppt_id": group_id,
        "x_m": round((last["x_m"] if last else 0.) +
                     scene["module"]["width_m"] + scene["module"]["gap_m"], 3),
        "y_m": last["y_m"] if last else 0.,
        "bottom_height_m": scene["module"]["bottom_height_m"],
    })


def _apply_drag(scene, incoming):
    """Copiar somente XY com IDs estáveis. JS não controla z, MPPT ou dimensões.

    Snapshots antigos (ex. após remover uma placa) são rejeitados; o
    Python é a fonte de verdade para os campos de engenharia.
    """
    if not isinstance(incoming, dict) or not isinstance(incoming.get("scene"), dict):
        return False
    candidate = validate_scene(incoming["scene"])
    if ({p["id"] for p in scene["panels"]} != {p["id"] for p in candidate["panels"]} or
        {o["id"] for o in scene["obstacles"]} !=
            {o["id"] for o in candidate["obstacles"]}):
        return False
    changed = False
    for key in ("panels", "obstacles"):
        from_client = {p["id"]: p for p in candidate[key]}
        for original in scene[key]:
            updated = from_client[original["id"]]
            for field in ("x_m", "y_m"):
                if original[field] != updated[field]:
                    original[field] = updated[field]
                    changed = True
    return changed


def _group_controls(scene):
    st.markdown("#### Placas e grupos MPPT")
    st.caption("MPPT é uma etiqueta de agrupamento geométrico; não se "
               "calculam curvas elétricas, corrente de string ou perdas DC/AC.")
    a, b = st.columns(2)
    if a.button("Adicionar grupo MPPT", disabled=len(scene["groups"]) >= 16,
                key="hsp3d_add_mppt"):
        number = st.session_state["hsp3d_next_mppt_id"]
        st.session_state["hsp3d_next_mppt_id"] += 1
        scene["groups"].append({"id": f"mppt-{number}", "name": f"MPPT {number}"})
        st.rerun()
    if b.button("Aplicar altura padrão a todas as placas",key="hsp3d_apply_height"):
        for panel in scene["panels"]:
            panel["bottom_height_m"] = scene["module"]["bottom_height_m"]
            st.session_state[f"hsp3d_z_{panel['id']}"] = panel["bottom_height_m"]
        st.rerun()

    for group in list(scene["groups"]):
        grouped = [p for p in scene["panels"] if p["mppt_id"] == group["id"]]
        with st.expander(f"{group['name']} · {len(grouped)} placa(s)",
                         expanded=(len(scene["groups"]) == 1)):
            name = st.text_input("Nome do grupo", group["name"],
                                 key=f"hsp3d_name_{group['id']}",max_chars=80)
            if name.strip():
                group["name"] = name.strip()
            left,right = st.columns(2)
            if left.button("Adicionar placa neste MPPT", key=f"hsp3d_add_{group['id']}",
                           disabled=len(scene["panels"]) >= 48):
                _add_panel(scene, group["id"])
                st.rerun()
            if right.button("Excluir grupo vazio", key=f"hsp3d_del_{group['id']}",
                            disabled=len(scene["groups"]) == 1 or bool(grouped)):
                scene["groups"].remove(group)
                st.rerun()
            for panel in grouped:
                st.caption(f"**{panel['id']}** · X Leste {panel['x_m']:.2f} m · "
                           f"Y Norte {panel['y_m']:.2f} m")
                col_z, col_group, col_del = st.columns([2, 2, 1])
                hkey = f"hsp3d_z_{panel['id']}"
                if hkey not in st.session_state:
                    st.session_state[hkey] = panel["bottom_height_m"]
                panel["bottom_height_m"] = col_z.number_input(
                    f"Altura borda inferior {panel['id']} (m)",
                    0., 500., step=.05, format="%.3f", key=hkey)
                group_ids = [g["id"] for g in scene["groups"]]
                chosen = col_group.selectbox(
                    f"MPPT da placa {panel['id']}",
                    options=group_ids, index=group_ids.index(panel["mppt_id"]),
                    format_func=lambda gid: next(
                        g["name"] for g in scene["groups"] if g["id"] == gid),
                    key=f"hsp3d_group_{panel['id']}")
                if chosen != panel["mppt_id"]:
                    panel["mppt_id"] = chosen
                    st.rerun()
                if col_del.button("Remover",key=f"hsp3d_remove_{panel['id']}",
                                  disabled=len(scene["panels"]) == 1):
                    scene["panels"].remove(panel)
                    st.rerun()


def _obstacle_controls(scene):
    st.markdown("#### Obstáculos")
    if st.button("Adicionar obstáculo", key="hsp3d_add_obstacle",
                 disabled=len(scene["obstacles"]) >= 32):
        number = st.session_state["hsp3d_next_obstacle_id"]
        st.session_state["hsp3d_next_obstacle_id"] += 1
        scene["obstacles"].append({
            "id": f"obs-{number}", "x_m": 0.,
            "y_m": 3. + min(number - 1, 25),
            "width_m": 3., "depth_m": .5, "height_m": 3.,
        })
        st.rerun()
    if not scene["obstacles"]:
        st.caption("Sem obstáculos: o HSP com e sem sombra será igual.")
    for obs in list(scene["obstacles"]):
        with st.expander(f"{obs['id']} · X {obs['x_m']:.2f} / Y {obs['y_m']:.2f} m"):
            if st.button("Remover obstáculo", key=f"hsp3d_remove_{obs['id']}"):
                scene["obstacles"].remove(obs)
                st.rerun()
            ca, cb, cc = st.columns(3)
            for col, field, label, max_value in (
                (ca, "width_m", "Largura", 1000.),
                (cb, "depth_m", "Profundidade", 1000.),
                (cc, "height_m", "Altura", 500.),
            ):
                key = f"hsp3d_{field}_{obs['id']}"
                if key not in st.session_state:
                    st.session_state[key] = obs[field]
                obs[field] = col.number_input(
                    f"{label} de {obs['id']} (m)", min_value=.01,
                    max_value=max_value, step=.1, format="%.2f", key=key)


def render_scene_editor(lat, lon, tilt, azimuth, bottom_height,
                        panel_length, panel_width):
    """Editor de geometria 3D com estado bidirecional e seleção múltipla."""
    st.subheader("Visualizador 3D interativo de sombreamento")
    st.caption("Clique e arraste placas/obstáculos para mover em X/Y. "
               "Ctrl+clique: várias placas; Shift+clique: todas do mesmo MPPT. "
               "A altura só muda nos campos numéricos. Arraste sobre o "
               "espaço vazio para girar a câmera.")

    if "hsp3d_scene_state" not in st.session_state:
        st.session_state["hsp3d_scene_state"] = _initial_scene(
            tilt, azimuth, bottom_height, panel_length, panel_width)
        st.session_state["hsp3d_next_panel_id"] = 2
        st.session_state["hsp3d_next_mppt_id"] = 2
        st.session_state["hsp3d_next_obstacle_id"] = 2
    scene = st.session_state["hsp3d_scene_state"]
    module = scene["module"]
    module.update({
        "length_m": float(panel_length), "width_m": float(panel_width),
        "tilt_deg": float(tilt), "azimuth_deg": float(azimuth),
        "bottom_height_m": float(bottom_height),
        "count": len(scene["panels"]),
        "columns": min(int(module.get("columns", 1)), len(scene["panels"])),
    })
    with st.expander("Gerenciar MPPTs, placas e dimensões", expanded=False):
        _group_controls(scene)
        st.divider()
        _obstacle_controls(scene)

    clean = validate_scene(scene)
    st.session_state["hsp3d_scene_state"] = clean
    c1,c2,c3 = st.columns(3)
    day = c1.date_input("Data da prévia solar", value=date.today(),
                         key="hsp3d_day")
    local_hour = c2.slider("Hora local", 0., 23.75, 15., .25,
                           key="hsp3d_hour")
    offset = c3.selectbox("Fuso da prévia", list(range(-12,15)),
                          index=9, format_func=lambda x:f"UTC{x:+d}",
                          key="hsp3d_offset")
    elevation, sun_azi = preview_sun(lat, lon, day, local_hour, offset)
    ratios = shade_by_panel(clean, [elevation], [sun_azi], rows=8, cols=6)[0]
    try:
        from_client = interactive_scene(clean, elevation, sun_azi,
                                        ratios, key="hsp3d_drag_editor")
        if _apply_drag(clean, from_client):
            st.session_state["hsp3d_scene_state"] = validate_scene(clean)
            st.rerun()
    except ValueError as exc:
        st.warning(f"Movimentação inválida foi ignorada: {exc}")
    if elevation > 0:
        st.caption(f"Sol: elevação {elevation:.1f}°, azimute {sun_azi:.1f}°. "
                   f"Prévia: {ratios.mean()*100:.1f}% de área frontal sombreada "
                   "(grade 8×6; cálculo horário 5×5).")
    else:
        st.caption("Sol abaixo do horizonte; nenhuma contribuição direta nesta prévia.")
    st.caption(f"{len(clean['panels'])} placa(s), {len(clean['groups'])} grupo(s) "
               f"MPPT, {len(clean['obstacles'])} obstáculo(s). Altura de centro "
               "calculada a partir da borda inferior de cada placa.")
    st.info("Análise exclusivamente óptica: a média de sombra geométrica "
            "atinge somente o POA direto. MPPT é apenas agrupamento visual; "
            "não se calculam perdas elétricas.")
    return clean
