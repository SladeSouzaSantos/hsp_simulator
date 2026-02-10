import os
import streamlit as st
import pandas as pd
import altair as alt
import json
import plotly.graph_objects as go
import numpy as np
import math
from datetime import datetime

from core.app import calcular_projeto_solar
from utils.constants import ALBEDO_REFERENCE, CELL_TECHNOLOGY_REFERENCE
from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService

# --- FUNÇÕES DE NÚCLEO (GEOMETRIA SOLAR) ---

def calcular_posicoes(lat, altura, dia_ano, hora):
    """Calcula a física da sombra e a posição do sol (Azimute e Altitude)."""
    # Declinação Solar (Cooper, 1969)
    delta = 23.45 * math.sin(math.radians(360/365 * (dia_ano - 81)))
    # Ângulo Horário (15 graus por hora)
    h_ang = (hora - 12) * 15
    lat_rad, delta_rad, h_rad = map(math.radians, [lat, delta, h_ang])
    
    # Altitude Solar (Ângulo acima do horizonte)
    sin_alpha = (math.sin(lat_rad) * math.sin(delta_rad) + 
                 math.cos(lat_rad) * math.cos(delta_rad) * math.cos(h_rad))
    
    if sin_alpha <= 0.001: 
        return None 
    
    alpha_rad = math.asin(sin_alpha)
    comprimento_sombra = altura / math.tan(alpha_rad)
    
    # Azimute Solar
    arg_cos = (math.sin(delta_rad) - math.sin(lat_rad) * math.sin(alpha_rad)) / (math.cos(lat_rad) * math.cos(alpha_rad))
    arg_cos = max(min(arg_cos, 1), -1) 
    gamma_deg = math.degrees(math.acos(arg_cos))
    
    if h_ang > 0: 
        gamma_deg = 360 - gamma_deg
    
    return gamma_deg, (gamma_deg + 180) % 360, comprimento_sombra, math.degrees(alpha_rad)

# --- CARREGAMENTO DE LOCALIDADES ---
@st.cache_data
def carregar_localidades():
    with open("data/localidades.json", "r", encoding="utf-8") as f:
        return json.load(f)

localidades = carregar_localidades()

# O Docker injeta a API_URL aqui através do arquivo .env
API_BASE_URL = os.getenv("API_URL")

st.set_page_config(page_title="Dimensionador HSP", layout="wide")
st.title("☀️ Comparativo Solar: Projeto vs. Referência (0°/0°)")

# --- LÓGICA DE CACHE INTELIGENTE ---
if 'cache_nasa' not in st.session_state:
    st.session_state.cache_nasa = {}

