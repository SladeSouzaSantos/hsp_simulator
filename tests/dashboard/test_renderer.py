"""Dashboard tests assert Streamlit data cache, not obsolete session_state keys."""
import pytest
from unittest.mock import MagicMock

st = pytest.importorskip('streamlit')
from dashboard.visualizations import SolarDashboardRenderer, _load_provider_data


@pytest.fixture
def mock_components():
    return MagicMock(), MagicMock()


def test_renderer_initialization(mock_components):
    engine, repo = mock_components
    renderer = SolarDashboardRenderer(engine=engine, repository=repo)
    assert renderer.engine is engine
    assert renderer.repository is repo


def test_cache_logic_integration(mock_components):
    engine, repo = mock_components
    renderer = SolarDashboardRenderer(engine=engine, repository=repo)
    repo.get_standardized_data.return_value = {
        'hourly': 'hourly-fixture',
        'hsp_global': [5.0] * 12,
        'hsp_diffuse': [1.0] * 12,
        'metadata': {'source': 'NASA POWER', 'temporal_resolution': 'hourly'},
    }
    engine.calcular_projeto_solar.return_value = {
        'kWh/m²/dia': {
            'real': {'media': 5.0, 'mensal': [5.0] * 12},
            'referencia': {'media_sem_sombra': 5.2, 'mensal_sem_sombra': [5.2] * 12},
        },
        'perda_sombreamento_estimada': '4%',
        'detalhes': {'fonte': 'fixture'},
    }
    arguments = dict(
        lat=-7., lon=-35., inc=15, azi=0, alb=.2, h=1.,
        tec_chave='TOPCON', modo_bifacial=True, orientacao='Retrato',
        usar_obstaculo=False, config_obstaculo=None, nome_exibicao='Teste',
        provider_forcado='NASA POWER',
    )
    _load_provider_data.clear()
    try:
        renderer.renderizar_layout_comparativo(**arguments)
        renderer.renderizar_layout_comparativo(**arguments)
        # Cache is keyed by lat/lon/provider, instead of session_state.cache_api_data.
        repo.get_standardized_data.assert_called_once_with(
            -7., -35., force_provider='NASA POWER',
        )
        # Both project and horizontal reference were executed on each render.
        assert engine.calcular_projeto_solar.call_count == 4
    finally:
        _load_provider_data.clear()
