from .providers import NasaPowerProvider, PvgisProvider, InpeLabrenProvider
from .solar_repository import SolarRepository

class Dependencies:
    @staticmethod
    def get_solar_repository():
        return SolarRepository([NasaPowerProvider(), PvgisProvider(), InpeLabrenProvider()])