# Barra lateral para inputs
with st.sidebar:
    st.header("PARÂMETROS DO PROJETO")
    
    st.subheader("📍 Localização")
    # Seletor de modo de entrada
    metodo_loc = st.radio("Método de Seleção", ["Cidade", "Coordenadas Manuais"], horizontal=True)

    if metodo_loc == "Cidade":
        # 1. Seleção de Estado
        siglas_disponiveis = sorted(localidades.keys())
        sigla_sel = st.selectbox("Estado", siglas_disponiveis)
        
        # 2. Seleção de Cidade
        dados_estado = localidades[sigla_sel]
        lista_cidades = sorted(dados_estado["cidades"], key=lambda x: x["nome"])
        nomes_cidades = [c["nome"] for c in lista_cidades]
        cidade_sel_nome = st.selectbox("Cidade", nomes_cidades)
        
        # Extração de Coordenadas
        cidade_data = next(c for c in lista_cidades if c["nome"] == cidade_sel_nome)
        lat = cidade_data["latitude"]
        lon = cidade_data["longitude"]
        nome_exibicao = f"{cidade_sel_nome}/{sigla_sel}"
    
    else:
        # Entrada Manual - O segredo aqui é o step=None para remover o + e -
        col_lat, col_lon = st.columns(2)
        lat = col_lat.number_input("Latitude", value=-5.79448, format="%.5f", step=0.0)
        lon = col_lon.number_input("Longitude", value=-35.21101, format="%.5f", step=0.0)
        nome_exibicao = "Coordenadas Personalizadas"
        sigla_sel = "Custom"
    
    st.caption(f"📍 Coordenadas: {lat}, {lon}")
    
    st.divider()
    
    st.subheader("Orientação dos Módulos")
    inc = st.slider("Inclinação (°)", 0, 90, 15)
    azi = st.slider("Azimute (°)", 0, 360, 0)
    
    st.divider()
    
    st.subheader("Módulo FV")
    modo_bifacial = st.toggle("Ativar Ganho Bifacial", value=True)
    h = st.number_input("Altura da Placa do chão (m)", min_value=0.0, value=0.2, step=0.05)
    tec_chave = st.selectbox("Tecnologia da Célula", list(CELL_TECHNOLOGY_REFERENCE.keys()))
    st.caption(f"Tipo: {CELL_TECHNOLOGY_REFERENCE[tec_chave]['nome_comum']}")
    
    st.divider()
    
    st.subheader("Condições do Solo")
    tipo_solo = st.selectbox("Tipo de Solo", list(ALBEDO_REFERENCE.keys()))
    alb = st.slider("Albedo Ajustado", 0.0, 1.0, float(ALBEDO_REFERENCE[tipo_solo]))

    st.divider()

    st.subheader("🏗️ Obstruções e Sombra")
    usar_obstaculo = st.toggle("Considerar Obstáculo Próximo", value=False)

    h_obs, d_obs, azi_obs = 3.0, 2.0, azi
    obstacle_config = None
    
    if usar_obstaculo:
        h_obs = st.number_input("Altura do Obstáculo (m)", min_value=0.01, value=3.0, step=0.5, format="%.2f")
        d_obs = st.number_input("Distância do Painel (m)", min_value=0.1, value=2.0, step=0.5, format="%.2f")
        
        # Se o obstáculo for uma parede ao lado, podemos definir o azimute dela. 
        # Por padrão, vamos sugerir o mesmo azimute do painel (parede frontal/traseira)
        azi_obs = st.number_input("Azimute do Obstáculo (°)", min_value=0, max_value=360, value=int(azi), step=5)
        
        obstacle_config = {
            'height': h_obs,
            'distance': d_obs,
            'azimuth': azi_obs
        }
        
        # VISUALIZAÇÃO DO CENÁRIO COM OBSTÁCULO
        c1, c2 = st.columns(2)
        meses_lista = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes_v = c1.selectbox("Mês de Referência", meses_lista, index=datetime.now().month - 1)
        hora_sim = c2.slider("Horário da Simulação", 5.0, 19.0, 12.0, step=0.5, format="%g h")

        mes_num = meses_lista.index(mes_v) + 1
        dia_ano = datetime(2026, mes_num, 21).timetuple().tm_yday
        
        # Altura de referência para o cálculo do sol/sombra
        altura_ref = h_obs if usar_obstaculo else h
        pos_agora = calcular_posicoes(lat, altura_ref, dia_ano, hora_sim)

        # --- AJUSTES DE ESCALA (Sua regra: 2x a distância) ---
        # Se não houver obstáculo, usamos um padrão de 10m para visualização do painel
        max_r = d_obs * 2 if usar_obstaculo else 10

        fig = go.Figure()

        # =================================================================
        # INCLUSÃO DA TRAJETÓRIA DO SOL (ESTILO SHADOW_APP.PY)
        # =================================================================
        # Criamos o rastro na borda do gráfico (90% do raio máximo)
        rastro_distancia = max_r * 0.9 
        traj_theta = []
        
        # Fazemos a varredura do dia para desenhar o caminho
        for hr_track in np.linspace(5.5, 18.5, 60):
            p_track = calcular_posicoes(lat, altura_ref, dia_ano, hr_track)
            if p_track:
                traj_theta.append(p_track[0]) # Pega o Azimute do sol
        
        if traj_theta:
            fig.add_trace(go.Scatterpolar(
                r=[rastro_distancia] * len(traj_theta), 
                theta=traj_theta,
                mode='lines', 
                name='Trajetória do Sol',
                line=dict(color='gold', dash='dot', width=3) # Pontilhados amarelos
            ))
        # =================================================================

        # --- ELEMENTO 1: O PAINEL (Escala Real 2.4m) ---
        fig.add_trace(go.Scatterpolar(
            r=[0, 1], theta=[azi, azi],
            mode='lines+markers', name='Módulo FV (2.4m)',
            line=dict(color='blue', width=8),
            marker=dict(symbol='square', size=4)
        ))

        # --- ELEMENTO 2: O OBSTÁCULO E SOMBRA ---
        dist_sombra = 0
        if usar_obstaculo and pos_agora:
            az_sol, az_sombra, dist_sombra, alt_sol = pos_agora
            
            # Sombra projetada: Começa no obstáculo
            fig.add_trace(go.Scatterpolar(
                r=[d_obs, d_obs + dist_sombra], 
                theta=[azi_obs, az_sombra],
                mode='lines', name='Sombra Projetada',
                line=dict(color='rgba(50, 50, 50, 0.4)', width=10)
            ))

            # Marcador do Obstáculo
            fig.add_trace(go.Scatterpolar(
                r=[d_obs], theta=[azi_obs],
                mode='markers+text', name='Obstáculo',
                marker=dict(size=15, color='red', symbol='square')
            ))

        # --- ELEMENTO 3: TRAJETÓRIA DO SOL ---
        traj_theta, traj_r = [], []
        relatorio_dados = []
        for hr in np.linspace(5.5, 18.5, 60):
            p = calcular_posicoes(lat, altura_ref, dia_ano, hr)
            if p:
                # Para o rastro do sol, mapeamos a altitude (90-alt) para caber na escala do gráfico
                # Mas como o gráfico agora é focado em metros, o sol é apenas referencial
                traj_theta.append(p[0])
                traj_r.append(p[0]) # Apenas para rastro direcional

        if pos_agora:
            # Indicador da direção do Sol (seta externa)
            fig.add_trace(go.Scatterpolar(
                r=[d_obs * 1.8], theta=[pos_agora[0]],
                mode='markers', name='Direção do Sol',
                marker=dict(size=12, color='orange', symbol='star')
            ))

        fig.update_layout(
            polar=dict(
                angularaxis=dict(
                    direction="clockwise", 
                    rotation=90, 
                    tickvals=[0, 90, 180, 270], 
                    ticktext=['N', 'L', 'S', 'O']
                ),
                radialaxis=dict(
                    visible=True, 
                    range=[0, max_r], 
                    title="Metros"
                )
            ),
            height=700, 
            template="plotly_white",
            legend=dict(orientation="h", y=-0.2)
        )
        
        st.plotly_chart(fig, width='stretch') 
    
