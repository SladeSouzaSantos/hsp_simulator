"""Mock NASA response to assert units and timestamps without network calls."""
import pandas as pd
from services.providers.nasa_power_provider import NasaPowerProvider, PARAMS

class FakeResponse:
    def __init__(self, response): self.response = response
    def raise_for_status(self): pass
    def json(self): return self.response

def test_nasa_units_hours_and_utc(monkeypatch):
    idx=pd.date_range('2023-01-01','2024-01-01',inclusive='left',freq='h',tz='UTC')
    raw = {key: {t.strftime('%Y%m%d%H'): (250. if alias == 'ghi' else 100.) for t in idx}
           for key, alias in PARAMS.items()}
    calls=[]
    def fake_get(url,params,timeout):
        calls.append(params)
        return FakeResponse({'properties':{'parameter':raw}})
    import requests
    monkeypatch.setattr(requests,'get',fake_get)
    NasaPowerProvider._get_cached_data.cache_clear()
    df=NasaPowerProvider._get_cached_data(-5.79,-35.21,2023,2023)
    assert len(df)==8760
    assert df['ghi'].iloc[10] == 250. # W/m2; NEVER multiply each hour by .024
    assert str(df.index.tz)=='UTC'
    assert calls[0]['time-standard']=='UTC'
    assert 'ALLSKY_SFC_SW_DNI' in calls[0]['parameters']
    NasaPowerProvider._get_cached_data.cache_clear()
