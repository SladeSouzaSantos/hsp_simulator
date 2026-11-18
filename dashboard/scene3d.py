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


def _obstacle_controls():
    if "hsp3d_obstacle_ids" not in st.session_state:
        st.session_state["hsp3d_obstacle_ids"] = [1]
        st.session_state["hsp3d_next_id"] = 2
    ids = st.session_state["hsp3d_obstacle_ids"]
    if st.button("Adicionar obstáculo", disabled=len(ids) >= 12):
        ids.append(st.session_state["hsp3d_next_id"])
        st.session_state["hsp3d_next_id"] += 1
        st.rerun()
    obstacles = []
    for identifier in ids:
        with st.expander(f"Obstáculo {identifier}", expanded=(len(ids)==1)):
            if st.button("Remover", key=f"hsp3d_remove_{identifier}"):
                st.session_state["hsp3d_obstacle_ids"].remove(identifier)
                st.rerun()
            a,b,c,d,e = st.columns(5)
            x = a.number_input("X: Leste (m)",-1000.,1000.,0.,step=.25,key=f"hsp3d_x_{identifier}")
            y = b.number_input("Y: Norte (m)",-1000.,1000.,3.,step=.25,key=f"hsp3d_y_{identifier}")
            w = c.number_input("Largura (m)",.01,1000.,3.,step=.25,key=f"hsp3d_w_{identifier}")
            depth = d.number_input("Profundidade (m)",.01,1000.,.5,step=.25,key=f"hsp3d_d_{identifier}")
            h = e.number_input("Altura (m)",.01,500.,3.,step=.25,key=f"hsp3d_h_{identifier}")
            obstacles.append(dict(x_m=x,y_m=y,width_m=w,depth_m=depth,height_m=h))
    return obstacles


def render_scene_editor(lat, lon, tilt, azimuth, bottom_height,
                        panel_length, panel_width):
    """Retorna a cena em metros; chamada pela tela após o formulário do módulo."""
    st.subheader("Visualizador 3D de sombreamento")
    st.caption("Gire a cena com o mouse, aproxime com a roda. Mova e dimensione "
               "os obstáculos pelos campos abaixo. A borda inferior é o ponto "
               "mais baixo do plano inclinado do módulo.")
    c1,c2,c3 = st.columns(3)
    count = c1.number_input("Quantidade de módulos",1,24,1,step=1)
    columns = c2.number_input("Módulos por fileira",1,int(count),min(2,int(count)),step=1)
    gap = c3.number_input("Espaçamento (m)",0.,10.,.15,step=.05)
    scene = dict(
        module=dict(
            length_m=panel_length, width_m=panel_width,
            bottom_height_m=bottom_height, tilt_deg=tilt, azimuth_deg=azimuth,
            count=int(count), columns=int(columns), gap_m=gap,
        ),
        obstacles=_obstacle_controls(),
    )
    clean = validate_scene(scene)
    st.caption(f"Altura geométrica do centro: **{center_height(bottom_height, panel_length, tilt):.3f} m** "
               "(calculada automaticamente a partir da borda inferior). "
               "Esta altura não é solicitada como entrada.")
    c1,c2,c3 = st.columns(3)
    day = c1.date_input("Data para prévia solar",value=date.today())
    local_hour = c2.slider("Hora local",0.,23.75,15.,.25,format="%.2f h")
    offset = c3.selectbox("Fuso da prévia",list(range(-12,15)),index=9,
                          format_func=lambda x:f"UTC{x:+d}")
    elevation, sun_azi = preview_sun(lat,lon,day,local_hour,offset)
    fig, fractions = make_scene_figure(clean, elevation, sun_azi)
    st.plotly_chart(fig, use_container_width=True, key="hsp3d_scene")
    if elevation > 0:
        st.caption(f"Sol: elevação {elevation:.1f}°, azimute {sun_azi:.1f}° "
                   f"· área frontal sombreada na prévia: {fractions.mean()*100:.1f}%. "
                   "A prévia da face usa grade 8×6; cálculo horário usa 5×5.")
    else:
        st.caption("Sol abaixo do horizonte; nenhuma contribuição direta neste instante.")
    st.info("Cálculo HSP: a sombra 3D reduz apenas o POA direto, mantendo a "
            "componente difusa, a refletida e a aproximação bifacial sem "
            "obstrução. Não calcula perdas em strings, diodos ou MPPTs.")
    return clean
