import pytest
from core.shadow_engine import ShadowEngine

@pytest.fixture
def engine():
    return ShadowEngine()

def test_sombra_meio_dia_perfeita(engine):
    """Ao meio-dia (sol a 90°), não deve haver sombra projetada no chão"""
    perda = engine.estimar_perda_sombreamento(
        altitude_sol_deg=90, 
        azimute_sol_deg=0, 
        config_obstaculo={'altura_obstaculo': 10, 'distancia_obstaculo': 2}
    )
    assert perda == 0.0

def test_sombra_total_horizonte(engine):
    """Com o sol a 0° (nascendo/pondo atrás do muro), a perda deve ser máxima"""
    # Simulando muro de 5m a 1m de distância
    config = {
        'altura_obstaculo': 5.0,
        'distancia_obstaculo': 1.0,
        'referencia_azimutal_obstaculo': 0.0,
        'largura_obstaculo': 10.0
    }
    perda = engine.estimar_perda_sombreamento(
        altitude_sol_deg=1, # Sol bem baixo
        azimute_sol_deg=0, 
        config_obstaculo=config
    )
    assert perda == 1.0

def test_sol_fora_da_largura_do_obstaculo(engine):
    """Se o sol estiver lateralmente longe do obstáculo, não deve haver perda"""
    config = {
        'altura_obstaculo': 5.0,
        'distancia_obstaculo': 2.0,
        'referencia_azimutal_obstaculo': 0.0, # Muro no Norte
        'largura_obstaculo': 2.0
    }
    # Sol a 90° de azimute (Leste), enquanto o muro está a 0° (Norte)
    perda = engine.estimar_perda_sombreamento(
        altitude_sol_deg=20, 
        azimute_sol_deg=90, 
        config_obstaculo=config
    )
    assert perda == 0.0

def test_obstaculo_mais_baixo_que_o_painel(engine):
    """Se o muro for mais baixo que a instalação do painel, a sombra não atinge"""
    perda = engine.estimar_perda_sombreamento(
        altitude_sol_deg=10,
        azimute_sol_deg=0,
        altura_instalacao_modulo=2.0, # Painel alto
        config_obstaculo={'altura_obstaculo': 1.0} # Muro baixo
    )
    assert perda == 0.0