import pytest
from services.deps import Dependencies
from unittest.mock import patch

def test_repository_respects_dependency_order():
    """
    Garante que o repositório respeita a ordem de prioridade definida 
    em Dependencies.get_solar_repository() sem fixar nomes de provedores.
    """
    repo = Dependencies.get_solar_repository()
    providers = repo.providers
    
    assert len(providers) > 0, "O repositório deveria ter provedores injetados."
    
    # Espionamos o primeiro provedor da lista injetada
    with patch.object(providers[0], 'get_solar_data', wraps=providers[0].get_solar_data) as spy_primeiro:
        lat, lon = -5.79, -35.21
        repo.get_standardized_data(lat, lon)
        
        # O teste passa se o primeiro da lista foi o primeiro a ser chamado
        assert spy_primeiro.called, f"O provedor {providers[0].__class__.__name__} deveria ter sido o primeiro."

def test_repository_full_fallback_chain():
    """
    Valida se o repositório percorre a lista até encontrar um que funcione.
    Força uma falha fake no primeiro para ver se o segundo assume.
    """
    repo = Dependencies.get_solar_repository()
    providers = repo.providers
    
    if len(providers) < 2:
        pytest.skip("Necessário pelo menos 2 provedores para testar fallback.")

    # Simulamos erro no primeiro da lista (independente de quem for)
    with patch.object(providers[0], 'get_solar_data', side_effect=ValueError("Falha Simulada")):
        # Espionamos o segundo
        with patch.object(providers[1], 'get_solar_data', wraps=providers[1].get_solar_data) as spy_segundo:
            
            lat, lon = -5.79, -35.21
            data = repo.get_standardized_data(lat, lon)
            
            # O segundo deve ter sido chamado e os dados devem ter vindo dele
            assert spy_segundo.called
            assert data is not None

def test_repository_return_structure():
    """
    Garante que o repositório entrega o contrato de dados correto,
    não importa qual provedor responda.
    """
    repo = Dependencies.get_solar_repository()
    
    # Coordenadas de teste (São Paulo)
    lat, lon = -23.55, -46.63
    
    data = repo.get_standardized_data(lat, lon)
    
    # 1. Validamos o contrato (Interface)
    assert "hsp_global" in data
    assert "hsp_diffuse" in data
    assert "metadata" in data
    assert len(data["hsp_global"]) == 12
    
    # 2. Validamos que existe uma fonte registrada (Independente de qual seja)
    assert "source" in data["metadata"]
    print(f"\n✅ Repositório respondeu via: {data['metadata']['source']}")

def test_repository_fallback_logic():
    """
    Testa se o repositório sobrevive a coordenadas onde um provedor falha.
    Ex: Lisboa (Onde o INPE falha, mas NASA/PVGIS funcionam).
    """
    repo = Dependencies.get_solar_repository()
    
    # Lisboa está fora do Atlas INPE
    lat, lon = 38.72, -9.13
    
    data = repo.get_standardized_data(lat, lon)
    
    # Se chegamos aqui sem erro, o fallback funcionou!
    assert "hsp_global" in data
    # Garantimos que ele NÃO usou o INPE (que deveria falhar lá)
    assert "INPE" not in data["metadata"]["source"]
    print(f"✅ Fallback funcionou para Lisboa via: {data['metadata']['source']}")