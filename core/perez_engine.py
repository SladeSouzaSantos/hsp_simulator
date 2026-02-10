import numpy as np
from core.shadow_engine import ShadowEngine

class PerezEngine:
    def __init__(self, lat, is_bifacial=False, b_factor=0.85, albedo=0.4, height=1.5, panel_width=2.4):
        self.lat_rad = np.radians(lat)
        self.lat_deg = lat
        self.is_bifacial = is_bifacial
        self.b_factor = b_factor
        self.albedo = albedo
        self.h = height          
        self.L = panel_width
        self.shadow_engine = ShadowEngine() 

    def _get_shading_loss_factor(self, n, delta, ws, obstacle_config):
        """Calcula quanto da radiação direta é perdida por sombra no dia médio do mês."""
        if not obstacle_config:
            return 0.0

        # Amostragem de 20 pontos entre o nascer e o pôr do sol
        omega_points = np.linspace(-ws, ws, 20)
        shaded_count = 0
        
        for omega in omega_points:
            # 1. Altitude Solar
            sin_h = np.sin(self.lat_rad)*np.sin(delta) + np.cos(self.lat_rad)*np.cos(delta)*np.cos(omega)
            alt_rad = np.arcsin(np.clip(sin_h, -1, 1))
            alt_deg = np.degrees(alt_rad)
            
            # 2. Azimute Solar
            cos_az = (np.sin(delta) * np.cos(self.lat_rad) - np.cos(delta) * np.sin(self.lat_rad) * np.cos(omega)) / np.cos(alt_rad)
            az_deg = np.degrees(np.arccos(np.clip(cos_az, -1, 1)))
            if omega > 0: az_deg = 360 - az_deg # Ajuste para o período da tarde

            # 3. Verifica sombra
            if self.shadow_engine.check_shading(alt_deg, az_deg, obstacle_config):
                shaded_count += 1
        
        return shaded_count / len(omega_points)

    def calculate_tilt_hsp(self, data, tilt_deg, azimuth_deg, obstacle_config=None):
        beta = np.radians(tilt_deg)
        gamma = np.radians(azimuth_deg)
        results = []
        days_n = [17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344]

        for i in range(12):
            gh = data['hsp_global'][i]
            dh = data['hsp_diffuse'][i]
            n = days_n[i]

            # 1. Geometria Solar
            delta = np.radians(23.45 * np.sin(np.radians(360 * (284 + n) / 365)))
            ws = np.arccos(np.clip(-np.tan(self.lat_rad) * np.tan(delta), -1, 1))
            
            # Cálculo do rb (fator de inclinação)
            num = (np.sin(self.lat_rad)*np.cos(beta) + np.cos(self.lat_rad)*np.sin(beta)*np.cos(gamma))*np.sin(delta)*ws + \
                  (np.cos(self.lat_rad)*np.cos(beta) - np.sin(self.lat_rad)*np.sin(beta)*np.cos(gamma))*np.cos(delta)*np.sin(ws) - \
                  (np.sin(beta)*np.sin(gamma))*np.cos(delta)*(1-np.cos(ws))
            den = np.sin(self.lat_rad)*np.sin(delta)*ws + np.cos(self.lat_rad)*np.cos(delta)*np.sin(ws)
            rb = num / den

            # --- LÓGICA DE SOMBRA ---
            # Calculamos o fator de perda (ex: 0.2 se 20% do dia útil estiver sombreado)
            loss_factor = self._get_shading_loss_factor(n, delta, ws, obstacle_config)
            
            # Aplicamos a perda apenas na componente DIRETA (gh - dh)
            # Se houver sombra, reduzimos o rb proporcionalmente
            rb_shaded = rb * (1 - loss_factor)

            # --- FACE FRONTAL ---
            rb_front = max(0, rb_shaded)
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
                h_beam_rear = (gh - dh) * max(0, -rb_shaded) # Traseira também pode sofrer sombra
                h_diff_rear = dh * (1 - np.cos(beta)) / 2
                
                ratio = self.h / self.L
                vf_ground = (ratio / np.sqrt(ratio**2 + 1)) 
                vf_tilt = (1 - np.cos(beta)) / 2
                vf_final = np.clip(vf_ground + vf_tilt, 0, 1)
                
                h_refl_rear = gh * self.albedo * vf_final * 0.95 
                h_rear = (h_beam_rear + h_diff_rear + h_refl_rear) * self.b_factor
                h_total += h_rear

            results.append(max(0, h_total))

        return {
            "media": round(sum(results) / 12, 3), 
            "mensal": [round(val, 3) for val in results],
            "perda_sombreamento_estimada": f"{loss_factor*100:.1f}%" if obstacle_config else "0%"
        }