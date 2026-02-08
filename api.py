from fastapi import FastAPI
from pydantic import BaseModel, Field
from core.app import calcular_projeto_solar

app = FastAPI(title="HSP Simulator - Solar Engine API", description="API para cálculo de irradiância solar e ganho bifacial")

# Definimos o "Contrato" de entrada dos dados
class ProjetoSolarRequest(BaseModel):
    latitude: float = Field(..., example=-7.562)
    longitude: float = Field(..., example=-37.688)
    inclinacao_graus: int = Field(15, description="Ângulo de inclinação do painel (0 a 90)")
    azimute_graus: int = Field(0, description="Orientação (0=Norte, 180=Sul)")
    albedo_solo: float = Field(0.2, description="Fator de reflexão do solo")
    distancia_centro_modulo_chao: float = Field(0.2, description="Altura do centro da placa até o solo em metros")
    tecnologia_celula: str = Field("TOPCON", description="Ex: TOPCON, PERC, MONO-PERC")

@app.post("/calcular")
def post_hsp(dados: ProjetoSolarRequest):
    """
    Recebe os dados via POST (Body JSON) e retorna os cálculos de HSP.
    """
    # Convertemos o objeto 'dados' em um dicionário para passar para a função
    return calcular_projeto_solar(
        lat=dados.latitude, 
        lon=dados.longitude, 
        inclinacao=dados.inclinacao_graus, 
        azimute=dados.azimute_graus, 
        albedo=dados.albedo_solo, 
        altura=dados.distancia_centro_modulo_chao, 
        tecnologia=dados.tecnologia_celula, 
        formato="dict"
    )