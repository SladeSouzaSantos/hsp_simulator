"""Join original INPE monthly global+diffuse CSVs on physical coordinates."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / 'data/inpe_labren'
MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']

def consolidate_inpe_data(root=ROOT):
    root=Path(root)
    global_ = pd.read_csv(root/'global_horizontal_means.csv',sep=';')
    diffuse = pd.read_csv(root/'diffuse_means.csv',sep=';')
    # Explicit spatial join: row orders are NOT guaranteed to coincide.
    cols = ['LAT','LON'] + MONTHS
    if global_[['LAT','LON']].duplicated().any() or diffuse[['LAT','LON']].duplicated().any():
        raise ValueError('Duplicated Atlas coordinates')
    both = global_[cols].merge(diffuse[cols],on=['LAT','LON'],how='inner',
                               suffixes=('_glo','_dif'),validate='one_to_one')
    if len(both)!=len(global_) or len(both)!=len(diffuse):
        raise ValueError('Unequal coordinate grids; cannot combine without interpolation')
    both.to_parquet(root/'atlas_brasil_consolidado.parquet',index=False)
    return len(both)

if __name__=='__main__':
    print('Células consolidadas:',consolidate_inpe_data())
