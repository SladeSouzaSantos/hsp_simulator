#import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_calculo_simples_sucesso():
    """Teste básico: Verifica se a rota principal responde corretamente"""
    payload = {
        "latitude": -7.562,
        "longitude": -37.688,
        "inclinacao_graus": 15,
        "azimute_graus": 0,
        "albedo_solo": 0.2,
        "distancia_centro_modulo_chao": 0.15,
        "tecnologia_celula": "TOPCON",
        "is_bifacial": True,
        "orientacao": "Retrato"
    }
    response = client.post("/calcular", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "kWh/m²/dia" in data
    assert "real" in data["kWh/m²/dia"]
    assert data["kWh/m²/dia"]["real"]["media"] > 0

def test_calculo_arranjo_cache_performance():
    """Teste de lote: Verifica se o cálculo de múltiplas placas funciona"""
    payload = {
        "latitude": -5.8125,
        "longitude": -35.1875,
        "itens": [
            {
                "id_placa": "P1",
                "inclinacao_graus": 10,
                "azimute_graus": 0,
                "albedo_solo": 0.2,
                "distancia_centro_modulo_chao": 0.5,
                "tecnologia_celula": "TOPCON",
                "is_bifacial": True
            },
            {
                "id_placa": "P2",
                "inclinacao_graus": 20,
                "azimute_graus": 0,
                "albedo_solo": 0.2,
                "distancia_centro_modulo_chao": 0.5,
                "tecnologia_celula": "TOPCON",
                "is_bifacial": True
            }
        ]
    }
    response = client.post("/calcular-arranjo", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_placas"] == 2
    assert len(data["resultados"]) == 2

def test_arredondamento_coordenadas():
    """Verifica se coordenadas levemente diferentes usam o mesmo dado (via lógica de 4 casas)"""
    # Se o sistema arredonda para 4 casas, essas duas coordenadas devem ser idênticas para o motor
    coord1 = {"latitude": -7.12344, "longitude": -35.12344}
    coord2 = {"latitude": -7.12341, "longitude": -35.12341}
    
    # Fazemos a primeira chamada (vai na NASA)
    res1 = client.post("/calcular", json={**coord1, "inclinacao_graus": 0, "azimute_graus": 0, "albedo_solo": 0.2, "distancia_centro_modulo_chao": 0.2})
    
    # Fazemos a segunda chamada (deve ser instantânea via cache)
    res2 = client.post("/calcular", json={**coord2, "inclinacao_graus": 0, "azimute_graus": 0, "albedo_solo": 0.2, "distancia_centro_modulo_chao": 0.2})
    
    assert res1.status_code == 200
    assert res2.status_code == 200
    # Como as coordenadas arredondadas são iguais, os resultados de HSP devem ser idênticos
    assert res1.json()["kWh/m²/dia"]["real"]["media"] == res2.json()["kWh/m²/dia"]["real"]["media"]