"""PVGIS typical meteorological year in UTC, not monthly means."""
from functools import lru_cache
import numpy as np
import pandas as pd
from .solar_data_provider import SolarDataProvider

class PvgisProvider(SolarDataProvider):
    name = 'PVGIS'

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_cached_data(lat, lon):
        from pvlib import iotools
        df, _ = iotools.get_pvgis_tmy(lat, lon, outputformat='json',
                                      map_variables=True, coerce_year=2023, timeout=65)
        df = df.rename(columns={'Gb(n)':'dni','Gd(h)':'dhi','G(h)':'ghi'})
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        else:
            df.index = df.index.tz_convert('UTC')
        df = df.sort_index()
        if not {'ghi','dhi','dni'}.issubset(df.columns):
            raise ValueError('PVGIS TMY incompleto: sem ghi, dhi, dni')
        return df

    def fetch_solar_data(self, lat, lon):
        return self._get_cached_data(round(float(lat),4), round(float(lon),4))

    def get_solar_data(self, lat, lon):
        df = self.fetch_solar_data(lat, lon)
        m = (df[['ghi','dhi']].resample('D').sum()/1000).groupby(lambda idx: idx.month).mean().reindex(range(1,13))
        temp = df.groupby(df.index.month)['temp_air'] if 'temp_air' in df else None
        def clean(v):
            return [float(x) if pd.notna(x) else None for x in v]
        return {'hourly':df, 'hsp_global':m['ghi'].tolist(), 'hsp_diffuse':m['dhi'].tolist(),
                'temp_max':clean(temp.max().reindex(range(1,13))) if temp is not None else [None]*12,
                'temp_avg':clean(temp.mean().reindex(range(1,13))) if temp is not None else [None]*12,
                'temp_min':clean(temp.min().reindex(range(1,13))) if temp is not None else [None]*12,
                'metadata': {'source':self.name, 'temporal_resolution':'TMY_hourly',
                             'time_standard':'UTC', 'units':'W/m²','synthetic':False}}
