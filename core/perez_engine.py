import numpy as np

class PerezEngine:
    def __init__(self, lat, is_bifacial=False, b_factor=0.85, albedo=0.4, height=1.5, panel_width=2.4):
        """
        :param height: Altura do centro do painel ao solo (m)
        :param panel_width: Largura/Comprimento do painel (m)
        """
        self.lat_rad = np.radians(lat)
        self.is_bifacial = is_bifacial
        self.b_factor = b_factor
        self.albedo = albedo
        self.h = height          
        self.L = panel_width     

    def calculate_tilt_hsp(self, data, tilt_deg, azimuth_deg):
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
            
            num = (np.sin(self.lat_rad)*np.cos(beta) + np.cos(self.lat_rad)*np.sin(beta)*np.cos(gamma))*np.sin(delta)*ws + \
                  (np.cos(self.lat_rad)*np.cos(beta) - np.sin(self.lat_rad)*np.sin(beta)*np.cos(gamma))*np.cos(delta)*np.sin(ws) - \
                  (np.sin(beta)*np.sin(gamma))*np.cos(delta)*(1-np.cos(ws))
            den = np.sin(self.lat_rad)*np.sin(delta)*ws + np.cos(self.lat_rad)*np.cos(delta)*np.sin(ws)
            rb = num / den

            # --- FACE FRONTAL (Perez Simplificado) ---
            rb_front = max(0, rb)
            f1 = 0.28 * (1 - (dh/gh)) if gh > 0 else 0
            f2 = 0.02
            h_diff_front = dh * ((1-f1)*((1+np.cos(beta))/2) + f1*rb_front + f2*np.sin(beta))
            h_refl_front = gh * self.albedo * (1 - np.cos(beta)) / 2
            h_front = ((gh - dh) * rb_front) + h_diff_front + h_refl_front

            # --- FACE TRASEIRA (Bifacial com View Factor Saturação) ---
            h_total = h_front
            if self.is_bifacial:
                # 1. Ganho Direto (Sol batendo na traseira)
                h_beam_rear = (gh - dh) * max(0, -rb)
                
                # 2. Difusa do Céu Traseiro
                h_diff_rear = dh * (1 - np.cos(beta)) / 2
                
                # 3. Albedo (Reflexão do Solo)
                # O fator de visão do chão cresce com a altura relativa (h/L)
                ratio = self.h / self.L
                vf_ground = (ratio / np.sqrt(ratio**2 + 1)) 
                
                # A inclinação também ajuda a traseira a ver o horizonte
                vf_tilt = (1 - np.cos(beta)) / 2
                
                # View Factor total limitado ao domo (1.0)
                vf_final = np.clip(vf_ground + vf_tilt, 0, 1)
                
                # Cálculo da refletância traseira
                h_refl_rear = gh * self.albedo * vf_final * 0.95 
                
                # Soma e aplicação do Fator de Bifacialidade
                h_rear = (h_beam_rear + h_diff_rear + h_refl_rear) * self.b_factor
                h_total += h_rear

            results.append(max(0, h_total))

        return {
            "media": round(sum(results) / 12, 3), 
            "mensal": [round(val, 3) for val in results]
        }