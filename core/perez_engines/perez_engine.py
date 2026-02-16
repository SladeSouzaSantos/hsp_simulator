import traceback
import numpy as np
from core.perez_engines.perez_engine_base import BasePerezEngine

class PerezEngine(BasePerezEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _obter_fator_perda_sombra(self, delta, ws, config_obstaculo):
        """Calcula quanto da radiação direta é perdida por sombra no dia médio do mês."""
        if not config_obstaculo:
            return 0.0

        # Amostragem de 20 pontos entre o nascer e o pôr do sol
        omega_points = np.linspace(-ws, ws, 100)
        perda_acumulada = 0
        
        for omega in omega_points:
            # 1. Altitude Solar
            sin_h = np.sin(self.lat_rad)*np.sin(delta) + np.cos(self.lat_rad)*np.cos(delta)*np.cos(omega)
            alt_rad = np.arcsin(np.clip(sin_h, -1, 1))
            alt_deg = np.degrees(alt_rad)
            
            # 2. Azimute Solar
            cos_az = (np.sin(delta) * np.cos(self.lat_rad) - np.cos(delta) * np.sin(self.lat_rad) * np.cos(omega)) / np.cos(alt_rad)
            az_deg = np.degrees(np.arccos(np.clip(cos_az, -1, 1)))
            if omega > 0: 
                az_deg = 360 - az_deg # Ajuste para o período da tarde

            # 3. Verifica sombra            
            perda_ponto = self.shadow_engine.estimar_perda_sombreamento(
                altitude_sol_deg=alt_deg, 
                azimute_sol_deg=az_deg, 
                altura_instalacao_modulo=self.altura_instalacao,
                comprimento_modulo=self.comprimento_modulo, 
                largura_modulo=self.largura_modulo, 
                orientacao=self.orientacao, 
                config_obstaculo=config_obstaculo)

            perda_acumulada += perda_ponto
        
        return perda_acumulada / len(omega_points)

    def calcular_hsp_corrigido_inc_azi(self, dados, config_obstaculo=None):
        try:
            beta = np.radians(self.inclinacao_deg)
            gamma = np.radians(self.azimute_deg)
            results_liquido = []
            results_bruto = []
            perdas_mensais = []
            days_n = [17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344]

            for i in range(12):
                gh = dados['hsp_global'][i]
                dh = dados['hsp_diffuse'][i]
                n = days_n[i]

                # 1. Geometria Solar
                delta = np.radians(23.45 * np.sin(np.radians(360 * (284 + n) / 365)))
                ws = np.arccos(np.clip(-np.tan(self.lat_rad) * np.tan(delta), -1, 1))
                
                # Cálculo do rb (fator de inclinação)
                num = (np.sin(self.lat_rad)*np.cos(beta) + np.cos(self.lat_rad)*np.sin(beta)*np.cos(gamma))*np.sin(delta)*ws + \
                    (np.cos(self.lat_rad)*np.cos(beta) - np.sin(self.lat_rad)*np.sin(beta)*np.cos(gamma))*np.cos(delta)*np.sin(ws) - \
                    (np.sin(beta)*np.sin(gamma))*np.cos(delta)*(1-np.cos(ws))
                den = np.sin(self.lat_rad)*np.sin(delta)*ws + np.cos(self.lat_rad)*np.cos(delta)*np.sin(ws)
                rb = float(np.asarray(num / den).flatten()[0])

                # --- LÓGICA DE SOMBRA ---
                # Calculamos o fator de perda (ex: 0.2 se 20% do dia útil estiver sombreado)
                fator_perda = self._obter_fator_perda_sombra(delta, ws, config_obstaculo)
                perdas_mensais.append(fator_perda)
                
                # Aplicamos a perda apenas na componente DIRETA (gh - dh)
                # Se houver sombra, reduzimos o rb proporcionalmente
                rb_shaded = rb * (1 - fator_perda)

                # --- FACE FRONTAL ---

                def calcular_irradiancia(rb_valor):
                    rb_front = max(0, rb_valor)
                    f1 = 0.28 * (1 - (dh/gh)) if gh > 0 else 0
                    f2 = 0.02
                    h_diff_front = dh * ((1-f1)*((1+np.cos(beta))/2) + f1*rb_front + f2*np.sin(beta))
                    h_refl_front = gh * self.albedo * (1 - np.cos(beta)) / 2
                    
                    # Irradiância Direta Líquida (já com desconto da sombra)
                    h_beam_front = (gh - dh) * rb_front
                    h_front = h_beam_front + h_diff_front + h_refl_front

                    # --- FACE TRASEIRA ---
                    h_total = h_front

                    if self.is_bifacial:
                        h_beam_rear = (gh - dh) * max(0, -rb_valor) # Traseira também pode sofrer sombra
                        h_diff_rear = dh * (1 - np.cos(beta)) / 2
                        
                        ratio = self.altura_instalacao / self.dimensao_referencia_modulo
                        vf_ground = (ratio / np.sqrt(ratio**2 + 1)) 
                        vf_tilt = (1 - np.cos(beta)) / 2
                        vf_final = np.clip(vf_ground + vf_tilt, 0, 1)
                        
                        h_refl_rear = gh * self.albedo * vf_final * 0.95 
                        h_rear = (h_beam_rear + h_diff_rear + h_refl_rear) * self.fator_bifacial
                        h_total += h_rear

                    return float(max(0, np.asarray(h_total).flatten()[0]))
            
                results_bruto.append(calcular_irradiancia(rb)) # RB Original
                results_liquido.append(calcular_irradiancia(rb_shaded)) # RB com desconto de sombra
                
            media_bruta = float(np.mean(results_bruto))
            media_hsp = float(np.mean(results_liquido))
            media_perda = (sum(perdas_mensais) / 12) * 100 if config_obstaculo else 0
            
            return {
                "media": round(media_hsp, 3),
                "media_sem_sombra": round(media_bruta, 3),
                "mensal": [round(val, 3) for val in results_liquido],            
                "mensal_sem_sombra": [round(val, 3) for val in results_bruto],
                "perda_sombreamento_estimada": f"{media_perda:.1f}%" if config_obstaculo else "0%"
            }
        
        except Exception as e:
            # 1. Captura o log detalhado (Stack Trace)
            error_details = traceback.format_exc()
            
            # 2. Imprime no console do VS Code para você debugar
            print("="*50)
            print(f"ERRO DETECTADO NO MOTOR PEREZ")
            print(error_details) 
            print("="*50)
            
            return