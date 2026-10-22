"""Generate solar orientation sensitivity table with one real hourly source.

This is a regression/sanity report, NOT an independent scientific validation.
For PVSyst comparison, use exactly the same hourly GHI/DHI/DNI and no shading.
"""
import argparse
from pathlib import Path
import pandas as pd
from services.deps import Dependencies
from core.solar_physics import compute_poa, summarize_poa


def matrix(latitude, longitude, source='NASA POWER', model='perez'):
    weather=Dependencies.get_solar_repository().get_standardized_data(
        latitude, longitude, force_provider=source)['hourly']
    values=[]
    for tilt in (0, 15, 30, 45, 60, 90):
        for az in (0, 90, 180, 270):
            result=summarize_poa(compute_poa(weather,latitude,longitude,tilt,az,
                                              model=model, bifaciality=None))
            values.append({'latitude':latitude,'longitude':longitude,
                           'fonte':source,'modelo':model,'inclinacao':tilt,'azimute':az,
                           'hsp_media_diaria':result['media'],
                           **{f'hsp_{m:02d}':result['mensal'][m-1] for m in range(1,13)}})
    return pd.DataFrame(values)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--latitude',type=float,default=-5.79448)
    p.add_argument('--longitude',type=float,default=-35.21101)
    p.add_argument('--source',default='NASA POWER')
    p.add_argument('--model',default='perez')
    p.add_argument('--output',default='benchmarks/orientacoes.csv')
    a=p.parse_args()
    df=matrix(a.latitude,a.longitude,a.source,a.model)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(a.output,index=False)
    print(df[['inclinacao','azimute','hsp_media_diaria']].to_string(index=False))
    print('Salvo:',a.output)
