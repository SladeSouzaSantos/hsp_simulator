import json
import streamlit as st
from datetime import datetime
from dashboard.visualizations import renderizar_grafico_sombra, renderizar_layout_comparativo
from utils.constants import ALBEDO_REFERENCE, CELL_TECHNOLOGY_REFERENCE

# --- CARREGAMENTO DE LOCALIDADES ---
@st.cache_data
def carregar_localidades():
    with open("data/localidades.json", "r", encoding="utf-8") as f:
        return json.load(f)

localidades = carregar_localidades()

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

    h_obs, d_obs, azi_obs = 3.0, 2.0, azi # Valores padrão para o cenário sem obstáculo
    
    if usar_obstaculo:
        h_obs = st.number_input("Altura do Obstáculo (m)", min_value=0.01, value=3.0, step=0.05, format="%.2f")
        largura_obj = st.number_input("Largura do Obstáculo (m)", min_value=0.1, value=5.0, step=0.05, format="%.2f")
        # Se o obstáculo for uma parede ao lado, podemos definir o azimute dela. 
        # Por padrão, vamos sugerir o mesmo azimute do painel (parede frontal/traseira)
        azi_obs = st.number_input("Azimute do Obstáculo (°)", min_value=0, max_value=360, value=int(azi), step=5)
               
        col_dim1, col_dim2 = st.columns(2)
        orientacao = col_dim1.selectbox("Orientação da Placa", ["Retrato", "Paisagem"])
        dist_input = col_dim2.number_input("Distância (m)", value=2.0, step=0.05, format="%.2f")

        st.divider()
        
        # Lógica interna para corrigir d_obs
        tamanho_placa = 1.134 if orientacao == "Paisagem" else 2.278
        d_obs = dist_input + tamanho_placa

        api_obstacle_config = {
            'altura_obstaculo': h_obs,
            'distancia_obstaculo': dist_input,
            'referencia_azimutal_obstaculo': azi_obs,
            'largura_obstaculo': largura_obj
        }
        
        # VISUALIZAÇÃO DO CENÁRIO COM OBSTÁCULO
        c1, c2 = st.columns(2)
        meses_lista = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes_v = c1.selectbox("Mês de Referência", meses_lista, index=datetime.now().month - 1)
        hora_sim = c2.slider("Horário da Simulação", 8.0, 16.0, 12.0, step=0.5, format="%g h")
        
        renderizar_grafico_sombra(meses_lista, mes_v, hora_sim, lat, h, usar_obstaculo, h_obs, d_obs, azi_obs, azi, orientacao) 
    else:
        api_obstacle_config = None    
        orientacao = "Retrato" # Valor padrão, pode ser ajustado na configuração do obstáculo

if st.button("Calcular e Comparar"):
    renderizar_layout_comparativo(
        lat=lat, 
        lon=lon, 
        inc=inc, 
        azi=azi, 
        alb=alb, 
        h=h,
        tec_chave=tec_chave, 
        modo_bifacial=modo_bifacial, 
        orientacao=orientacao,
        usar_obstaculo=usar_obstaculo,
        config_obstaculo=api_obstacle_config,
        nome_exibicao=nome_exibicao)