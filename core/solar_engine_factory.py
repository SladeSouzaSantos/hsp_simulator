from .perez_engines import PerezEngine, PerezEnginePVLib

class SolarPerezEngineFactory:
    ENGINES = {'perez_legacy': PerezEngine, 'perez_pvlib': PerezEnginePVLib, 'perez': PerezEnginePVLib}
    @classmethod
    def get_engine_type(cls, motor_type='perez_pvlib'):
        if motor_type not in cls.ENGINES:
            raise ValueError('Motor desconhecido: ' + motor_type)
        return cls.ENGINES[motor_type]
