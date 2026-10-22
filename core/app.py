"""Application service; API schema remains compatible with original POST routes."""
import json
from core.solar_engine_factory import SolarPerezEngineFactory

class SolarEngine:
    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def _wrap(result, climate):
        return {
            'clima': {
                'temp_max_mensal': climate.get('temp_max', []),
                'temp_avg_mensal': climate.get('temp_avg', []),
                'temp_min_mensal': climate.get('temp_min', [])},
            'kWh/m²/dia': {
                'real': {'media':result['media'], 'mensal':result['mensal']},
                'referencia': {'media_sem_sombra':result['media_sem_sombra'],
                               'mensal_sem_sombra':result['mensal_sem_sombra']}},
            'perda_sombreamento_estimada':result['perda_sombreamento_estimada'],
            'detalhes': {
                'modelo_transposicao':result['modelo'],
                'fonte': result['metadata'].get('source'),
                'qualidade':result['metadata'].get('temporal_resolution'),
                'hsp_frontal':result['hsp_frontal_media'],
                'hsp_frontal_mensal':result['hsp_frontal_mensal'],
                'hsp_frontal_mensal_sem_sombra':result['hsp_frontal_mensal_sem_sombra'],
                'perda_sombreamento_mensal_pct':result['perda_sombreamento_mensal_pct'],
                'sombra_geometria':result.get('sombra_geometria'),
                'hsp_traseira_equivalente':result['hsp_traseira_equivalente_media'],
                'hsp_traseira_equivalente_mensal':result['hsp_traseira_equivalente_mensal'],
                'hsp_horizontal':result['hsp_horizontal_media'],
                'observacao':'Valor equivalente bifacial é aproximação para módulo isolado; não representa a produção AC.'}
        }

    def calcular_projeto_solar(self, perez_engine, dados_pre_carregados=None,
                               config_obstaculo=None, formato='dict', force_provider=None):
        climate = dados_pre_carregados if dados_pre_carregados is not None else \
            self.repository.get_standardized_data(perez_engine.lat, perez_engine.lon, force_provider=force_provider)
        result = perez_engine.calcular_hsp_corrigido_inc_azi(climate, config_obstaculo)
        wrapped = self._wrap(result, climate)
        return json.dumps(wrapped, ensure_ascii=False, indent=2) if formato == 'json' else wrapped

    def calcular_arranjo_completo(self, lat, lon, itens, perez_engine_class=None):
        if not itens: raise ValueError('Arranjo vazio')
        providers = set(item.fonte_dados for item in itens)
        if len(providers) > 1:
            raise ValueError('Todos os itens de um lote devem usar a mesma fonte de dados')
        provider = next(iter(providers))
        climate = self.repository.get_standardized_data(lat, lon,
                            force_provider=None if provider=='auto' else provider)
        results = []
        for item in itens:
            engine_type = perez_engine_class or SolarPerezEngineFactory.get_engine_type()
            eng = engine_type(lat=lat, lon=lon, inclinacao_deg=item.inclinacao_graus,
                azimute_deg=item.azimute_graus, is_bifacial=item.is_bifacial,
                tecnologia_celula=item.tecnologia_celula, albedo=item.albedo_solo,
                altura_instalacao=item.distancia_centro_modulo_chao,
                comprimento_modulo=item.comprimento_modulo,
                largura_modulo=item.largura_modulo, orientacao=item.orientacao,
                model=item.modelo_transposicao)
            result = self.calcular_projeto_solar(eng, climate,
                item.config_obstaculo.model_dump() if item.config_obstaculo else None)
            results.append({'id_placa':item.id_placa, **{k:v for k,v in result.items() if k!='clima'}})
        return {'total_placas':len(results), 'resultados':results,
                'clima':self._wrap_climate(climate)}

    @staticmethod
    def _wrap_climate(data):
        return {'temp_max_mensal':data.get('temp_max',[]),
                'temp_avg_mensal':data.get('temp_avg',[]),
                'temp_min_mensal':data.get('temp_min',[])}
