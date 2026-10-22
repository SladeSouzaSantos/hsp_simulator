import logging
log = logging.getLogger(__name__)

class SolarRepository:
    def __init__(self, providers):
        self.providers = providers

    def get_standardized_data(self, lat, lon, force_provider=None):
        if force_provider:
            p = next((x for x in self.providers if x.name == force_provider), None)
            if p is None: raise ValueError('Fonte desconhecida: '+force_provider)
            return p.get_solar_data(lat, lon)
        errors = []
        for p in self.providers:
            # Never silently degrade from hourly Perez to monthly climatology.
            if p.name.startswith('INPE'):
                continue
            try:
                return p.get_solar_data(lat, lon)
            except Exception as e:
                log.warning('Provedor %s indisponível: %s', p.name, e)
                errors.append(f'{p.name}: {e}')
        raise RuntimeError('Nenhum provedor horário disponível: '+'; '.join(errors))
