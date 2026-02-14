import pytest
from services.providers.pvgis_provider import PvgisProvider

def test_pvgis_provider_integrity():
    """
    Valida a integração real com a API do PVGIS.
    Verifica se a comunicação, o parsing e os dados estão consistentes.
    """
    # 1. Setup do Provider
    provider = PvgisProvider()
    
    # 2. Coordenadas de teste (Ex: Lisboa, Portugal - local nativo do PVGIS)
    lat, lon = 38.7223, -9.1393
    
    # 3. Execução da chamada real
    try:
        data = provider.get_solar_data(lat, lon)
    except Exception as e:
        pytest.fail(f"A API do PVGIS falhou ou está offline: {e}")

    # 4. Validações de Estrutura (Contrato de Dados)
    assert "hsp_global" in data, "O campo 'hsp_global' está ausente."
    assert len(data["hsp_global"]) == 12, "Deveria conter 12 meses de dados."
    assert "hsp_diffuse" in data, "O campo 'hsp_diffuse' está ausente."
    
    # 5. Validação de Sanidade Numérica
    # Radiação HSP média diária raramente é < 1.0 (inverno extremo) ou > 10.0
    for hsp in data["hsp_global"]:
        assert 0.5 <= hsp <= 10.0, f"Valor de HSP suspeito detectado: {hsp}"

    # 6. Validação de Metadados
    assert "metadata" in data
    assert "PVGIS" in data["metadata"]["source"]
    
    print(f"\n✅ Integração PVGIS OK! HSP Médio em Lisboa: {sum(data['hsp_global'])/12:.2f}")

if __name__ == "__main__":
    # Permite execução rápida via terminal
    test_pvgis_provider_integrity()