import numpy as np
import pandas as pd
import pvlib
from core.perez_engines.perez_engine_base import BasePerezEngine

class PerezEnginePVLib(BasePerezEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _obter_fator_perda_sombra(self, delta, ws, config_obstaculo):
        """Calcula a fração de perda (0 a 1) para o dia médio."""
        if not config_obstaculo:
            return 0.0
        
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
            if omega > 0: az_deg = 360 - az_deg

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
        # 1. Preparação dos dados (Padrão 12 meses do INPE)
        if isinstance(dados, dict):
            # Garante que temos apenas os 12 valores mensais
            ghi_mensal = np.array(dados.get('hsp_global', []))
            dhi_mensal = np.array(dados.get('hsp_diffuse', []))
        else:
            ghi_mensal = dados['hsp_global'].values
            dhi_mensal = dados['hsp_diffuse'].values

        # 2. Setup de Tempo para o PVLib (Ponto único ao meio-dia para cálculo de transposição)
        times = pd.to_datetime([f'2024-{m:02d}-21 12:00:00' for m in range(1, 13)]).tz_localize(self.tz)
        sol_pos = self.location.get_solarposition(times)
        dni_extra = pvlib.irradiance.get_extra_radiation(times)
        airmass = self.location.get_airmass(times).airmass_relative
        
        # O PVLib precisa de DNI. Vamos estimar um DNI "equivalente" para o HSP mensal
        dni_mensal = pvlib.irradiance.dni(ghi_mensal, dhi_mensal, sol_pos['zenith']).fillna(0)

        # 3. Transposição de Perez via PVLib
        # O azimute do PVLib é invertido em relação ao que costumamos usar (0=N, 180=S)
        pvlib_azimuth = (360 - self.azimute_deg) % 360

        irrad = pvlib.irradiance.get_total_irradiance(
            surface_tilt=self.inclinacao_deg, 
            surface_azimuth=pvlib_azimuth,
            solar_zenith=sol_pos['zenith'], 
            solar_azimuth=sol_pos['azimuth'],
            dni=dni_mensal, ghi=ghi_mensal, dhi=dhi_mensal,
            dni_extra=dni_extra, airmass=airmass, model='perez', albedo=self.albedo
        )

        # 4. Cálculo de Sombras e Bifacialidade
        res_bruto = []
        res_liquido = []
        perdas_sombreamento = []

        # Parâmetros astronômicos para a função de sombra
        day_of_year = times.dayofyear
        # Declinação e ângulo horário do pôr do sol
        delta = np.radians(23.45 * np.sin(np.radians(360/365 * (284 + day_of_year))))
        ws = np.arccos(-np.tan(self.lat_rad) * np.tan(delta))

        for i in range(12):
            # A. Obtém o fator de perda do mês (ex: 0.05 para 5% de perda)
            f_sombra = self._obter_fator_perda_sombra(delta[i], ws[i], config_obstaculo)
            perdas_sombreamento.append(f_sombra)

            # B. Calcula Irradiância Frontal
            # Somente a componente direta (poa_direct) sofre sombra
            frontal_sem_sombra = irrad['poa_global'].iloc[i]
            frontal_com_sombra = (irrad['poa_direct'].iloc[i] * (1 - f_sombra)) + \
                                 irrad['poa_sky_diffuse'].iloc[i] + \
                                 irrad['poa_ground_diffuse'].iloc[i]

            # C. Ganho Bifacial (usando a mesma lógica da Base)
            ganho_traseiro = 0
            if self.is_bifacial:
                fator_view = min(1.0, self.altura_instalacao / (self.altura_instalacao + 0.05))
                ganho_traseiro = irrad['poa_ground_diffuse'].iloc[i] * self.fator_bifacial * fator_view

            res_bruto.append(float(frontal_sem_sombra + ganho_traseiro))
            res_liquido.append(float(frontal_com_sombra + ganho_traseiro))

        # 5. Formatação do Resultado
        total_bruto = sum(res_bruto)
        total_liquido = sum(res_liquido)
        perda_global_pct = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

        return {
            "media": round(float(np.mean(res_liquido)), 3),
            "media_sem_sombra": round(float(np.mean(res_bruto)), 3),
            "mensal": [round(v, 3) for v in res_liquido],
            "mensal_sem_sombra": [round(v, 3) for v in res_bruto],
            "perda_sombreamento_estimada": f"{perda_global_pct:.1f}%"
        }