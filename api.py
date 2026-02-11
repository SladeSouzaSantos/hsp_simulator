from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from typing import Optional, List

from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService
from core.app import calcular_projeto_solar

app = FastAPI(
    title="HSP Simulator - Solar Engine API", 
    description="API para cálculo de irradiância solar, ganho bifacial e sombreamento por obstáculos.",
    openapi_url="/openapi.json",
    root_path="/api"
)

# --- MODELOS DE RESPOSTA (Para documentação no Swagger) ---
class ProjetoSolarResponse(BaseModel):
    media: float = Field(..., title="Média HSP", description="Média anual de Horas de Sol Pleno")
    mensal: List[float] = Field(..., title="HSP Mensal", description="Lista com os 12 valores mensais de HSP")
    perda_sombreamento_estimada: str = Field(..., title="Perda de Sombra", description="Percentual estimado de perda por obstrução")

class ItemArranjoResponse(BaseModel):
    id_placa: str = Field(..., title="ID")
    hsp_media: float = Field(..., title="HSP Médio")
    perda_sombra: str = Field(..., title="Perda de Sombra (%)")

class ArranjoSolarResponse(BaseModel):
    total_placas: int = Field(..., title="Total de Itens")
    resultados: List[ItemArranjoResponse]

# --- MODELOS DE ENTRADA ---
class ConfigObstaculo(BaseModel):
    altura_obstaculo: float = Field(
        ..., title="Altura do Obstáculo", description="Altura total do objeto em metros"
    )
    distancia_obstaculo: float = Field(
        ..., title="Distância do Obstáculo", description="Vão livre horizontal até a borda do painel (m)"
    )
    referencia_azimutal_obstaculo: float = Field(
        ..., title="Azimute do Obstáculo", description="Direção central do objeto (0=N, 180=S)"
    )
    largura_obstaculo: float = Field(
        10.0, title="Largura do Obstáculo", description="Extensão lateral da face do objeto (m)"
    )

class ItemArranjoRequest(BaseModel):
    id_placa: str = Field(..., title="Identificador", example="Modulo_01")
    distancia_obstaculo: float = Field(..., title="Distância do Objeto (m)", example=2.5)

class ProjetoSolarRequest(BaseModel):
    latitude: float = Field(..., title="Latitude", json_schema_extra={"example": -7.562})
    longitude: float = Field(..., title="Longitude", json_schema_extra={"example": -37.688})
    inclinacao_graus: int = Field(
        15, title="Inclinação", description="Ângulo de inclinação do painel (0 a 90°)"
    )
    azimute_graus: int = Field(
        0, title="Azimute", description="Orientação do painel (0=Norte, 180=Sul)"
    )
    albedo_solo: float = Field(
        0.2, title="Albedo", description="Fator de reflexão do solo (ex: 0.2 para grama)"
    )
    distancia_centro_modulo_chao: float = Field(
        0.15, title="Altura de Instalação", description="Altura do centro do módulo até o solo (m)"
    )
    tecnologia_celula: str = Field(
        "TOPCON", title="Tecnologia", description="Tipo de célula (TOPCON, PERC, AL BSF)"
    )
    is_bifacial: bool = Field(
        True, title="Bifacialidade", description="Habilitar cálculo de face traseira"
    )
    comprimento_modulo: float = Field(
        2.278, title="Comprimento", description="Lado maior do painel em metros"
    )
    largura_modulo: float = Field(
        1.134, title="Largura", description="Lado menor do painel em metros"
    )
    orientacao: str = Field(
        "Retrato", title="Orientação", description="Posicionamento: 'Retrato' ou 'Paisagem'"
    )
    config_obstaculo: Optional[ConfigObstaculo] = Field(
        None, title="Configuração de Sombra", description="Dicionário com dados do obstáculo"
    )

class ProjetoArranjoRequest(BaseModel):
    latitude: float = Field(..., example=-7.562)
    longitude: float = Field(..., example=-37.688)
    inclinacao_graus: int = Field(15)
    azimute_graus: int = Field(0)
    tecnologia_celula: str = Field("TOPCON")
    # Dados comuns do obstáculo fixo (exceto a distância que varia por item)
    altura_obstaculo: float = Field(..., description="Altura do muro/prédio")
    referencia_azimutal_obstaculo: float = Field(..., description="Azimute do objeto")
    # Lista de placas/fileiras para analisar
    itens: List[ItemArranjoRequest]

# --- ENDPOINTS ---

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
    # Lógica de extração do obstáculo
    config_sombra = None
    if dados.config_obstaculo and dados.config_obstaculo.altura_obstaculo > 0:
        config_sombra = dados.config_obstaculo.model_dump()

    # Chamada do core
    return calcular_projeto_solar(
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

@app.post("/calcular-arranjo", response_model=ArranjoSolarResponse, summary="Cálculo em Lote (Com Cache)")
def post_arranjo(
    dados: ProjetoArranjoRequest = Body(
        ...,
        openapi_examples={
            "Arranjo de 3 Fileiras": {
                "summary": "Estudo de 3 fileiras com distâncias diferentes",
                "value": {
                    "latitude": -7.562,
                    "longitude": -37.688,
                    "inclinacao_graus": 15,
                    "azimute_graus": 0,
                    "tecnologia_celula": "TOPCON",
                    "altura_obstaculo": 3.5,
                    "referencia_azimutal_obstaculo": 0,
                    "itens": [
                        {"id_placa": "Fileira_01", "distancia_obstaculo": 2.0},
                        {"id_placa": "Fileira_02", "distancia_obstaculo": 4.5},
                        {"id_placa": "Fileira_03", "distancia_obstaculo": 7.0}
                    ]
                }
            }
        }
    )
):
    """
    Analisa múltiplas placas/fileiras para a mesma coordenada.
    Faz apenas UMA chamada à API da NASA para todo o lote.
    """
    # 1. Busca e processa os dados da NASA apenas UMA VEZ para o lote
    gateway = NasaPowerGateway(dados.latitude, dados.longitude)
    raw_data = gateway.fetch_climatology()
    dados_limpos = SolarDataService.standardize_data(raw_data)

    resultados_finais = []

    # 2. Processa cada item do arranjo usando os dados em cache (dados_limpos)
    for item in dados.itens:
        # Monta a config de sombra específica para este item (variando a distância)
        config_sombra = {
            "altura_obstaculo": dados.altura_obstaculo,
            "distancia_obstaculo": item.distancia_obstaculo,
            "referencia_azimutal_obstaculo": dados.referencia_azimutal_obstaculo,
            "largura_obstaculo": 15.0 # Largura generosa padrão
        }

        # Chama o core injetando os dados_pre_carregados
        res = calcular_projeto_solar(
            lat=dados.latitude,
            lon=dados.longitude,
            inclinacao=dados.inclinacao_graus,
            azimute=dados.azimute_graus,
            albedo=0.2,
            altura_instalacao=1.5,
            tecnologia=dados.tecnologia_celula,
            is_bifacial=True,
            dados_pre_carregados=dados_limpos,
            config_obstaculo=config_sombra
        )

        resultados_finais.append({
            "id_placa": item.id_placa,
            "hsp_media": res["media"],
            "perda_sombra": res["perda_sombreamento_estimada"]
        })

    return {
        "total_placas": len(resultados_finais),
        "resultados": resultados_finais
    }