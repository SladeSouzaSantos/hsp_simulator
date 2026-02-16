from typing import Type
from core.perez_engines import BasePerezEngine, PerezEngine, PerezEnginePVLib

class SolarEngineFactory:
    ENGINES = {
        "perez_legacy": PerezEngine,
        "perez_pvlib": PerezEnginePVLib
    }

    @classmethod
    def get_engine(cls, motor_type: str = "perez_legacy") -> Type[BasePerezEngine]:
        # O uso de .get() com um default garante que o sistema nunca pare
        engine_class = cls.ENGINES.get(motor_type.lower())
        
        if not engine_class:
            print(f"Aviso: Motor '{motor_type}' não encontrado. Usando padrão.")
            return PerezEngine
            
        return engine_class