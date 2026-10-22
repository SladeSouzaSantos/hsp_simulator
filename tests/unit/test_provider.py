import pandas as pd
import pytest
from services.providers.nasa_power_provider import NasaPowerProvider
from services.solar_repository import SolarRepository

class MockUnavailable:
    name='NASA POWER'
    def get_solar_data(self,lat,lon): raise OSError('offline')

class MockAvailable:
    name='PVGIS'
    def get_solar_data(self,lat,lon): return {'hourly':'fixture','metadata':{'source':'PVGIS'}}

class MockMonthly:
    name='INPE/LABREN Atlas 2017'
    def get_solar_data(self,lat,lon): return {'hsp_global':[5]*12}

def test_fallback_hourly_only():
    r=SolarRepository([MockUnavailable(), MockAvailable(), MockMonthly()])
    assert r.get_standardized_data(-5,-35)['metadata']['source']=='PVGIS'
    assert 'hsp_global' in r.get_standardized_data(-5,-35,force_provider='INPE/LABREN Atlas 2017')

def test_fallback_does_not_silently_use_monthly():
    r=SolarRepository([MockUnavailable(),MockMonthly()])
    with pytest.raises(RuntimeError,match='Nenhum provedor horário'):
        r.get_standardized_data(-5,-35)
