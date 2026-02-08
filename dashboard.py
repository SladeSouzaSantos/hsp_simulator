import os
import streamlit as st
import pandas as pd
import altair as alt

from core.app import calcular_projeto_solar
from utils.constants import ALBEDO_REFERENCE, CELL_TECHNOLOGY_REFERENCE
from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService

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
    
    st.divider()
    
    st.subheader("Dados Geográficos")
    lat = st.number_input("Latitude", value=-7.562, format="%.4f")
    lon = st.number_input("Longitude", value=-37.688, format="%.4f")
    
    st.divider()
    
    st.subheader("Orientação dos Módulos")
    inc = st.slider("Inclinação (°)", 0, 90, 15)
    azi = st.slider("Azimute (°)", 0, 360, 0)
    
    st.divider()
    
    st.subheader("Módulo FV")
    modo_bifacial = st.toggle("Ativar Ganho Bifacial", value=True)
    h = st.number_input("Altura da Placa do chão (m)", value=0.2)
    # Busca as tecnologias (PERC, TOPCON, etc) do dicionário
    tec_chave = st.selectbox("Tecnologia da Célula", list(CELL_TECHNOLOGY_REFERENCE.keys()))
    # Opcional: mostrar o nome comum abaixo do seletor
    st.caption(f"Tipo: {CELL_TECHNOLOGY_REFERENCE[tec_chave]['nome_comum']}")
    
    st.divider()
    
    st.subheader("Condições do Solo")
    # Busca os nomes das chaves do dicionário de Albedo
    tipo_solo = st.selectbox("Tipo de Solo", list(ALBEDO_REFERENCE.keys()))
    alb = st.slider("Albedo Ajustado", 0.0, 1.0, float(ALBEDO_REFERENCE[tipo_solo]))
    
if st.button("Calcular e Comparar"):
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
            dados_pre_carregados=dados_clima
        )
        
        # Cenário B: Padrão (Inclinação 0, Azimute 0) - Mantém a bifacialidade se o toggle estiver ligado
        res_padrao = calcular_projeto_solar(
            lat=lat, lon=lon, inclinacao=0, azimute=0, 
            albedo=alb, altura=h, tecnologia=tec_chave, 
            is_bifacial=modo_bifacial, panel_width=2.278,
            dados_pre_carregados=dados_clima
        )
        
        # --- EXIBIÇÃO DE MÉTRICAS ---
        label_tipo = "Bifacial" if modo_bifacial else "Monofacial"
        st.subheader(f"Resultados Médios Diários ({label_tipo})")
        
        col1, col2, col3 = st.columns(3)
        ganho_vs_padrao = ((res_projeto['media'] / res_padrao['media']) - 1) * 100
        
        col1.metric("HSP Projeto", f"{res_projeto['media']:.3f}", f"{ganho_vs_padrao:.1f}% vs. 0°/0°")
        col2.metric("HSP Padrão (0°/0°)", f"{res_padrao['media']:.3f}")
        col3.metric("Diferença Bruta", f"{res_projeto['media'] - res_padrao['media']:.3f} kWh/m²")

        # 3. Preparação do Gráfico Comparativo
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        # Criamos um DataFrame longo (ideal para o Altair)
        df_projeto = pd.DataFrame({"Mês": meses, "HSP": res_projeto["mensal"], "Cenário": "Seu Projeto"})
        df_padrao = pd.DataFrame({"Mês": meses, "HSP": res_padrao["mensal"], "Cenário": "Padrão (0°/0°)"})
        df_comp = pd.concat([df_projeto, df_padrao])

        # Construção do Gráfico com Barras Lado a Lado
        grafico = alt.Chart(df_comp).mark_bar().encode(
            x=alt.X('Mês:N', sort=None, title="Meses"),
            y=alt.Y('HSP:Q', title="HSP (kWh/m²/dia)"),
            xOffset='Cenário:N', # Este comando coloca as barras lado a lado
            color=alt.Color('Cenário:N', scale=alt.Scale(range=['#ff4b4b', '#4b4bff']), title="Cenário"),
            tooltip=['Cenário', 'Mês', alt.Tooltip('HSP', format='.3f')]
        ).properties(
            height=400,
            title=f"Comparativo Mensal: Projeto vs. Referência Plana ({label_tipo})"
        )

        st.altair_chart(grafico, width="stretch")

        # 4. Tabela de Dados Transposta
        with st.expander("Ver Tabela Comparativa Detalhada"):
            df_table = pd.DataFrame({
                "Mês": meses,
                "Seu Projeto": res_projeto["mensal"],
                "Padrão (0°/0°)": res_padrao["mensal"]
            }).set_index("Mês").T
            st.table(df_table.style.format("{:.3f}"))