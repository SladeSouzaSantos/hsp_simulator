import pytest
import numpy as np
from core.app import SolarEngine
from core.perez_engines.perez_engine import PerezEngine
from unittest.mock import MagicMock

@pytest.fixture
def engine_setup():
    repo_mock = MagicMock()
    dados_fake = {
        "hsp_global": [5.0, 5.2, 5.5, 4.8, 4.2, 3.9, 4.1, 4.7, 5.3, 5.8, 5.6, 5.1],
        "hsp_diffuse": [1.2, 1.3, 1.4, 1.1, 1.0, 0.9, 1.0, 1.2, 1.3, 1.5, 1.4, 1.2],
        "temp_max": [30.0] * 12,
        "temp_avg": [25.0] * 12,
        "temp_min": [20.0] * 12,
        "wind_speed": [2.0] * 12
    }
    repo_mock.get_standardized_data.return_value = dados_fake
    return SolarEngine(repository=repo_mock)

def test_consistencia_sombra_objetos_identicos(engine_setup):
    engine = engine_setup
    
    # Criamos a engine de cálculo para injetar na SolarEngine
    perez = PerezEngine(lat=-23.5, lon=-46.6, inclinacao_deg=20, azimute_deg=0)

    obstaculo = {
        "altura_obstaculo": 3.0,
        "distancia_obstaculo": 5.0,
        "largura_obstaculo": 4.0,
        "referencia_azimutal_obstaculo": 0
    }

    # Passamos a perez_engine explicitamente
    res1 = engine.calcular_projeto_solar(perez_engine=perez, config_obstaculo=obstaculo)
    res2 = engine.calcular_projeto_solar(perez_engine=perez, config_obstaculo=obstaculo)

    perda1 = float(res1["perda_sombreamento_estimada"].replace('%', ''))
    perda2 = float(res2["perda_sombreamento_estimada"].replace('%', ''))

    assert perda1 > 0
    assert perda1 == perda2

def test_estresse_arranjo_misto(engine_setup):
    engine = engine_setup
    perez = PerezEngine(lat=-23.5, lon=-46.6, inclinacao_deg=20, azimute_deg=0)

    sombra_severa = {
        "altura_obstaculo": 10.0,
        "distancia_obstaculo": 1.0,
        "largura_obstaculo": 5.0,
        "referencia_azimutal_obstaculo": 0
    }

    # Cálculo 1: Com sombra
    res_sombra = engine.calcular_projeto_solar(perez_engine=perez, config_obstaculo=sombra_severa)
    
    # Cálculo 2: Sem sombra (Resetando o estado)
    res_livre = engine.calcular_projeto_solar(perez_engine=perez, config_obstaculo=None)

    perda_sombra = float(res_sombra["perda_sombreamento_estimada"].replace('%', ''))
    perda_livre = float(res_livre["perda_sombreamento_estimada"].replace('%', ''))

    assert perda_sombra > 40
    assert perda_livre == 0.0
    assert res_sombra["kWh/m²/dia"]["real"]["media"] < res_livre["kWh/m²/dia"]["real"]["media"]