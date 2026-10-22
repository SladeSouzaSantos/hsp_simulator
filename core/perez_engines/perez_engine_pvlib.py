from .perez_engine_base import BasePerezEngine
from core.solar_physics import compute_poa, summarize_poa

class PerezEnginePVLib(BasePerezEngine):
    def calcular_hsp_corrigido_inc_azi(self, dados, config_obstaculo=None):
        if dados.get('hourly') is None:
            raise ValueError('Transposição Perez requer GHI, DHI e DNI em série horária (W/m²)')
        result = summarize_poa(compute_poa(
            dados['hourly'], self.lat, self.lon, self.inclinacao_deg, self.azimute_deg,
            albedo=self.albedo, model=self.model,
            bifaciality=self.fator_bifacial if self.is_bifacial else None,
            obstacle=config_obstaculo, module_height=self.altura_instalacao,
            module_length=self.comprimento_modulo if self.orientacao == 'Retrato' else self.largura_modulo,
            module_width=self.largura_modulo if self.orientacao == 'Retrato' else self.comprimento_modulo))
        if config_obstaculo:
            from .shadow_engine import ShadowEngine
            length = self.comprimento_modulo if self.orientacao == 'Retrato' else self.largura_modulo
            effective = ShadowEngine.effective_center_height(self.altura_instalacao, length, self.inclinacao_deg)
            result['sombra_geometria'] = {
                'tipo': 'tela_vertical_retangular',
                'modelo': 'intersecao_analitica_area_frontal',
                'altura_centro_informada_m': self.altura_instalacao,
                'altura_centro_utilizada_m': round(effective, 5),
                'altura_ajustada_para_evitar_solo': effective > self.altura_instalacao + 1e-8,
                'distancia_referencia': 'borda_mais_proxima_modulo',
                'limite': 'apenas_feixe_direto; sem perdas difusas, traseiras ou eletricas',
            }
        result['modelo'] = self.model
        result['metadata'] = dados.get('metadata', {})
        return result
