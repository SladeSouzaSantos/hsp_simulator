from .providers.solar_data_provider import SolarDataProvider

class SolarRepository:
    def __init__(self, provider: SolarDataProvider):
        self.provider = provider

    def get_standardized_data(self, lat: float, lon: float):        
        return self.provider.get_solar_data(lat, lon)