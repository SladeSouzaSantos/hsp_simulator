from typing import List
from .providers.solar_data_provider import SolarDataProvider

class SolarRepository:
    def __init__(self, providers: List[SolarDataProvider]):
        """
        Injeção de Dependência (SOLID): O repositório respeita estritamente
        a ordem da lista de provedores injetada na inicialização.
        """
        self.providers = providers

    def get_standardized_data(self, lat: float, lon: float):
        """
        Lógica de Fallback:
        Percorre os provedores na ordem exata em que foram injetados.
        O primeiro que responder com sucesso interrompe a busca.
        """
        last_error = None

        for provider in self.providers:
            try:
                print(f"[Repository] Tentando provedor: {provider.name}")
                return provider.get_solar_data(lat, lon)
            except Exception as e:
                print(f"[Repository] Falha no {provider.name}: {e}")
                last_error = e
                continue
        
        raise Exception(f"Todos os provedores solares falharam. Último erro: {last_error}")