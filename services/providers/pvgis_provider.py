import pandas as pd
from pvlib import iotools
from functools import lru_cache
from .solar_data_provider import SolarDataProvider

class PvgisProvider(SolarDataProvider):
    def __init__(self):
        self.name = "PVGIS"

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_cached_data(lat, lon):
        """Acesso direto à API via PVLib com Cache."""
        print(f"[PVGIS API] Buscando dados para {lat}, {lon}")
        data, _ = iotools.get_pvgis_tmy(
            latitude=lat, longitude=lon, map_variables=True, outputformat='json'
        )
        return data

    def fetch_solar_data(self, lat: float, lon: float) -> pd.DataFrame:
        """Camada intermediária para manter simetria com NasaProvider."""
        try:
            return self._get_cached_data(lat, lon)
        except Exception as e:
            print(f"Erro de conexão com o PVGIS: {e}")
            raise Exception("Serviço PVGIS temporariamente indisponível.")

    def get_solar_data(self, lat: float, lon: float) -> dict:
        """Processa o bruto (DataFrame) para o contrato padronizado."""
        df_hourly = self.fetch_solar_data(lat, lon)

        # Agrupamento Mensal (Resample)
        # Convertemos W/m² para kWh/m²/dia (HSP) -> * 24 / 1000 = 0.024
        monthly_ghi = df_hourly['ghi'].resample('ME').mean() * 0.024
        monthly_dhi = df_hourly['dhi'].resample('ME').mean() * 0.024
        monthly_temp = df_hourly['temp_air'].resample('ME').max()
        monthly_wind = df_hourly['wind_speed'].resample('ME').mean()

        return {
            "hsp_global": monthly_ghi.tolist(),
            "hsp_diffuse": monthly_dhi.tolist(),
            "temp_max": monthly_temp.tolist(),
            "wind_speed": monthly_wind.tolist(),
            "metadata": {
                "source": "PVGIS-SARAH2/TMY Digital Observatory",
                "lat": lat,
                "lon": lon
            }
        }