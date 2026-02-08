import requests
from functools import lru_cache

class NasaPowerGateway:
    def __init__(self, lat, lon):
        self.url = "https://power.larc.nasa.gov/api/temporal/climatology/point"
        self.lat = lat
        self.lon = lon

    # O segredo está aqui: o Python guarda o resultado baseado nos argumentos
    # Como lat/lon são os identificadores do local, usamos eles no cache
    @lru_cache(maxsize=32)
    def _get_data(self, lat, lon):
        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,T2M,T2M_MAX,RH2M,WS10M",
            "community": "SB",
            "longitude": lon,
            "latitude": lat,
            "format": "JSON"
        }
        
        print(f"\n[NASA API] Consultando novas coordenadas: {lat}, {lon}...")
        response = requests.get(self.url, params=params)
        
        if response.status_code == 200:
            return response.json()['properties']['parameter']
        else:
            raise Exception(f"Erro ao acessar API NASA: {response.status_code}")

    def fetch_climatology(self):
        """
        Método público que utiliza o cache interno.
        """
        return self._get_data(self.lat, self.lon)