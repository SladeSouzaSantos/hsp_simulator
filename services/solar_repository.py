from typing import List
from .providers.solar_data_provider import SolarDataProvider

class SolarRepository:
    def __init__(self, providers: List[SolarDataProvider]):
        """
        Injeção de Dependência (SOLID): O repositório respeita a ordem da lista.
        """
        self.providers = providers

    def _fetch_from_provider(self, provider: SolarDataProvider, lat: float, lon: float):
        """Método privado para execução segura e padronização de logs."""
        try:
            print(f"[Repository] Tentando provedor: {provider.name}")
            return provider.get_solar_data(lat, lon)
        except Exception as e:
            print(f"[Repository] Falha no {provider.name}: {e}")
            raise e

    def get_standardized_data(self, lat: float, lon: float, force_provider: str = None):
        """
        Orquestrador: Decide entre o fluxo de Fallback ou Provedor Único.
        """
        # Fluxo 1: Provedor Específico (Focado em Dashboard/Debug)
        if force_provider:
            target = next((p for p in self.providers if p.name == force_provider), None)
            if not target:
                raise ValueError(f"Provedor {force_provider} não encontrado.")
            return self._fetch_from_provider(target, lat, lon)

        # Fluxo 2: Fallback Automático (Focado em Resiliência/Produção)
        last_error = None
        for provider in self.providers:
            try:
                return self._fetch_from_provider(provider, lat, lon)
            except Exception as e:
                last_error = e
                continue
        
        raise Exception(f"Todos os provedores falharam. Último erro: {last_error}")