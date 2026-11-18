"""HSP Simulator dashboard 2.0; physically consistent hourly backend."""
import json
from pathlib import Path
import streamlit as st
from core.app import SolarEngine
from dashboard.visualizations import SolarDashboardRenderer
from dashboard.scene3d import render_scene_editor
from core.scene3d_shading import center_height
from services.deps import Dependencies
from utils.constants import ALBEDO_REFERENCE, CELL_TECHNOLOGY_REFERENCE

st.set_page_config(page_title='HSP Simulator v2', page_icon='☀️',layout='wide')
st.title('☀️ Simulador de HSP — transposição horária')
st.caption('Irradiação incidente no plano do módulo (POA) a partir de séries horárias; média climatológica não substitui simulação temporal.')
repo = Dependencies.get_solar_repository()
renderer = SolarDashboardRenderer(SolarEngine(repo), repo)
@st.cache_data
def localities():
    p = Path('data/localidades.json')
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

with st.sidebar:
    st.header('Configuração do projeto')
    mode = st.radio('Localização', ['Cidade','Coordenadas manuais'],horizontal=True)
    lat,lon,name = -5.79448,-35.21101,'Natal/RN'
    if mode == 'Cidade':
        cities = localities()
        if cities:
            state = st.selectbox('Estado', sorted(cities), index=(sorted(cities).index('RN') if 'RN' in cities else 0))
            items = sorted(cities[state]['cidades'],key=lambda d:d['nome'])
            names = [x['nome'] for x in items]
            city = st.selectbox('Cidade', names, index=(names.index('Natal') if 'Natal' in names else 0))
            point = next(c for c in items if c['nome']==city)
            lat,lon,name = point['latitude'], point['longitude'], f'{city}/{state}'
        else:
            st.info('Use coordenadas manuais ou restaure localidades.json do repositório original.')
    else:
        lat = st.number_input('Latitude', min_value=-90.,max_value=90.,value=-5.79448,format='%.5f')
        lon = st.number_input('Longitude', min_value=-180.,max_value=180.,value=-35.21101,format='%.5f')
        name=f'{lat:.4f},{lon:.4f}'
    st.caption(f'{lat:.5f}, {lon:.5f}')
    provider = st.selectbox('Fonte de dados', ['Automático (NASA → PVGIS)', 'NASA POWER','PVGIS','INPE/LABREN Atlas 2017'])
    forced = None if provider.startswith('Automático') else provider
    model = st.selectbox('Modelo de transposição', ['Perez','Haydavies','Isotropic'])
    tilt = st.slider('Inclinação (°)', 0,90,15)
    azi = st.slider('Azimute geográfico (0=N, 90=L, 180=S, 270=O)',0,360,0)
    bifacial = st.toggle('Módulo bifacial (aproximação de face traseira isolada)',value=False)
    technology = st.selectbox('Tecnologia da célula',list(CELL_TECHNOLOGY_REFERENCE))
    orientation = st.selectbox('Disposição do módulo',['Retrato','Paisagem'])
    module_length = st.number_input('Comprimento físico do módulo (m)', min_value=.1,
                                     max_value=10., value=2.278, step=.01, format='%.3f')
    module_width = st.number_input('Largura física do módulo (m)', min_value=.1,
                                    max_value=10., value=1.134, step=.01, format='%.3f')
    bottom_height = st.number_input('Altura padrão da borda inferior — novas placas (m)',
                                    min_value=0., max_value=500., value=.15,
                                    step=.05, format='%.3f')
    terrain = st.selectbox('Superfície do solo',list(ALBEDO_REFERENCE))
    albedo = st.slider('Albedo',0.,1.,float(ALBEDO_REFERENCE[terrain]),.01)
# Retrato: comprimento físico acompanha a rampa; paisagem: largura acompanha.
slope_length = module_length if orientation == 'Retrato' else module_width
face_width = module_width if orientation == 'Retrato' else module_length
height_center = center_height(bottom_height, slope_length, tilt)
scene3d = render_scene_editor(lat, lon, tilt, azi, bottom_height,
                               slope_length, face_width)
if st.button('Calcular e comparar', type='primary'):
    renderer.renderizar_layout_comparativo(
        lat, lon, tilt, azi, albedo, height_center, technology,
        bifacial, orientation, bool(scene3d['obstacles']), None,
        name, forced, model.lower(), scene3d=scene3d,
        module_length=module_length, module_width=module_width)

st.caption('Estimativa ótica: sombra amostrada na face dos módulos reduz somente '
           'a irradiância DIRETA. O HSP não representa produção DC/AC, perda '
           'elétrica de strings ou laudo de sombreamento certificado.')
