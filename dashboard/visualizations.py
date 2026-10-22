"""Streamlit result renderer; plotted values come from corrected engine only."""
import pandas as pd
import streamlit as st
from core.perez_engines.perez_engine_pvlib import PerezEnginePVLib

MONTHS = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']


@st.cache_data(ttl=3600, show_spinner=False)
def _load_provider_data(latitude, longitude, provider, _repository):
    """Cache per coordinate and source, shared across dashboard reruns.

    `_repository` is a dependency excluded from the cache key by Streamlit.
    Source and coordinates ARE part of the key. For a newly configured provider,
    explicitly clear the cache via the app/Streamlit cache management interface.
    """
    return _repository.get_standardized_data(
        latitude, longitude, force_provider=provider,
    )


class SolarDashboardRenderer:
    def __init__(self, engine, repository):
        self.engine, self.repository = engine, repository

    def renderizar_layout_comparativo(self, lat, lon, inc, azi, alb, h, tec_chave,
             modo_bifacial, orientacao, usar_obstaculo, config_obstaculo,
             nome_exibicao, provider_forcado=None, modelo='perez'):
        try:
            with st.spinner('Carregando série horária e calculando irradiância...'):
                climate = _load_provider_data(
                    round(float(lat), 4), round(float(lon), 4),
                    provider_forcado, self.repository,
                )
                if climate.get('hourly') is None:
                    st.warning('INPE/LABREN fornece apenas médias mensais; não é possível calcular Perez horário sem inventar o perfil temporal. Selecione NASA POWER ou PVGIS.')
                    st.dataframe(pd.DataFrame({'Mês':MONTHS,'GHI horizontal (kWh/m²/dia)':climate['hsp_global']}))
                    return
                def engine(tilt, azimuth, bifacial):
                    return PerezEnginePVLib(lat, lon, tilt, azimuth, is_bifacial=bifacial,
                        tecnologia_celula=tec_chave, albedo=alb, altura_instalacao=h,
                        orientacao=orientacao, model=modelo)
                projet = self.engine.calcular_projeto_solar(engine(inc,azi,modo_bifacial),climate,
                          config_obstaculo if usar_obstaculo else None)
                horizontal = self.engine.calcular_projeto_solar(engine(0,0,False),climate)
                # Horizontal reference deliberately monofacial: direct comparison to GHI.
            real = projet['kWh/m²/dia']['real']
            ref = horizontal['kWh/m²/dia']['real']
            st.subheader(f'Resultados — {nome_exibicao}')
            st.caption(f"Fonte: {climate['metadata']['source']} | resolução: {climate['metadata']['temporal_resolution']} | modelo: {modelo} | azimute 0°=N, 90°=L, 180°=S, 270°=O")
            baseline = projet['kWh/m²/dia']['referencia']
            a,b,c,d = st.columns(4)
            a.metric('HSP com sombra (kWh/m²/dia)', f"{real['media']:.3f}")
            b.metric('HSP sem sombra (kWh/m²/dia)', f"{baseline['media_sem_sombra']:.3f}")
            c.metric('GHI horizontal (kWh/m²/dia)', f"{ref['media']:.3f}")
            d.metric('Perda anual de irradiância frontal', projet['perda_sombreamento_estimada'])
            if modo_bifacial:
                st.info('HSP equivalente bifacial = HSP frontal + irradiância traseira estimada × fator de bifacialidade. Não representa energia elétrica de saída nem validou o sombreamento por fileiras.')
            if usar_obstaculo:
                st.warning('Sombreamento geométrico de tela vertical retangular: apenas perda de irradiância DIRETA, não de energia elétrica. Difusa, refletida e face traseira não são obstruídas neste estágio.')
                geometry = projet['detalhes'].get('sombra_geometria') or {}
                if geometry.get('altura_ajustada_para_evitar_solo'):
                    st.warning(f"Altura informada do centro ({h:.3f} m) colocaria a borda inferior abaixo do solo. Para a geometria de sombra, centro ajustado para {geometry['altura_centro_utilizada_m']:.3f} m. Informe uma altura real maior para melhorar a confiabilidade.")
            df = pd.DataFrame({'Mês': MONTHS,
                'HSP com sombra': real['mensal'],
                'HSP sem sombra': baseline['mensal_sem_sombra'],
                'GHI horizontal': ref['mensal'],
                'Perda frontal de sombra (%)': projet['detalhes'].get('perda_sombreamento_mensal_pct', [0.]*12)})
            st.bar_chart(df.set_index('Mês')[['HSP com sombra', 'HSP sem sombra', 'GHI horizontal']])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button('Baixar resultados (CSV)', df.to_csv(index=False).encode('utf-8-sig'),
                               'hsp_mensal.csv', mime='text/csv')
            with st.expander('Componentes e qualidade do resultado'):
                st.json(projet['detalhes'])
        except Exception as e:
            st.error(f'Não foi possível calcular: {e}')
            st.info('Confira a fonte horária, as dependências, o acesso à rede e as mensagens no terminal.')

    def renderizar_grafico_sombra(self, *args, **kwargs):
        st.caption('Sombra estimada por hora no cálculo físico. O gráfico polar ilustrativo antigo foi removido para evitar referência solar incorreta.')