if st.button("Calcular e Comparar"):
    # Normalizamos para o cache interno do worker
    lat_fixed = round(float(lat), 4)
    lon_fixed = round(float(lon), 4)
    chave_local = f"{lat_fixed}_{lon_fixed}"
    
    # 1. Gerenciamento de Dados (NASA)
    if chave_local in st.session_state.cache_nasa:
        dados_clima = st.session_state.cache_nasa[chave_local]
    else:
        with st.spinner("Buscando novos dados na NASA..."):
            gateway = NasaPowerGateway(lat_fixed, lon_fixed)
            dados_clima = SolarDataService.standardize_data(gateway.fetch_climatology())
            st.session_state.cache_nasa[chave_local] = dados_clima
            st.success("✅ Dados carregados!")

    # 2. Execução dos Cálculos (Dois Cenários)
    with st.spinner("Calculando modelos..."):
        # Cenário A: Seu Projeto
        res_projeto = calcular_projeto_solar(
            lat=lat, lon=lon, inclinacao=inc, azimute=azi, 
            albedo=alb, altura=h, tecnologia=tec_chave, 
            is_bifacial=modo_bifacial, panel_width=2.278,
            dados_pre_carregados=dados_clima,
            obstacle_config=obstacle_config
        )
        
        # Cenário B: Padrão (Inclinação 0, Azimute 0)
        res_padrao = calcular_projeto_solar(
            lat=lat, lon=lon, inclinacao=0, azimute=0, 
            albedo=alb, altura=h, tecnologia=tec_chave, 
            is_bifacial=modo_bifacial, panel_width=2.278,
            dados_pre_carregados=dados_clima,
            obstacle_config=None
        )
        
        # --- EXIBIÇÃO DE MÉTRICAS E GRÁFICOS ---
        # (O resto do seu código de métricas e Altair permanece igual daqui para baixo)
        label_tipo = "Bifacial" if modo_bifacial else "Monofacial"
        st.subheader(f"Resultados Médios Diários ({label_tipo}) - {nome_exibicao}")
        
        col1, col2, col3 = st.columns(3)
        ganho_vs_padrao = ((res_projeto['media'] / res_padrao['media']) - 1) * 100
        
        col1.metric("HSP Projeto", f"{res_projeto['media']:.3f}", f"{ganho_vs_padrao:.1f}% vs. 0°/0°")
        col2.metric("HSP Padrão (0°/0°)", f"{res_padrao['media']:.3f}")
        col3.metric("Diferença Bruta", f"{res_projeto['media'] - res_padrao['media']:.3f} kWh/m²")

        perda_str = res_projeto.get("perda_sombreamento_estimada", "0%")
        
        # Verificamos se há obstáculo e se a perda não é zero
        if usar_obstaculo and perda_str not in ["0%", "0.0%"]:
            st.error(f"🚨 **Perda por Sombreamento:** {perda_str}")

        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        df_projeto = pd.DataFrame({"Mês": meses, "HSP": res_projeto["mensal"], "Cenário": "Seu Projeto"})
        df_padrao = pd.DataFrame({"Mês": meses, "HSP": res_padrao["mensal"], "Cenário": "Padrão (0°/0°)"})
        df_comp = pd.concat([df_projeto, df_padrao])

        grafico = alt.Chart(df_comp).mark_bar().encode(
            x=alt.X('Mês:N', sort=None, title="Meses"),
            y=alt.Y('HSP:Q', title="HSP (kWh/m²/dia)"),
            xOffset='Cenário:N',
            color=alt.Color('Cenário:N', scale=alt.Scale(range=['#ff4b4b', '#4b4bff']), title="Cenário"),
            tooltip=['Cenário', 'Mês', alt.Tooltip('HSP', format='.3f')]
        ).properties(
            height=400,
            title=f"Comparativo Mensal: Projeto vs. Referência Plana ({label_tipo})"
        )

        st.altair_chart(grafico, width='stretch')

        with st.expander("Ver Tabela Comparativa Detalhada"):
            # Criamos o dataframe garantindo que os dados venham das variáveis de resultado
            df_table = pd.DataFrame({
                "Mês": meses,
                "Seu Projeto": res_projeto["mensal"],
                "Padrão (0°/0°)": res_padrao["mensal"]
            }).set_index("Mês").T
            
            # O .style.format força o Streamlit a mostrar 3 casas decimais em tudo
            st.table(df_table.style.format("{:.3f}"))