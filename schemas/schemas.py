from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ConfigObstaculo(BaseModel):
    altura_obstaculo: float = Field(ge=0)
    distancia_obstaculo: float = Field(gt=0)
    referencia_azimutal_obstaculo: float = Field(ge=0, le=360)
    largura_obstaculo: float = Field(default=10, gt=0)

class ConfigTecnicaBase(BaseModel):
    inclinacao_graus: float = Field(default=15, ge=0, le=90)
    azimute_graus: float = Field(default=0, ge=0, le=360,
        description='Geográfico: 0=N, 90=L, 180=S, 270=O')
    albedo_solo: float = Field(default=.2, ge=0, le=1)
    distancia_centro_modulo_chao: float = Field(default=.2, ge=0)
    tecnologia_celula: Literal['TOPCON','PERC','AL_BSF','HJT'] = 'TOPCON'
    is_bifacial: bool = False
    comprimento_modulo: float = Field(default=2.278, gt=0)
    largura_modulo: float = Field(default=1.134, gt=0)
    orientacao: Literal['Retrato','Paisagem'] = 'Retrato'
    config_obstaculo: Optional[ConfigObstaculo] = None
    modelo_transposicao: Literal['perez','haydavies','isotropic'] = 'perez'
    fonte_dados: Literal['auto','NASA POWER','PVGIS','INPE/LABREN Atlas 2017'] = 'auto'

class ProjetoSolarRequest(ConfigTecnicaBase):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class ItemArranjoRequest(ConfigTecnicaBase):
    id_placa: str = Field(min_length=1)

class ProjetoArranjoRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    itens: List[ItemArranjoRequest] = Field(min_length=1, max_length=500)

class DadosHSPReal(BaseModel):
    media: float
    mensal: List[float] = Field(min_length=12, max_length=12)

class DadosHSPReferencia(BaseModel):
    media_sem_sombra: float
    mensal_sem_sombra: List[float] = Field(min_length=12, max_length=12)

class UnidadeEnergia(BaseModel):
    real: DadosHSPReal
    referencia: DadosHSPReferencia

class DadosClimaticos(BaseModel):
    temp_max_mensal: List[Optional[float]] = Field(default_factory=list)
    temp_avg_mensal: List[Optional[float]] = Field(default_factory=list)
    temp_min_mensal: List[Optional[float]] = Field(default_factory=list)

class ProjetoSolarResponse(BaseModel):
    clima: DadosClimaticos
    hsp_unidade: UnidadeEnergia = Field(alias='kWh/m²/dia')
    perda_sombreamento_estimada: str
    detalhes: dict = Field(default_factory=dict)
    model_config = ConfigDict(populate_by_name=True)

class ItemArranjoResponse(BaseModel):
    id_placa: str
    hsp_unidade: UnidadeEnergia = Field(alias='kWh/m²/dia')
    perda_sombreamento_estimada: str
    detalhes: dict = Field(default_factory=dict)
    model_config = ConfigDict(populate_by_name=True)

class ArranjoSolarResponse(BaseModel):
    total_placas: int
    clima: DadosClimaticos
    resultados: List[ItemArranjoResponse]
