import requests
from functools import lru_cache
from .solar_data_provider import SolarDataProvider


class NasaPowerProvider(SolarDataProvider):
    def __init__(self):
        self.url = "https://power.larc.nasa.gov/api/temporal/climatology/point"

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_cached_data(url, lat, lon):
        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,T2M,T2M_MAX,RH2M,WS10M",
            "community": "SB",
            "longitude": round(lon, 4),
            "latitude": round(lat, 4),
            "format": "JSON"
        }
        print(f"[NASA API] Buscando dados para {lat}, {lon}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()['properties']['parameter']

    def fetch_solar_data(self, lat: float, lon: float) -> dict:
        lat_fixed = round(float(lat), 4)
        lon_fixed = round(float(lon), 4)

        try:
            return self._get_cached_data(self.url, lat_fixed, lon_fixed)
        except requests.exceptions.RequestException as e:
            # Erro de rede (timeout, DNS, etc)
            print(f"Erro de conexão com a NASA: {e}")
            raise Exception("Serviço meteorológico temporariamente indisponível.")

    def get_solar_data(self, lat: float, lon: float):
        raw_data = self.fetch_solar_data(lat, lon)
        
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        return {
            "hsp_global": [raw_data['ALLSKY_SFC_SW_DWN'][m] * 0.024 for m in months],
            "hsp_diffuse": [raw_data['ALLSKY_SFC_SW_DIFF'][m] * 0.024 for m in months],
            "temp_max": [raw_data['T2M_MAX'][m] for m in months],
            "wind_speed": [raw_data['WS10M'][m] for m in months]
        }