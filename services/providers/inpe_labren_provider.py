import pandas as pd
import numpy as np
import os
from .solar_data_provider import SolarDataProvider

class InpeLabrenProvider(SolarDataProvider):
    """
    Provider para os dados do Atlas Brasileiro de Energia Solar - 2ª Edição (2017).
    Fonte: INPE/LABREN[cite: 9, 30].
    """

    def __init__(self, data_path="data/inpe_labren/atlas_brasil_consolidado.parquet"):
        self.name = "INPE/LABREN Atlas 2017"
        
        if not os.path.exists(data_path):
            raise FileNotFoundError(
                "Base consolidada não encontrada. "
                "Certifique-se de que o arquivo Parquet gerado a partir dos CSVs "
                "do Atlas [cite: 41, 42] esteja na pasta correta."
            )
            
        self.df = pd.read_parquet(data_path)

    def get_solar_data(self, lat: float, lon: float) -> dict:
        # Trava Geográfica: O Atlas INPE só é válido para a América do Sul
        # Aproximadamente: Lat (-55 a 15) e Lon (-95 a -30)
        if not (-60 <= lat <= 15 and -95 <= lon <= -30):
            raise ValueError(f"Coordenadas {lat}, {lon} fora da cobertura do Atlas INPE/LABREN.")
        
        # Busca por proximidade no grid de 10km x 10km 
        distances = np.sqrt((self.df['LAT'] - lat)**2 + (self.df['LON'] - lon)**2)
        row = self.df.iloc[distances.idxmin()]
        
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        # O Atlas fornece dados em Wh/m2 dia 
        # Retornamos o dicionário padronizado conforme o contrato
        return {
            "hsp_global": [row[f"{m}_glo"] / 1000 for m in months],
            "hsp_diffuse": [row[f"{m}_dif"] / 1000 for m in months],
            "temp_max": [25.0] * 12, 
            "wind_speed": [3.0] * 12,
            "metadata": {
                "source": "INPE/LABREN Atlas 2a Edicao (2017)",
                "resolution": "10km x 10km",
                "attribution": "Pereira et al., 2017"
            }
        }