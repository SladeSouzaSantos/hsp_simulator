from abc import ABC, abstractmethod
class SolarDataProvider(ABC):
    name: str
    @abstractmethod
    def get_solar_data(self, lat: float, lon: float) -> dict:
        raise NotImplementedError
