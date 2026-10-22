import numpy as np
import pandas as pd
import pytest
pvlib = pytest.importorskip('pvlib')
from core.solar_physics import compute_poa, summarize_poa

def clear_sky(lat=-5.79448,lon=-35.21101):
    idx=pd.date_range('2023-01-01','2024-01-01',freq='h',inclusive='left',tz='UTC')
    # use midpoint to align with engine calculation
    loc=pvlib.location.Location(lat,lon,tz='UTC')
    cs=loc.get_clearsky(idx+pd.Timedelta(minutes=30),model='ineichen')
    cs.index=idx
    return cs[['ghi','dhi','dni']]

def test_horizontal_equals_input_ghi():
    data=clear_sky()
    poa=compute_poa(data,-5.79448,-35.21101,0,0)
    assert np.allclose(poa['frontal'],data['ghi'],atol=1e-6)

def test_east_west_same_average_under_symmetrical_clearsky():
    data=clear_sky()
    e=summarize_poa(compute_poa(data,-5.79448,-35.21101,30,90,model='haydavies'))['media']
    w=summarize_poa(compute_poa(data,-5.79448,-35.21101,30,270,model='haydavies'))['media']
    assert abs(e-w)/max(e,w) < .03, (e,w)

def test_bifacial_adds_equivalent_not_front():
    data=clear_sky()
    mono=compute_poa(data,-5.79448,-35.21101,15,0)
    bi=compute_poa(data,-5.79448,-35.21101,15,0,bifaciality=.8)
    assert np.allclose(mono['frontal'],bi['frontal'])
    assert bi['equivalente'].sum()>mono['equivalente'].sum()
