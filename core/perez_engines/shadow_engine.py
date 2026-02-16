import numpy as np

class ShadowEngine:
    """
    Motor de Geometria de Sombreamento para Obstruções Fixas.
    """
    
    def estimar_perda_sombreamento(self, altitude_sol_deg, azimute_sol_deg, altura_instalacao_modulo=0.0, comprimento_modulo=2.278, largura_modulo=1.134, orientacao='Retrato', config_obstaculo=None):
        """
        Estima a fração de perda de radiação direta baseada na geometria da sombra projetada.
        
        :param altitude_sol_deg: Ângulo de altitude do sol (0° no horizonte, 90° no zênite).
        :param azimute_sol_deg: Ângulo azimutal do sol (0°=Norte, 90°=Leste, 180°=Sul, 270°=Oeste).
        :param comprimento_modulo: Lado maior do painel (m).
        :param largura_modulo: Lado menor do painel (m).
        :param orientacao: 'Retrato' (comprimento inclinado) ou 'Paisagem' (largura inclinada).
        :param config_obstaculo: Dicionário com:
                - 'altura_obstaculo': m
                - 'distancia_obstaculo': m (vão livre até o início do painel)
                - 'referencia_azimutal_obstaculo': deg (posição central do objeto)
                - 'largura_obstaculo': m (extensão lateral do objeto)
        :return: Float entre 0.0 (sem sombra) e 1.0 (painel totalmente coberto).
        """
        
        # Se o sol está abaixo do horizonte, tecnicamente é "sombra" (noite)
        if not config_obstaculo or altitude_sol_deg <= 0:
            return 1.0 if altitude_sol_deg <= 0 else 0.0

        h_obs_absoluta = config_obstaculo.get('altura_obstaculo', 0.0)
        d_obs = config_obstaculo.get('distancia_obstaculo', 1.0)
        az_obs = config_obstaculo.get('referencia_azimutal_obstaculo', 0.0) 
        w_obs = config_obstaculo.get('largura_obstaculo', 10.0)
        
        # Altura efetiva do obstáculo em relação ao painel
        h_obs = max(0, h_obs_absoluta - altura_instalacao_modulo)
        # Se o obstáculo é baixo demais para projetar sombra, retorna 0.0
        if h_obs <= 0:
            return 0.0 # Sem sombra
        
        # A dimensão relevante para calcular a penetração da sombra depende da orientação do painel
        dimensao_percorrida = comprimento_modulo if orientacao == 'Retrato' else largura_modulo
        

        # Verificação de Azimute (Abertura da parede)
        meio_angulo_abertura = np.degrees(np.arctan2(w_obs / 2, d_obs))
        
        # Diferença angular mínima entre o sol e o centro da parede
        diff_az = abs(azimute_sol_deg - az_obs)
        if diff_az > 180: diff_az = 360 - diff_az

        if diff_az <= meio_angulo_abertura:
            # Comprimento da sombra no chão
            comprimento_sombra = h_obs / np.tan(np.radians(altitude_sol_deg))

            # Cálculo da Perda Gradual
            if comprimento_sombra > d_obs:
                penetracao = comprimento_sombra - d_obs
                percentual_perda = penetracao / dimensao_percorrida
                return float(np.clip(percentual_perda, 0.0, 1.0))
        
        return 0.0 # Sem sombra