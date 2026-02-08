class SolarDataService:
    @staticmethod
    def standardize_data(raw_data):
        # Converte W/m2 para HSP (kWh/m2/dia) e organiza em listas de 12 meses
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        processed = {
            "hsp_global": [raw_data['ALLSKY_SFC_SW_DWN'][m] * 0.024 for m in months],
            "hsp_diffuse": [raw_data['ALLSKY_SFC_SW_DIFF'][m] * 0.024 for m in months],
            "temp_max": [raw_data['T2M_MAX'][m] for m in months],
            "wind_speed": [raw_data['WS10M'][m] for m in months]
        }
        return processed