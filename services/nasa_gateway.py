import requests
from functools import lru_cache

class NasaPowerGateway:
    def __init__(self, lat, lon):
        self.url = "https://power.larc.nasa.gov/api/temporal/climatology/point"
        # Arredondamos na entrada para garantir consistência
        self.lat = round(float(lat), 4)
        self.lon = round(float(lon), 4)

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_cached_data(url, lat, lon):
        """
        Método estático para que o cache seja compartilhado entre todas 
        as instâncias da classe dentro do mesmo worker.
        """
        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,T2M,T2M_MAX,RH2M,WS10M",
            "community": "SB",
            "longitude": lon,
            "latitude": lat,
            "format": "JSON"
        }
        
        print(f"\n[NASA API] Buscando dados novos para Lat: {lat}, Lon: {lon}...")
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()['properties']['parameter']
        else:
            raise Exception(f"Erro ao acessar API NASA: {response.status_code}")

    def fetch_climatology(self):
        """
        Chama o cache centralizado usando as coordenadas já arredondadas.
        """
        return self._get_cached_data(self.url, self.lat, self.lon)