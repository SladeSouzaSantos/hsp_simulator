from abc import ABC, abstractmethod
from utils.constants import CELL_TECHNOLOGY_REFERENCE

class BasePerezEngine(ABC):
    def __init__(self, lat, lon, inclinacao_deg, azimute_deg, is_bifacial=False,
                 tecnologia_celula='TOPCON', albedo=.2, altura_instalacao=.2,
                 comprimento_modulo=2.278, largura_modulo=1.134, orientacao='Retrato',
                 tz='UTC', model='perez'):
        self.lat, self.lon = float(lat), float(lon)
        self.inclinacao_deg, self.azimute_deg = float(inclinacao_deg), float(azimute_deg)
        self.is_bifacial = bool(is_bifacial)
        self.fator_bifacial = CELL_TECHNOLOGY_REFERENCE[tecnologia_celula]['fator_conservador']
        self.albedo, self.altura_instalacao = float(albedo), float(altura_instalacao)
        self.comprimento_modulo, self.largura_modulo = float(comprimento_modulo), float(largura_modulo)
        self.orientacao, self.tz, self.model = orientacao, tz, model
        self.tecnologia_celula = tecnologia_celula

    @abstractmethod
    def calcular_hsp_corrigido_inc_azi(self, dados, config_obstaculo=None):
        raise NotImplementedError
