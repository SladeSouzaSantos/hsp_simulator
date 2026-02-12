import pytest
from unittest.mock import MagicMock
from dashboard.visualizations import SolarDashboardRenderer

@pytest.fixture
def mock_components():
    """Cria mocks do engine e do repository para não precisar de internet"""
    engine = MagicMock()
    repo = MagicMock()
    return engine, repo

def test_renderer_initialization(mock_components):
    engine, repo = mock_components
    renderer = SolarDashboardRenderer(engine=engine, repository=repo)
    
    assert renderer.engine == engine
    assert renderer.repository == repo

def test_cache_logic_integration(mock_components):
    """Verifica se o renderer tenta buscar dados no repositório"""
    engine, repo = mock_components
    renderer = SolarDashboardRenderer(engine=engine, repository=repo)
    
    # Simula o comportamento do Streamlit session_state
    import streamlit as st
    st.session_state.cache_api_data = {}
    
    # Mock do retorno do repositório
    repo.get_standardized_data.return_value = {"hsp_global": [5.0]*12}
    engine.calcular_projeto_solar.return_value = {"media": 5.0, "mensal": [5.0]*12}

    # Executa uma renderização parcial (apenas para testar o fluxo de dados)
    # Usamos valores arbitrários
    renderer.renderizar_layout_comparativo(
        lat=-7.0, lon=-35.0, inc=15, azi=0, alb=0.2, h=1.0, 
        tec_chave="TOPCON", modo_bifacial=True, orientacao="Retrato",
        usar_obstaculo=False, config_obstaculo=None, nome_exibicao="Teste"
    )

    # Verifica se o repositório foi chamado (provas de que a integração funciona)
    repo.get_standardized_data.assert_called_once()
    assert "-7.0_-35.0" in st.session_state.cache_api_data