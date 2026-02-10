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
               - 'altura': Altura da parede (m)
               - 'distancia': Distância da base da parede ao centro da placa (m)
               - 'az_parede': Azimute para onde a parede está "olhando" (deg)
               - 'largura': Largura da parede (m)
        """
        # Se o sol está abaixo do horizonte, tecnicamente é "sombra" (noite)
        if sun_alt_deg <= 0:
            return 1.0 # 100% de perda direta

        h_obs = obstacle_config.get('altura', 4.0)
        d_obs = obstacle_config.get('distancia', 2.0)
        az_obs = obstacle_config.get('az_parede', 45.0) 
        w_obs = obstacle_config.get('largura', 4.0)

        # 1. Comprimento da sombra projetada (L = H / tan(alt))
        l_sombra = h_obs / np.tan(np.radians(sun_alt_deg))

        # 2. Verificação de Azimute (O sol está na 'fatia' da parede?)
        # Calculamos a abertura angular que a largura da parede ocupa na visão da placa
        meio_angulo_abertura = np.degrees(np.arctan2(w_obs / 2, d_obs))
        
        # Diferença angular mínima entre o sol e o centro da parede
        diff_az = abs(sun_az_deg - az_obs)
        if diff_az > 180:
            diff_az = 360 - diff_az

        # 3. Decisão Booleana: Sol atrás da parede e sombra alcança a placa?
        if diff_az <= meio_angulo_abertura:
            if l_sombra >= d_obs:
                return 1.0 # Obstrução total do raio direto
        
        return 0.0 # Sem sombra