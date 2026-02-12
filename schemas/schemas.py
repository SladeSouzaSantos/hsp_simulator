from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

# --- MODELOS DE RESPOSTA (Para documentação no Swagger) ---
class DadosHSPReal(BaseModel):
    media: float = Field(..., description="Média anual de HSP corrigida com perdas")
    mensal: List[float] = Field(..., description="Lista de 12 valores mensais de HSP com perdas")

class DadosHSPReferencia(BaseModel):
    media_sem_sombra: float = Field(..., description="Potencial teórico médio anual (Sem Sombra)")
    mensal_sem_sombra: List[float] = Field(..., description="Lista de 12 valores mensais teóricos (Sem Sombra)")

class UnidadeEnergia(BaseModel):
    real: DadosHSPReal = Field(..., description="Dados reais considerando sombreamento")
    referencia: DadosHSPReferencia = Field(..., description="Dados de referência para comparação")

class ProjetoSolarResponse(BaseModel):
    hsp_unidade: UnidadeEnergia = Field(
        ..., 
        alias="kWh/m²/dia",
        title="Dados de Irradiância",
        description="Dados de HSP (Horas de Sol Pleno) aninhados por tipo"
    )
    perda_sombreamento_estimada: str = Field(
        ..., 
        title="Perda de Sombra", 
        description="Percentual estimado de perda por obstrução"
    )

    model_config = ConfigDict(populate_by_name=True)

class ItemArranjoResponse(BaseModel):
    id_placa: str = Field(..., title="ID do Módulo", json_schema_extra={"example": "Placa_01"})
    
    # O alias permite que a chave no JSON seja a unidade técnica
    hsp_unidade: UnidadeEnergia = Field(
        ..., 
        alias="kWh/m²/dia", 
        title="Dados por Unidade",
        description="Agrupamento de dados de irradiância em kWh/m²/dia"
    )
    
    perda_sombreamento_estimada: str = Field(
        ..., 
        title="Perda de Sombra (%)", 
        description="Impacto percentual do obstáculo no rendimento"
    )

    # Necessário para que o FastAPI aceite o dicionário com a chave "kWh/m²/dia"
    model_config = ConfigDict(populate_by_name=True)


class ArranjoSolarResponse(BaseModel):
    total_placas: int = Field(..., title="Total de Itens", description="Quantidade de placas processadas")
    resultados: List[ItemArranjoResponse] = Field(..., title="Lista de Resultados")

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

class ConfigTecnicaBase(BaseModel):
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

class ProjetoSolarRequest(ConfigTecnicaBase):
    latitude: float = Field(..., title="Latitude", json_schema_extra={"example": -7.562})
    longitude: float = Field(..., title="Longitude", json_schema_extra={"example": -37.688})
    
class ItemArranjoRequest(ConfigTecnicaBase):
    id_placa: str = Field(..., title="Identificador", json_schema_extra={"example": "Modulo_01"})

class ProjetoArranjoRequest(BaseModel):
    latitude: float = Field(..., json_schema_extra={"example": -7.562})
    longitude: float = Field(..., json_schema_extra={"example": -37.688})
    # Lista de placas/fileiras para analisar
    itens: List[ItemArranjoRequest]

# --- ENDPOINTS ---