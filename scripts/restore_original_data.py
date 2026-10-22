"""Restore optional original datasets (not modified by this patch).

Requires internet. Downloads the immutable GitHub revision of source files and
regenerates the parquet after validating the merge by LAT/LON.
"""
from pathlib import Path
import argparse
import requests
from process_inpe_data import consolidate_inpe_data

COMMIT='c7da7eab1e7a0f67a7d45007f1d8bd3a81e4855a'
BASE=f'https://raw.githubusercontent.com/SladeSouzaSantos/hsp_simulator/{COMMIT}/'
FILES=['data/localidades.json','data/inpe_labren/global_horizontal_means.csv',
       'data/inpe_labren/diffuse_means.csv','data/inpe_labren/direct_normal_means.csv',
       'data/inpe_labren/atlas_solar_2017_metadados.pdf',
       'tests/fixtures/amostragem_sundata.json']

def restore(root=None, overwrite=False):
    base=Path(root) if root else Path(__file__).resolve().parents[1]
    for name in FILES:
        target=base/name
        if target.exists() and not overwrite:
            print('Mantido:',name)
            continue
        r=requests.get(BASE+name,timeout=120)
        r.raise_for_status()
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(r.content)
        print('Baixado:',name,len(r.content),'bytes')
    consolidate_inpe_data(base/'data/inpe_labren')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--overwrite',action='store_true',help='sobrescreve localidades/fixtures existentes')
    opts=parser.parse_args()
    restore(overwrite=opts.overwrite)
