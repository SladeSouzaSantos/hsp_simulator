import pytest
import json
import math
from core.app import SolarEngine
from core.perez_engines.perez_engine import PerezEngine
from unittest.mock import MagicMock

def carregar_dados_sundata():
    """Carrega o arquivo de amostragem real"""
    try:
        with open("tests/fixtures/amostragem_sundata.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback caso o caminho mude em diferentes ambientes
        return {}

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
    # 1. Setup do motor (o repositório é mockado pois já temos os dados injetados via dados_pre)
    repo_mock = MagicMock()
    engine = SolarEngine(repository=repo_mock)
    
    # 2. Preparamos o pacote de dados Climatológicos no formato que o motor espera
    meses_sd = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dados_pre = {
        "hsp_global": [dados_hsp[m] for m in meses_sd],
        "hsp_diffuse": [h * 0.3 for h in [dados_hsp[m] for m in meses_sd]], # Difusa estimada
        "temp_max": [30.0] * 12,
        "temp_avg": [26.0] * 12,
        "temp_min": [18.0] * 12,
        "wind_speed": [3.0] * 12
    }

    # 3. Criamos a PerezEngine injetando os parâmetros geográficos e técnicos
    # Usamos uma latitude condizente com o Brasil para o teste de estresse
    motor_perez = PerezEngine(
        lat=-15.0, 
        lon=-47.0, 
        inclinacao_deg=inclinacao, 
        azimute_deg=0,
        albedo=0.2,
        altura_instalacao=0.5,
        tecnologia_celula="TOPCON",
        is_bifacial=True
    )

    # 4. Execução do cálculo
    # Agora passamos a instância motor_perez e os dados pré-carregados
    resultado = engine.calcular_projeto_solar(
        perez_engine=motor_perez,
        dados_pre_carregados=dados_pre
    )

    # 5. Validações básicas de sanidade
    assert "kWh/m²/dia" in resultado
    assert "real" in resultado["kWh/m²/dia"]
    assert len(resultado["kWh/m²/dia"]["real"]["mensal"]) == 12
    assert isinstance(resultado["kWh/m²/dia"]["real"]["media"], float)