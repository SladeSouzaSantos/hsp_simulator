"""FastAPI application, compatible with the original JSON payload and response."""
import requests
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from core.app import SolarEngine
from core.solar_engine_factory import SolarPerezEngineFactory
from services.deps import Dependencies
from schemas.schemas import ProjetoSolarRequest, ProjetoSolarResponse, ProjetoArranjoRequest, ArranjoSolarResponse

app = FastAPI(title='HSP Simulator — corrected hourly transposition', version='2.0.0',
              description='Perez/Hay-Davies hourly solar transposition with explicit sources and units',
              root_path='/api')

def get_engine():
    return SolarEngine(Dependencies.get_solar_repository())

@app.get('/health')
def health():
    return {'status':'ok','engine':'hourly-pvlib', 'version':'2.0.0'}

def request_engine(d):
    cls = SolarPerezEngineFactory.get_engine_type()
    return cls(lat=d.latitude, lon=d.longitude, inclinacao_deg=d.inclinacao_graus,
        azimute_deg=d.azimute_graus, is_bifacial=d.is_bifacial,
        tecnologia_celula=d.tecnologia_celula, albedo=d.albedo_solo,
        altura_instalacao=d.distancia_centro_modulo_chao,
        comprimento_modulo=d.comprimento_modulo, largura_modulo=d.largura_modulo,
        orientacao=d.orientacao, model=d.modelo_transposicao)

@app.post('/calcular', response_model=ProjetoSolarResponse)
def calcular(dados: ProjetoSolarRequest = Body(...), engine: SolarEngine=Depends(get_engine)):
    try:
        eng = request_engine(dados)
        return engine.calcular_projeto_solar(eng,
            config_obstaculo=dados.config_obstaculo.model_dump() if dados.config_obstaculo else None,
            force_provider=None if dados.fonte_dados=='auto' else dados.fonte_dados)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e
    except (RuntimeError, OSError, requests.RequestException) as e:
        raise HTTPException(503, detail=str(e)) from e

@app.post('/calcular-arranjo', response_model=ArranjoSolarResponse)
def calcular_arranjo(dados: ProjetoArranjoRequest = Body(...), engine: SolarEngine=Depends(get_engine)):
    try:
        return engine.calcular_arranjo_completo(dados.latitude,dados.longitude,dados.itens)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e
    except (RuntimeError, OSError, requests.RequestException) as e:
        raise HTTPException(503, detail=str(e)) from e
