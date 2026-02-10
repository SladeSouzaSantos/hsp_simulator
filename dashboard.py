import os
import streamlit as st
import pandas as pd
import altair as alt
import json # Adicionado para ler o banco local

from core.app import calcular_projeto_solar
from utils.constants import ALBEDO_REFERENCE, CELL_TECHNOLOGY_REFERENCE
from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService

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