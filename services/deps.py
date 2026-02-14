from services.providers import NasaPowerProvider, InpeLabrenProvider, PvgisProvider
from services.solar_repository import SolarRepository

class Dependencies:

    @staticmethod
    def get_solar_repository() -> SolarRepository:
        
        providers = [
            InpeLabrenProvider(),
            PvgisProvider(),
            NasaPowerProvider()
        ]
        
        return SolarRepository(providers=providers)