import numpy as np
import pandas as pd
import pytest
from core.solar_physics import validate_weather, summarize_poa

def sample(year=2023):
    idx=pd.date_range(f'{year}-01-01',f'{year+1}-01-01',freq='h',inclusive='left',tz='UTC')
    # Synthetic constant mean power density, testing integration not solar geometry.
    return pd.DataFrame({'ghi':np.full(len(idx),250.),'dhi':np.full(len(idx),100.),
                         'dni':np.full(len(idx),300.)},index=idx)

def test_integracao_horizontal_diaria_e_anual():
    w=sample()
    poa=pd.DataFrame({key:w['ghi'] for key in (
        'frontal','frontal_sem_sombra','equivalente','equivalente_sem_sombra','horizontal')},index=w.index)
    poa['traseira_equivalente']=0
    result=summarize_poa(poa)
    assert result['media']==6.0
    assert result['mensal']==[6.0]*12
    assert result['hsp_traseira_equivalente_media']==0.

def test_dia_bissexto():
    assert len(validate_weather(sample(2024)))==8784

def test_horarios_com_lacunas_sao_rejeitados():
    w=sample().drop(sample().index[100])
    with pytest.raises(ValueError,match='intervalos contínuos'):
        validate_weather(w)

def test_nao_aceita_hsp_diario_no_lugar_de_wm2():
    with pytest.raises(ValueError,match='ano completo'):
        validate_weather(sample().iloc[:12])

def test_valores_missing_sao_rejeitados():
    w=sample()
    w.loc[w.index[5],'dni']=float('nan')
    with pytest.raises(ValueError,match='dni inválido'):
        validate_weather(w)
