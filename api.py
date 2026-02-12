from fastapi import Body, FastAPI, HTTPException
from services.providers import NasaPowerProvider
from services.solar_repository import SolarRepository
from schemas.schemas import ProjetoSolarRequest, ProjetoSolarResponse, ProjetoArranjoRequest, ArranjoSolarResponse
from core.app import SolarEngine

app = FastAPI(
    title="HSP Simulator - Solar Engine API", 
    description="API para cálculo de irradiância solar, ganho bifacial e sombreamento por obstáculos.",
    openapi_url="/openapi.json",
    root_path="/api"
)

repo = SolarRepository(provider=NasaPowerProvider())
engine = SolarEngine(repository=repo)

@app.post("/calcular", response_model=ProjetoSolarResponse, summary="Calcula HSP Corrigido",
    description="Calcula a média de HSP considerando inclinação, azimute, ganho bifacial e sombras."
)
def post_hsp(
    dados: ProjetoSolarRequest = Body(
        ...,
        openapi_examples={
            "Cenário Horizonte Livre": {
                "summary": "Sem Sombra",
                "description": "Cálculo padrão sem obstáculos próximos.",
                "value": {
                    "latitude": -7.562,
                    "longitude": -37.688,
                    "inclinacao_graus": 15,
                    "azimute_graus": 0,
                    "albedo_solo": 0.2,
                    "distancia_centro_modulo_chao": 0.15,
                    "tecnologia_celula": "TOPCON",
                    "is_bifacial": True,
                    "comprimento_modulo": 2.278,
                    "largura_modulo": 1.134,
                    "orientacao": "Retrato"
                }
            },
            "Cenário com Muro": {
                "summary": "Com Sombra",
                "description": "Simula um muro de 4m de altura posicionado a 2m do painel.",
                "value": {
                    "latitude": -5.8125,
                    "longitude": -35.1875,
                    "inclinacao_graus": 15,
                    "azimute_graus": 0,
                    "albedo_solo": 0.2,
                    "distancia_centro_modulo_chao": 0.15,
                    "tecnologia_celula": "TOPCON",
                    "is_bifacial": True,
                    "comprimento_modulo": 2.278,
                    "largura_modulo": 1.134,
                    "orientacao": "Retrato",
                    "config_obstaculo": {
                        "altura_obstaculo": 4.0,
                        "distancia_obstaculo": 2.0,
                        "referencia_azimutal_obstaculo": 0.0,
                        "largura_obstaculo": 4.0
                    }
                }
            }
        }
    )
):
    try:
        # Lógica de extração do obstáculo
        config_sombra = None
        if dados.config_obstaculo and dados.config_obstaculo.altura_obstaculo > 0:
            config_sombra = dados.config_obstaculo.model_dump()

        # Chamada do core
        res = engine.calcular_projeto_solar(
            lat=dados.latitude, 
            lon=dados.longitude, 
            inclinacao=dados.inclinacao_graus, 
            azimute=dados.azimute_graus, 
            albedo=dados.albedo_solo, 
            altura_instalacao=dados.distancia_centro_modulo_chao, 
            tecnologia=dados.tecnologia_celula,
            is_bifacial=dados.is_bifacial,
            comprimento_modulo=dados.comprimento_modulo,
            largura_modulo=dados.largura_modulo,
            orientacao=dados.orientacao,
            config_obstaculo=config_sombra,
            formato="dict"
        )

        return {
            "kWh/m²/dia": {
                "real": {
                    "media": res["media"],
                    "mensal": res["mensal"],
                },
                "referencia": {
                    "media_sem_sombra": res["media_sem_sombra"],
                    "mensal_sem_sombra": res["mensal_sem_sombra"],
                }
            },
            "perda_sombreamento_estimada": res["perda_sombreamento_estimada"]
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/calcular-arranjo", response_model=ArranjoSolarResponse, summary="Cálculo em Lote (Com Cache)")
def post_arranjo(
    dados: ProjetoArranjoRequest = Body(
        ...,
        openapi_examples={
            "Arranjo Complexo": {
                "summary": "Múltiplas placas com configurações distintas",
                "value": {
                    "latitude": -5.8125,
                    "longitude": -35.1875,
                    "itens": [
                        {
                            "id_placa": "Fileira_Norte_01",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.0,
                                "referencia_azimutal_obstaculo": 180.0,
                                "largura_obstaculo": 10.0
                            }
                        },
                        {
                            "id_placa": "Fileira_Central",
                            "inclinacao_graus": 20,
                            "azimute_graus": 90,
                            "albedo_solo": 0.5,
                            "distancia_centro_modulo_chao": 0.2,
                            "tecnologia_celula": "PERC",
                            "is_bifacial": True,
                            "config_obstaculo": None
                        },
                        {
                            "id_placa": "Fileira_Sul_01",
                            "inclinacao_graus": 15,
                            "azimute_graus": 180,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.0,
                                "referencia_azimutal_obstaculo": 0.0,
                                "largura_obstaculo": 10.0
                            }
                        },
                    ]
                }
            },
            "Arranjo Enfileirada Complexo": {
                "summary": "Múltiplas placas enfileiradas (Obstáculo único de 4m)",
                "value": {
                    "latitude": -5.8125,
                    "longitude": -35.1875,
                    "itens": [
                        {
                            "id_placa": "Placa_01_Esq_Fora",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.45,
                                "referencia_azimutal_obstaculo": 345.0,
                                "largura_obstaculo": 4.0
                            }
                        },
                        {
                            "id_placa": "Placa_02_Centro_Esq",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.0,
                                "referencia_azimutal_obstaculo": 0.0,
                                "largura_obstaculo": 4.0
                            }
                        },
                        {
                            "id_placa": "Placa_03_Centro_Meio",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.0,
                                "referencia_azimutal_obstaculo": 0.0,
                                "largura_obstaculo": 4.0
                            }
                        },
                        {
                            "id_placa": "Placa_04_Centro_Ref",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.0,
                                "referencia_azimutal_obstaculo": 0.0,
                                "largura_obstaculo": 4.0
                            }
                        },
                        {
                            "id_placa": "Placa_05_Dir_Quina",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 2.42,
                                "referencia_azimutal_obstaculo": 12.8,
                                "largura_obstaculo": 4.0
                            }
                        },
                        {
                            "id_placa": "Placa_06_Dir_Longe",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 3.48,
                                "referencia_azimutal_obstaculo": 26.5,
                                "largura_obstaculo": 4.0
                            }
                        },
                        {
                            "id_placa": "Placa_12_Dir_Extrema",
                            "inclinacao_graus": 15,
                            "azimute_graus": 0,
                            "albedo_solo": 0.2,
                            "distancia_centro_modulo_chao": 0.5,
                            "tecnologia_celula": "TOPCON",
                            "is_bifacial": True,
                            "config_obstaculo": {
                                "altura_obstaculo": 4.0,
                                "distancia_obstaculo": 11.12,
                                "referencia_azimutal_obstaculo": 65.5,
                                "largura_obstaculo": 4.0
                            }
                        }
                    ]
                }
            }
        }
    )
):
    """
    Analisa múltiplas placas/fileiras para a mesma coordenada.
    Mantém a otimização de UMA chamada à API da NASA para todo o lote.
    """
    try:
        resultados = engine.calcular_arranjo_completo(
            lat=dados.latitude, 
            lon=dados.longitude, 
            itens=dados.itens
        )
        
        return {
            "total_placas": len(resultados),
            "resultados": resultados
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))