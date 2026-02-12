import pytest
import json
import math
from core.app import SolarEngine
from unittest.mock import MagicMock

def carregar_dados_sundata():
    """Carrega o arquivo de amostragem real"""
    with open("tests/fixtures/amostragem_sundata.json", "r", encoding="utf-8") as f:
        return json.load(f)

# Criamos uma lista de casos de teste dinamicamente a partir do JSON
sundata = carregar_dados_sundata()
casos_teste = []
for cidade, inclinacoes in sundata.items():
    for inc_str, valores in inclinacoes.items():
        casos_teste.append((cidade, int(inc_str), valores))

@pytest.mark.parametrize("cidade, inclinacao, dados_hsp", casos_teste)
def test_estresse_motor_com_cidades_reais(cidade, inclinacao, dados_hsp):
    """
    Testa se o motor de cálculo processa corretamente dados de cidades reais
    em diferentes inclinações sem gerar erros numéricos.
    """
    # 1. Setup do motor (o repositório é mockado pois já temos os dados)
    repo_mock = MagicMock()
    engine = SolarEngine(repository=repo_mock)
    
    # 2. Preparamos o pacote de dados Climatológicos no formato que o motor espera
    meses_sd = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dados_pre = {
        "hsp_global": [dados_hsp[m] for m in meses_sd],
        "hsp_diffuse": [h * 0.3 for h in [dados_hsp[m] for m in meses_sd]], # Difusa estimada
        "temp_max": [30.0] * 12,
        "wind_speed": [3.0] * 12
    }

    # 3. Execução do cálculo (Coordenadas fictícias para a cidade)
    # Usamos uma latitude condizente com o Brasil para evitar problemas de hemisfério
    resultado = engine.calcular_projeto_solar(
        lat=-15.0, lon=-47.0, 
        inclinacao=inclinacao, 
        azimute=0, 
        albedo=0.2, 
        altura_instalacao=0.5,
        tecnologia="TOPCON",
        is_bifacial=True,
        dados_pre_carregados=dados_pre
    )

    # 4. Asserts de Sanidade
    assert resultado["media"] > 0, f"Erro em {cidade} ({inclinacao}°): Média zero ou negativa"
    assert not math.isnan(resultado["media"]), f"Erro em {cidade}: Resultado gerou NaN"
    assert len(resultado["mensal"]) == 12
    
    # Verificação de lógica: se tem inclinação e azimute 0, 
    # a perda de sombra deve ser "0%" se config_obstaculo é None
    assert "perda_sombreamento_estimada" in resultado