from typing import List
from .providers.solar_data_provider import SolarDataProvider
from .providers.inpe_labren_provider import InpeLabrenProvider

class SolarRepository:
    def __init__(self, providers: List[SolarDataProvider]):
        """
        Injeção de Dependência (SOLID): O repositório recebe uma lista 
        de provedores, mantendo-se desacoplado de implementações específicas.
        """
        self.providers = providers

    def _is_brazil(self, lat: float, lon: float) -> bool:
        """Verifica se a coordenada está dentro da abrangência do Atlas (Metadados)."""
        return -33.75 <= lat <= 5.35 and -74.0 <= lon <= -34.7

    def get_standardized_data(self, lat: float, lon: float):
        """
        Lógica de Negócio (Orquestração):
        1. Prioriza o INPE se estiver no Brasil (Mais preciso).
        2. Usa PVGIS ou NASA como Fallback/Internacional.
        """
        # Reordena para priorizar o INPE caso esteja no Brasil
        ordered_providers = self.providers
        if self._is_brazil(lat, lon):
            # Move o InpeLabrenProvider para o topo da lista se ele existir
            ordered_providers = sorted(
                self.providers, 
                key=lambda p: isinstance(p, InpeLabrenProvider), 
                reverse=True
            )

        last_error = None
        for provider in ordered_providers:
            try:
                print(f"[Repository] Tentando provedor: {provider.name}")
                return provider.get_solar_data(lat, lon)
            except Exception as e:
                print(f"[Repository] Falha no {provider.name}: {e}")
                last_error = e
                continue
        
        raise Exception(f"Todos os provedores solares falharam. Último erro: {last_error}")