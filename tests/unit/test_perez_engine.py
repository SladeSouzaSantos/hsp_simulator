import pytest
import numpy as np
from core.perez_engine import PerezEngine

@pytest.fixture
def base_params():
    return {
        "lat": -7.0,
        "is_bifacial": True,
        "fator_bifacial": 0.8,
        "albedo": 0.2,
        "altura_instalacao": 1.0,
        "comprimento_modulo": 2.278,
        "largura_modulo": 1.134
    }

def test_ganho_bifacial_zero_quando_desativado(base_params):
    # Criamos os motores
    params_mono = base_params.copy()
    params_mono["is_bifacial"] = False
    engine_mono = PerezEngine(**params_mono)
    engine_bi = PerezEngine(**base_params)

    # Criamos dados para os 12 meses (essencial para evitar IndexError)
    dados_12_meses = {
        "hsp_global": [5.0] * 12,
        "hsp_diffuse": [1.0] * 12,
        "temp_max": [30.0] * 12,
        "wind_speed": [2.0] * 12
    }

    # ORDEM CORRETA: (dados, inclinacao, azimute)
    output_mono = engine_mono.calcular_hsp_corrigido_inc_azi(dados_12_meses, 15, 0)
    output_bi = engine_bi.calcular_hsp_corrigido_inc_azi(dados_12_meses, 15, 0)

    assert output_bi["media"] > output_mono["media"], "O ganho bifacial deveria aumentar a média"

def test_perez_com_inclinacao_zero(base_params):
    engine = PerezEngine(**base_params)
    hsp_referencia = 6.0
    
    dados_12_meses = {
        "hsp_global": [hsp_referencia] * 12,
        "hsp_diffuse": [1.2] * 12,
        "temp_max": [25.0] * 12,
        "wind_speed": [3.0] * 12
    }

    # Usando argumentos nomeados para não ter erro de ordem
    res = engine.calcular_hsp_corrigido_inc_azi(
        dados=dados_12_meses, 
        inclinacao_deg=0, 
        azimute_deg=0
    )
    
    # Com inclinação 0 e bifacial ativo, a média deve ser no mínimo o valor horizontal
    assert res["media"] >= hsp_referencia