from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional
from core.app import calcular_projeto_solar

app = FastAPI(
    title="HSP Simulator - Solar Engine API", 
    description="API para cálculo de irradiância solar e ganho bifacial",
    openapi_url="/openapi.json",
    root_path="/api"
)

# Definimos a estrutura do obstáculo para o Pydantic
class ObstacleConfig(BaseModel):
    height: float = Field(..., description="Altura do obstáculo em metros")
    distance: float = Field(..., description="Distância do painel ao obstáculo")
    azimuth: float = Field(..., description="Azimute do obstáculo (0-360)")

# Atualizamos o "Contrato" de entrada dos dados
class ProjetoSolarRequest(BaseModel):
    latitude: float = Field(..., json_schema_extra={"example": -7.562})
    longitude: float = Field(..., json_schema_extra={"example": -37.688})
    inclinacao_graus: int = Field(15, description="Ângulo de inclinação do painel (0 a 90)")
    azimute_graus: int = Field(0, description="Orientação (0=Norte, 180=Sul)")
    albedo_solo: float = Field(0.2, description="Fator de reflexão do solo")
    distancia_centro_modulo_chao: float = Field(0.2, description="Altura do centro da placa até o solo")
    tecnologia_celula: str = Field("TOPCON", description="Ex: TOPCON, AL BSF, PERC")
    is_bifacial: bool = Field(True, description="Define se o cálculo deve considerar ganho traseiro")
    obstacle_config: Optional[ObstacleConfig] = Field(None, description="Configuração de sombra (opcional)")

@app.post("/calcular")
def post_hsp(dados: ProjetoSolarRequest):
    # Validamos se o obstáculo realmente existe fisicamente
    config_sombra = None
    if dados.obstacle_config and dados.obstacle_config.height > 0:
        config_sombra = dados.obstacle_config.model_dump()

    """
    Recebe os dados via POST (Body JSON) e retorna os cálculos de HSP.
    """
    # Mapeamos o contrato da API para os argumentos da função core
    return calcular_projeto_solar(
        lat=dados.latitude, 
        lon=dados.longitude, 
        inclinacao=dados.inclinacao_graus, 
        azimute=dados.azimute_graus, 
        albedo=dados.albedo_solo, 
        altura=dados.distancia_centro_modulo_chao, 
        tecnologia=dados.tecnologia_celula,
        is_bifacial=dados.is_bifacial,
        obstacle_config=config_sombra,
        formato="dict"
    )