import json
from services.providers import NasaPowerProvider
from services.solar_repository import SolarRepository
from core.perez_engine import PerezEngine
from utils.constants import CELL_TECHNOLOGY_REFERENCE

class SolarEngine:
    def __init__(self, repository: SolarRepository):
        self.repository = repository
    
    def calcular_projeto_solar(self,
            lat, lon, inclinacao, azimute, albedo=0.2, altura_instalacao=0.15, 
            tecnologia="TOPCON", 
            orientacao="Retrato",
            is_bifacial=True, 
            comprimento_modulo=2.278,
            largura_modulo=1.134,
            dados_pre_carregados=None, 
            config_obstaculo=None, 
            formato="dict"):
        """
        Função principal para cálculo de HSP (Horas de Sol Pleno) com suporte a ganho bifacial.
        
        :param lat: Latitude do local.
        :param lon: Longitude do local.
        :param inclinacao: Ângulo de inclinação dos módulos.
        :param azimute: Orientação azimutal (0=Norte, 180=Sul).
        :param albedo: Coeficiente de reflexão do solo.
        :param altura_instalacao: Altura de instalação do módulo (m).
        :param tecnologia: Chave tecnológica (ex: "TOPCON", "PERC") definida em constants.py.
        :param is_bifacial: Booleano para ativar/desativar cálculo traseiro.
        :param largura_modulo: Dimensão do lado menor do painel (m).
        :param comprimento_modulo: Dimensão do lado maior do painel (m).
        :param orientacao: "Paisagem" (horizontal) ou "Retrato" (vertical).
        :param dados_pre_carregados (dict, optional): Dados meteorológicos já processados. 
                Se None, consulta a API da NASA. Útil para otimizar cálculos em lote.
        :param config_obstaculo (dict, optional): Configuração de obstáculo fixo (ex: muro, prédio).
            Campos esperados:
            - 'altura_obstaculo': (float) Altura total do objeto em metros.
            - 'distancia_obstaculo': (float) Distância horizontal do objeto até a borda do painel (m).
            - 'referencia_azimutal_obstaculo': (float) Azimute central do objeto (0=N, 180=S).
            - 'largura_obstaculo': (float) Largura horizontal da face do objeto (m).
            Se None, assume-se que não há sombreamento por obstáculos próximos.
        :param formato: "dict" para retorno nativo, "json" para string formatada.
        """
        
        # 1. Obtém os dados climatológicos (HSP, temperatura, etc.)
        if dados_pre_carregados is not None:
            dados_climatologicos = dados_pre_carregados
        else:
            dados_climatologicos = self.repository.get_standardized_data(lat=lat, lon=lon)
        
        # 2. Configura o Método de Cálculo
        fator_bifacial = CELL_TECHNOLOGY_REFERENCE.get(tecnologia, {}).get("fator_conservador", 0.70)
        
        metodo_calculo = PerezEngine(
            lat=lat, 
            is_bifacial=is_bifacial, 
            fator_bifacial=fator_bifacial, 
            albedo=albedo, 
            altura_instalacao=altura_instalacao,
            largura_modulo=largura_modulo,
            comprimento_modulo=comprimento_modulo,
            orientacao=orientacao
        )
        
        # 3. Executa o cálculo
        resultado = metodo_calculo.calcular_hsp_corrigido_inc_azi(dados_climatologicos, inclinacao, azimute, config_obstaculo=config_obstaculo)
        
        # 4. Formata o retorno
        if formato == "json":
            return json.dumps(resultado, indent=4, ensure_ascii=False)
        
        return resultado
    
    def calcular_arranjo_completo(self, lat, lon, itens):
        """
        Lógica de processamento em lote movida do api.py para o Core.
        """
        
        # 1. Busca e processa os dados da API Meteorológica apenas UMA VEZ para a coordenada global
        dados_cache_api = self.repository.get_standardized_data(lat, lon)

        resultados = []

        # 2. Processa cada item usando sua própria configuração individual
        for item in itens:

            # Chama o core injetando os dados_pre_carregados e as configs do item
            res = self.calcular_projeto_solar(
                lat=lat,
                lon=lon,
                inclinacao=item.inclinacao_graus,
                azimute=item.azimute_graus,
                albedo=item.albedo_solo,
                altura_instalacao=item.distancia_centro_modulo_chao,
                tecnologia=item.tecnologia_celula,
                is_bifacial=item.is_bifacial,
                comprimento_modulo=item.comprimento_modulo,
                largura_modulo=item.largura_modulo,
                orientacao=item.orientacao,
                dados_pre_carregados=dados_cache_api,
                config_obstaculo=item.config_obstaculo.model_dump() if item.config_obstaculo else None
            )

            resultados.append({
                "id_placa": item.id_placa,
                "kWh/m²/dia": {
                    "real": {
                        "media": res["media"],
                        "mensal": res["mensal"],
                    },
                    "referencia": {
                        "media_sem_sombra": res["media_sem_sombra"],
                        "mensal_sem_sombra": res["mensal_sem_sombra"],
                    }
                },
                "perda_sombreamento_estimada": res["perda_sombreamento_estimada"]
            })

        return resultados