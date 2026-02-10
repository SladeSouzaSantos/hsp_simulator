import json
from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService
from core.perez_engine import PerezEngine
from utils.constants import CELL_TECHNOLOGY_REFERENCE

def calcular_projeto_solar(lat, lon, inclinacao, azimute, albedo, altura, tecnologia="TOPCON", is_bifacial=True, panel_width=2.278, dados_pre_carregados=None, obstacle_config=None, formato="dict"):
    """
    Função principal para cálculo de HSP (Horas de Sol Pleno) com suporte a ganho bifacial.
    
    :param lat: Latitude do local.
    :param lon: Longitude do local.
    :param inclinacao: Ângulo de inclinação dos módulos.
    :param azimute: Orientação azimutal (0=Norte, 180=Sul).
    :param albedo: Coeficiente de reflexão do solo.
    :param altura: Altura de instalação do módulo (m).
    :param tecnologia: Chave tecnológica (ex: "TOPCON", "PERC") definida em constants.py.
    :param is_bifacial: Booleano para ativar/desativar cálculo traseiro.
    :param panel_width: Largura/Comprimento do painel para cálculo de View Factor.
    :param dados_pre_carregados (dict, optional): Dados meteorológicos já processados. 
            Se None, consulta a API da NASA. Útil para otimizar cálculos em lote.
    :param obstacle_config (dict, optional): Configuração de obstáculo próximo (ex: parede).
            Formato: {'height': float, 'distance': float, 'azimuth': float}. 
            Se None, assume horizonte livre.
    :param formato: "dict" para retorno nativo, "json" para string formatada.
    """
    
    if dados_pre_carregados:
        clean_data = dados_pre_carregados
    else:
        # 1. Busca Dados da NASA
        gateway = NasaPowerGateway(lat, lon)
        raw = gateway.fetch_climatology()
        clean_data = SolarDataService.standardize_data(raw)
    
    # 2. Configura o Motor de Cálculo
    b_factor = CELL_TECHNOLOGY_REFERENCE.get(tecnologia, {}).get("fator_conservador", 0.70)
    
    engine = PerezEngine(
        lat=lat, 
        is_bifacial=is_bifacial, 
        b_factor=b_factor, 
        albedo=albedo, 
        height=altura,
        panel_width=panel_width
    )
    
    # 3. Executa o cálculo
    resultado = engine.calculate_tilt_hsp(clean_data, inclinacao, azimute, obstacle_config=obstacle_config)
    
    # 4. Formata o retorno
    if formato == "json":
        return json.dumps(resultado, indent=4, ensure_ascii=False)
    
    return resultado