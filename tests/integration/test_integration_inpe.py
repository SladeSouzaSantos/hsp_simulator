import pytest
import os
from services.providers.inpe_labren_provider import InpeLabrenProvider

def test_inpe_provider_integrity():
    """
    Valida a integridade do provedor INPE/LABREN.
    Verifica se o arquivo Parquet local é lido corretamente e se os dados são consistentes.
    """
    # 1. Setup do Provider
    provider = InpeLabrenProvider()
    
    # 2. Coordenadas de teste (Ex: São José dos Campos - Sede do INPE)
    lat, lon = -23.1791, -45.8872
    
    # 3. Execução da busca (Leitura do Parquet + Processamento)
    try:
        data = provider.get_solar_data(lat, lon)
    except FileNotFoundError:
        pytest.fail("Arquivo Parquet do INPE não encontrado na pasta data/inpe_labren/")
    except Exception as e:
        pytest.fail(f"Erro ao processar dados do INPE: {e}")

    # 4. Validações de Estrutura
    assert "hsp_global" in data, "O campo 'hsp_global' está ausente."
    assert len(data["hsp_global"]) == 12, "Deveria conter 12 meses de dados."
    assert "hsp_diffuse" in data, "O campo 'hsp_diffuse' está ausente."
    
    # 5. Validação de Sanidade Numérica (Valores típicos para o Brasil)
    for hsp in data["hsp_global"]:
        # O Brasil tem radiação alta, geralmente entre 3.0 e 7.0 HSP
        assert 2.0 <= hsp <= 8.5, f"Valor de HSP do INPE fora da curva esperada: {hsp}"

    # 6. Validação de Metadados e Fonte
    assert "metadata" in data
    assert "INPE/LABREN" in data["metadata"]["source"]
    assert "2017" in data["metadata"]["source"]
    
    print(f"\n✅ Integração INPE/LABREN OK! HSP Médio em SJC: {sum(data['hsp_global'])/12:.2f}")

def test_inpe_provider_out_of_bounds():
    """
    Verifica se o provedor levanta erro corretamente ao buscar coordenadas fora do Brasil.
    """
    provider = InpeLabrenProvider()
    lat, lon = 51.5074, -0.1278 # Londres
    
    with pytest.raises(ValueError, match="fora da cobertura"):
        provider.get_solar_data(lat, lon)

if __name__ == "__main__":
    test_inpe_provider_integrity()
    print("Teste de fora de cobertura...")
    test_inpe_provider_out_of_bounds()