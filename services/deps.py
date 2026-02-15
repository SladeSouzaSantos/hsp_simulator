from services.providers import NasaPowerProvider, InpeLabrenProvider, PvgisProvider
from services.solar_repository import SolarRepository

class Dependencies:

    @staticmethod
    def get_solar_repository() -> SolarRepository:
        
        providers = [
            NasaPowerProvider(),
            InpeLabrenProvider(),
            PvgisProvider()
        ]
        
        return SolarRepository(providers=providers)