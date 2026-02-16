import numpy as np
import pvlib
from abc import ABC, abstractmethod
from core.perez_engines.shadow_engine import ShadowEngine
from utils.constants import CELL_TECHNOLOGY_REFERENCE

class BasePerezEngine(ABC):
    @abstractmethod
    def __init__(self, lat, lon, inclinacao_deg, azimute_deg, is_bifacial=False, tecnologia_celula="TOPCON", albedo=0.2, 
                 altura_instalacao=0.0, comprimento_modulo=2.278, largura_modulo=1.134, 
                 orientacao="Retrato", tz="UTC"):
        """
        Motor de cálculo baseado no modelo de Perez para irradiância em superfícies inclinadas.
        
        :param lat: Latitude em graus decimais.
        :param lon: Longitude em graus decimais.
        :param is_bifacial: Ativa o cálculo da irradiância na face traseira.
        :param tecnologia_celula: Tecnologia da célula solar (TOPCON, PERC, etc.).
        :param albedo: Reflectância do solo ao redor.
        :param altura_instalacao: Altura do solo até o eixo central/inferior do módulo (m).
        :param comprimento_modulo: Dimensão do lado maior do painel (m).
        :param largura_modulo: Dimensão do lado menor do painel (m).
        :param orientacao: "Retrato" ou "Paisagem".
        """
        self.lat_rad = np.radians(lat)
        self.lat = lat
        self.lon_rad = np.radians(lon)
        self.lon = lon
        self.inclinacao_deg = inclinacao_deg
        self.azimute_deg = azimute_deg
        self.is_bifacial = is_bifacial
        self.tecnologia_celula = tecnologia_celula
        self.fator_bifacial = CELL_TECHNOLOGY_REFERENCE.get(tecnologia_celula, 0.85)['fator_conservador']
        self.albedo = albedo
        self.altura_instalacao = altura_instalacao          
        self.comprimento_modulo = comprimento_modulo
        self.largura_modulo = largura_modulo
        self.orientacao = orientacao
        self.tz = tz

        self.dimensao_referencia_modulo = comprimento_modulo if orientacao == "Retrato" else largura_modulo
        self.location = pvlib.location.Location(lat, lon, tz=tz)
        self.shadow_engine = ShadowEngine()

    @abstractmethod
    def calcular_hsp_corrigido_inc_azi(self, dados, config_obstaculo=None):
        """
        Deve retornar um dicionário com:
        {
            "media": float,
            "media_sem_sombra": float,
            "mensal": list,
            "mensal_sem_sombra": list,
            "perda_sombreamento_estimada": str
        }
        """
        pass