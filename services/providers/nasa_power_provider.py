"""NASA POWER hourly UTC data. No 0.024 factor: each observation is W/m²."""
import os
from functools import lru_cache
import pandas as pd
import numpy as np
import requests
from .solar_data_provider import SolarDataProvider

PARAMS = {'ALLSKY_SFC_SW_DWN':'ghi', 'ALLSKY_SFC_SW_DIFF':'dhi',
          'ALLSKY_SFC_SW_DNI':'dni', 'T2M':'temp_air', 'WS10M':'wind_speed'}

class NasaPowerProvider(SolarDataProvider):
    name = 'NASA POWER'
    url = 'https://power.larc.nasa.gov/api/temporal/hourly/point'

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_cached_data(lat, lon, start_year, end_year):
        params = {'parameters': ','.join(PARAMS), 'community': 'RE',
                  'longitude': lon, 'latitude': lat,
                  'start': f'{start_year}0101', 'end':f'{end_year}1231',
                  'format':'JSON', 'time-standard':'UTC'}
        r = requests.get(NasaPowerProvider.url, params=params, timeout=90)
        r.raise_for_status()
        payload = r.json()
        if 'properties' not in payload or 'parameter' not in payload['properties']:
            raise ValueError(f'NASA não forneceu parâmetros esperados: {payload.get("messages", "sem detalhes")}')
        raw = payload['properties']['parameter']
        if not all(key in raw for key in ('ALLSKY_SFC_SW_DWN','ALLSKY_SFC_SW_DIFF','ALLSKY_SFC_SW_DNI')):
            raise ValueError('NASA não retornou as três componentes GHI/DHI/DNI')
        frame = pd.DataFrame({alias: pd.Series(raw[key], dtype=float) for key, alias in PARAMS.items() if key in raw})
        frame.index = pd.to_datetime(frame.index, format='%Y%m%d%H', utc=True)
        frame = frame.sort_index()
        frame = frame.replace([-999., -9999., -99.], np.nan)
        # Do not replace missing hours with 0: they bias the annual irradiation.
        if frame[['ghi','dhi','dni']].isnull().values.any():
            raise ValueError('NASA retornou horas sem GHI/DHI/DNI; não serão convertidas em zeros')
        return frame

    def fetch_solar_data(self, lat, lon):
        start = int(os.environ.get('NASA_START_YEAR', '2022'))
        end = int(os.environ.get('NASA_END_YEAR', '2024'))
        if start < 2001 or end < start or end > 2025 or end - start > 9:
            raise ValueError('NASA_START_YEAR/NASA_END_YEAR inválidos: use 2001-2025 e até 10 anos')
        return self._get_cached_data(round(float(lat),4), round(float(lon),4), start, end)

    def get_solar_data(self, lat, lon):
        df = self.fetch_solar_data(lat, lon)
        monthly = (df[['ghi','dhi']].resample('D').sum()/1000).groupby(lambda idx: idx.month).mean().reindex(range(1,13))
        temps = df.groupby(df.index.month)['temp_air'] if 'temp_air' in df else None
        def clean(v):
            return [float(x) if pd.notna(x) else None for x in v]
        return {
            'hourly': df,
            'hsp_global': monthly['ghi'].tolist(),
            'hsp_diffuse': monthly['dhi'].tolist(),
            'temp_avg': clean(temps.mean().reindex(range(1,13))) if temps is not None else [None]*12,
            'temp_max': clean(temps.max().reindex(range(1,13))) if temps is not None else [None]*12,
            'temp_min': clean(temps.min().reindex(range(1,13))) if temps is not None else [None]*12,
            'metadata': {'source': self.name, 'temporal_resolution':'hourly', 'time_standard':'UTC',
                         'years':f'{df.index.year.min()}-{df.index.year.max()}',
                         'units':'W/m²', 'synthetic':False}
        }
