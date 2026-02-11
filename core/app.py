import json
from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService
from core.perez_engine import PerezEngine
from utils.constants import CELL_TECHNOLOGY_REFERENCE

def calcular_projeto_solar(
        lat, lon, inclinacao, azimute, albedo, altura_instalacao, 
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
    
    if dados_pre_carregados:
        dados_limpos = dados_pre_carregados
    else:
        # 1. Busca Dados da NASA
        gateway = NasaPowerGateway(lat, lon)
        raw = gateway.fetch_climatology()
        dados_limpos = SolarDataService.standardize_data(raw)
    
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
    resultado = metodo_calculo.calcular_hsp_corrigido_inc_azi(dados_limpos, inclinacao, azimute, config_obstaculo=config_obstaculo)
    
    # 4. Formata o retorno
    if formato == "json":
        return json.dumps(resultado, indent=4, ensure_ascii=False)
    
    return resultado