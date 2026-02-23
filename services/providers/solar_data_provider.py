from abc import ABC, abstractmethod


class SolarDataProvider(ABC):

    @abstractmethod
    def get_solar_data(self, lat: float, lon: float) -> dict:
        """
        Contrato único: Deve retornar o dicionário PADRONIZADO:
        {
            "hsp_global": [...], 
            "hsp_diffuse": [...],
            "temp_max": [...],
            "temp_avg": [...],
            "temp_min": [...],
            "wind_speed": [...]
        }
        """
        pass