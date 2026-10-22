"""Integration tests for repeated panels and deterministic obstruction handling."""
import pytest
from unittest.mock import MagicMock

pytest.importorskip('pvlib')
from core.app import SolarEngine
from core.perez_engines.perez_engine import PerezEngine
from tests.fixtures.hourly_weather import climate_fixture


@pytest.fixture(scope='module')
def annual_climate():
    return climate_fixture(-23.5, -46.6)


@pytest.fixture
def engine_setup(annual_climate):
    repo = MagicMock()
    repo.get_standardized_data.return_value = annual_climate
    return SolarEngine(repository=repo)


def test_consistencia_sombra_objetos_identicos(engine_setup):
    motor = PerezEngine(lat=-23.5, lon=-46.6, inclinacao_deg=20, azimute_deg=0)
    obstaculo = {
        'altura_obstaculo': 3.0, 'distancia_obstaculo': 5.0,
        'largura_obstaculo': 4.0, 'referencia_azimutal_obstaculo': 0,
    }
    a = engine_setup.calcular_projeto_solar(motor, config_obstaculo=obstaculo)
    b = engine_setup.calcular_projeto_solar(motor, config_obstaculo=obstaculo)
    assert a == b
    assert float(a['perda_sombreamento_estimada'].rstrip('%')) >= 0


def test_estresse_arranjo_misto(engine_setup):
    motor = PerezEngine(lat=-23.5, lon=-46.6, inclinacao_deg=20, azimute_deg=0)
    # Intentionally broad obstacle directly in the northern exposure.
    obstaculo = {
        'altura_obstaculo': 10.0, 'distancia_obstaculo': 1.0,
        'largura_obstaculo': 20.0, 'referencia_azimutal_obstaculo': 0,
    }
    sombreado = engine_setup.calcular_projeto_solar(motor, config_obstaculo=obstaculo)
    livre = engine_setup.calcular_projeto_solar(motor, config_obstaculo=None)
    perda_sombra = float(sombreado['perda_sombreamento_estimada'].rstrip('%'))
    assert 0 < perda_sombra <= 100
    assert livre['perda_sombreamento_estimada'] == '0.0%'
    assert sombreado['kWh/m²/dia']['real']['media'] < livre['kWh/m²/dia']['real']['media']
    # Shadow must not modify the independent unconstrained baseline.
    assert sombreado['kWh/m²/dia']['referencia'] == livre['kWh/m²/dia']['referencia']
