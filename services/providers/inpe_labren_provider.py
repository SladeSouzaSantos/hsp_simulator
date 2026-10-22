"""INPE/LABREN Atlas 2017: MONTHLY daily irradiation, not an hourly source.

This provider deliberately does not invent hourly DNI. For Perez calculations,
choose NASA POWER or PVGIS. It can still be used to inspect horizontal HSP.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from .solar_data_provider import SolarDataProvider

class InpeLabrenProvider(SolarDataProvider):
    name = 'INPE/LABREN Atlas 2017'
    def __init__(self, data_path='data/inpe_labren/atlas_brasil_consolidado.parquet'):
        self.data_path = Path(data_path)
        self._df = None

    def get_solar_data(self, lat, lon):
        if not self.data_path.exists():
            raise FileNotFoundError('Atlas INPE ausente; execute python scripts/restore_original_data.py')
        if not (-60 <= lat <= 15 and -95 <= lon <= -30):
            raise ValueError('Coordenada fora da cobertura aproximada da base INPE')
        if self._df is None:
            self._df = pd.read_parquet(self.data_path).reset_index(drop=True)
        diff = (self._df['LAT']-lat)**2 + (self._df['LON']-lon)**2
        row = self._df.iloc[int(np.argmin(diff.to_numpy()))]
        months = ('JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC')
        return {'hsp_global':[float(row[f'{m}_glo'])/1000 for m in months],
                'hsp_diffuse':[float(row[f'{m}_dif'])/1000 for m in months],
                'temp_max':[None]*12, 'temp_avg':[None]*12, 'temp_min':[None]*12,
                'metadata':{'source':self.name,'temporal_resolution':'monthly_daily_mean',
                            'units':'kWh/m²/day','synthetic':False, 'can_transpose':False}}
