import pytest
from services.deps import Dependencies

def test_full_solar_stack_integration():
    """Valida se o Dependencies monta o Repo e se o Repo busca dados do INPE com sucesso."""
    # Uso da classe central de dependências
    repo = Dependencies.get_solar_repository()
    
    # Coordenadas de SP
    lat, lon = -23.5505, -46.6333
    
    # Execução através do Repositório (Testando a orquestração)
    data = repo.get_standardized_data(lat, lon)
    
    assert "hsp_global" in data
    assert "INPE/LABREN" in data["metadata"]["source"] # Garante que priorizou o INPE no BR
    assert 4.0 <= (sum(data["hsp_global"])/12) <= 5.0
    print(f"\n✅ Sucesso: Dados carregados via {data['metadata']['source']}")