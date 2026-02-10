import numpy as np

class ShadowEngine:
    """
    Motor de Geometria de Sombreamento para Obstruções Fixas.
    """
    
    def check_shading(self, sun_alt_deg, sun_az_deg, obstacle_config):
        """
        Verifica se há obstrução solar para uma determinada posição do sol.
        
        :param sun_alt_deg: Altitude solar em graus (0-90)
        :param sun_az_deg: Azimute solar em graus (0-360)
        :param obstacle_config: Dicionário contendo:
               - 'altura_obstaculo': Altura da parede/objeto (m)
               - 'distancia_obstaculo': Vão livre até a borda da placa (m)
               - 'referencia_azimutal_obstaculo': Azimute do objeto (deg)
               - 'largura_obstaculo': Largura do objeto (m)
               - 'orientacao_modulo': 'Paisagem' ou 'Retrato'
               - 'dimensao_percorrida': Dimensão de referência do painel, com base na orientação do modulo fv
        """
        
        # Se o sol está abaixo do horizonte, tecnicamente é "sombra" (noite)
        if not obstacle_config or sun_alt_deg <= 0:
            return 1.0 if sun_alt_deg <= 0 else 0.0

        h_obs = obstacle_config.get('altura_obstaculo', 0.0)
        d_obs = obstacle_config.get('distancia_obstaculo', 1.0)
        az_obs = obstacle_config.get('referencia_azimutal_obstaculo', 0.0) 
        w_obs = obstacle_config.get('largura_obstaculo', 10.0)
        orientacao = obstacle_config.get('orientacao_modulo', 'Paisagem')
        dimensao_percorrida = obstacle_config.get('altura_modulo_fv', 2.278) if orientacao == 'Paisagem' else obstacle_config.get('largura_modulo_fv', 1.134)
        
        

        # Verificação de Azimute (Abertura da parede)
        meio_angulo_abertura = np.degrees(np.arctan2(w_obs / 2, d_obs))
        
        # Diferença angular mínima entre o sol e o centro da parede
        diff_az = abs(sun_az_deg - az_obs)
        if diff_az > 180: diff_az = 360 - diff_az

        if diff_az <= meio_angulo_abertura:
            # Comprimento da sombra no chão
            comprimento_sombra = h_obs / np.tan(np.radians(sun_alt_deg))

            # Cálculo da Perda Gradual
            if comprimento_sombra > d_obs:
                penetracao = comprimento_sombra - d_obs
                percentual_perda = penetracao / dimensao_percorrida
                return float(np.clip(percentual_perda, 0.0, 1.0))
        
        return 0.0 # Sem sombra