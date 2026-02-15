import pytest
from services.providers.nasa_power_provider import NasaPowerProvider

def test_nasa_provider_integrity():
    """
    Valida a integração real com a API NASA POWER.
    Verifica se a comunicação, o parsing e o fator de conversão estão corretos.
    """
    # 1. Setup do Provider
    provider = NasaPowerProvider()
    
    # 2. Coordenadas de teste (Ex: Natal, RN - Alta radiação)
    lat, lon = -5.7945, -35.2110
    
    # 3. Execução da chamada real
    try:
        data = provider.get_solar_data(lat, lon)
    except Exception as e:
        pytest.fail(f"A API da NASA falhou ou está offline: {e}")

    # 4. Validações de Estrutura (Contrato de Dados)
    assert "hsp_global" in data, "O campo 'hsp_global' está ausente."
    assert len(data["hsp_global"]) == 12, "Deveria conter 12 meses de dados."
    assert "hsp_diffuse" in data, "O campo 'hsp_diffuse' está ausente."
    assert "temp_max" in data, "Dados de temperatura ausentes."
    
    # 5. Validação de Sanidade Numérica
    # A NASA retorna kWh/m²/dia após o seu fator de correção (* 0.024)
    for hsp in data["hsp_global"]:
        assert 1.0 <= hsp <= 10.0, f"Valor de HSP da NASA fora da realidade física: {hsp}"

    # 6. Validação de Metadados
    assert "metadata" in data
    assert "NASA" in data["metadata"]["source"]
    
    print(f"\n✅ Integração NASA POWER OK! HSP Médio em Natal: {sum(data['hsp_global'])/12:.2f}")

if __name__ == "__main__":
    test_nasa_provider_integrity()