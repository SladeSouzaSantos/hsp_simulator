"""Test API contract with a deterministic fake engine/repository (no internet)."""
from fastapi.testclient import TestClient
from api import app, get_engine

class FakeSolarEngine:
    def calcular_projeto_solar(self, eng, **kwargs):
        return {'clima': {'temp_max_mensal':[30]*12,'temp_avg_mensal':[25]*12,
                          'temp_min_mensal':[20]*12},
                'kWh/m²/dia': {'real':{'media':5.7,'mensal':[5.7]*12},
                 'referencia':{'media_sem_sombra':5.8,'mensal_sem_sombra':[5.8]*12}},
                'perda_sombreamento_estimada':'2.0%', 'detalhes':{'fonte':'fixture'}}


def test_calcular_contract():
    app.dependency_overrides[get_engine]=lambda:FakeSolarEngine()
    try:
        r=TestClient(app).post('/calcular',json={'latitude':-5.79,'longitude':-35.21,
             'inclinacao_graus':15,'azimute_graus':90})
        assert r.status_code==200, r.text
        assert r.json()['kWh/m²/dia']['real']['media']==5.7
    finally:
        app.dependency_overrides.clear()

def test_invalid_coordinates_rejected():
    r=TestClient(app).post('/calcular',json={'latitude':-150,'longitude':-35})
    assert r.status_code==422

def test_health():
    assert TestClient(app).get('/health').status_code==200
