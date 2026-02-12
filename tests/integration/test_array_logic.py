import pytest
import numpy as np
from core.app import SolarEngine
from unittest.mock import MagicMock

@pytest.fixture
def engine_setup():
    """
    Configura o motor com um Mock que retorna dados numéricos reais,
    evitando que o PerezEngine receba objetos MagicMock em cálculos matemáticos.
    """
    repo_mock = MagicMock()
    
    # Dados climatológicos reais (12 meses)
    # O motor acessa dados['hsp_global'][i] e dados['hsp_diffuse'][i]
    dados_fake = {
        "hsp_global": [5.0, 5.2, 5.5, 4.8, 4.2, 3.9, 4.1, 4.7, 5.3, 5.8, 5.6, 5.1],
        "hsp_diffuse": [1.2, 1.3, 1.4, 1.1, 1.0, 0.9, 1.0, 1.2, 1.3, 1.5, 1.4, 1.2],
        "temp_max": [30.0] * 12,
        "wind_speed": [2.0] * 12
    }
    
    # Garantimos que o mock retorne o dicionário de listas
    repo_mock.get_standardized_data.return_value = dados_fake
    
    return SolarEngine(repository=repo_mock)

def test_consistencia_sombra_objetos_identicos(engine_setup):
    """
    TESTE 1: Valida se o motor é determinístico.
    Placas na mesma posição sob o mesmo obstáculo devem ter resultados idênticos.
    """
    engine = engine_setup
    
    obstaculo = {
        "altura_obstaculo": 3.0,
        "distancia_obstaculo": 5.0,
        "largura_obstaculo": 4.0,
        "referencia_azimutal_obstaculo": 0
    }

    # Simulação de 3 placas do arranjo de 7
    res1 = engine.calcular_projeto_solar(lat=-23.5, lon=-46.6, inclinacao=20, azimute=0, config_obstaculo=obstaculo)
    res2 = engine.calcular_projeto_solar(lat=-23.5, lon=-46.6, inclinacao=20, azimute=0, config_obstaculo=obstaculo)
    res3 = engine.calcular_projeto_solar(lat=-23.5, lon=-46.6, inclinacao=20, azimute=0, config_obstaculo=obstaculo)

    # Extração das perdas (convertendo string "X.X%" para float)
    perda1 = float(res1["perda_sombreamento_estimada"].replace('%', ''))
    perda2 = float(res2["perda_sombreamento_estimada"].replace('%', ''))
    perda3 = float(res3["perda_sombreamento_estimada"].replace('%', ''))

    assert perda1 > 0, "O obstáculo deveria gerar alguma perda."
    assert perda1 == perda2 == perda3, "Placas idênticas divergiram no cálculo."

def test_estresse_arranjo_misto(engine_setup):
    """
    TESTE 2: Garante o isolamento térmico/lógico entre cálculos.
    Uma placa sombreada não pode 'contaminar' o resultado de uma placa no sol.
    """
    engine = engine_setup

    sombra_severa = {
        "altura_obstaculo": 10.0,
        "distancia_obstaculo": 1.0,
        "largura_obstaculo": 5.0,
        "referencia_azimutal_obstaculo": 0
    }

    # 1. Calcula placa com sombra severa
    res_sombra = engine.calcular_projeto_solar(lat=-23.5, lon=-46.6, inclinacao=20, azimute=0, config_obstaculo=sombra_severa)
    
    # 2. Calcula placa livre
    res_livre = engine.calcular_projeto_solar(lat=-23.5, lon=-46.6, inclinacao=20, azimute=0, config_obstaculo=None)

    perda_sombra = float(res_sombra["perda_sombreamento_estimada"].replace('%', ''))
    perda_livre = float(res_livre["perda_sombreamento_estimada"].replace('%', ''))

    assert perda_sombra > 40, "A sombra deveria ser drástica."
    assert perda_livre == 0.0, "ERRO: A sombra da placa anterior 'vazou' para o cálculo atual."
    assert res_sombra["media"] < res_livre["media"], "A média com sombra deve ser menor que a livre."