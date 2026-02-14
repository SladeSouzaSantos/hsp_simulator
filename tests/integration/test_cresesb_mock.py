import pytest
import json
from unittest.mock import MagicMock
from services.solar_repository import SolarRepository

@pytest.fixture
def mock_cresesb_data():
    """Carrega o JSON de amostragem do SunData"""
    with open("tests/fixtures/amostragem_sundata.json", "r", encoding="utf-8") as f:
        return json.load(f)

def test_repository_com_dados_sundata(mock_cresesb_data):
    """
    Simula um provedor do SunData usando o JSON de Natal
    """
    # 1. Extraímos Natal (inclinação 0) e preparamos o retorno padronizado
    natal_0 = mock_cresesb_data["Natal"]["0"]
    meses_sd = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    dados_padronizados = {
        "hsp_global": [natal_0[m] for m in meses_sd],
        "hsp_diffuse": [1.0] * 12, # Valores fictícios para completar o contrato
        "temp_max": [30.0] * 12,
        "wind_speed": [2.0] * 12
    }

    # 2. Criamos o Mock do Provedor
    mock_provider = MagicMock()
    mock_provider.name = "MockProvider"
    mock_provider.get_solar_data.return_value = dados_padronizados

    # 3. Injetamos no Repositório
    repo = SolarRepository(providers=[mock_provider])

    # 4. Executamos
    resultado = repo.get_standardized_data(lat=-5.79, lon=-35.20)

    # 5. Validação: O valor de Janeiro em Natal deve ser 6.02
    assert resultado["hsp_global"][0] == 6.02
    assert len(resultado["hsp_global"]) == 12
    print(f"\n[DADOS REAIS] Natal validado com sucesso: {resultado['hsp_global'][0]} HSP")