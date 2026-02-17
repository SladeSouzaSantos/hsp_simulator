import math
import streamlit as st
import pandas as pd
import altair as alt
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from typing import Type
from core.app import SolarEngine
from core.perez_engines.perez_engine_base import BasePerezEngine
from services.solar_repository import SolarRepository

class SolarDashboardRenderer:
    def __init__(self, engine: SolarEngine, repository: SolarRepository, perez_engine_type: Type[BasePerezEngine]):
        """
        Injetamos as dependências necessárias para o Dashboard funcionar.
        """
        self.engine = engine
        self.repository = repository
        self.perez_engine_type = perez_engine_type

    def calcular_posicoes(self, lat, altura, dia_ano, hora):
        """Calcula a física da sombra e a posição do sol (Azimute e Altitude)."""
        # Declinação Solar (Cooper, 1969)
        delta = 23.45 * math.sin(math.radians(360/365 * (dia_ano - 81)))
        # Ângulo Horário (15 graus por hora)
        h_ang = (hora - 12) * 15
        lat_rad, delta_rad, h_rad = map(math.radians, [lat, delta, h_ang])
        
        # Altitude Solar (Ângulo acima do horizonte)
        sin_alpha = (math.sin(lat_rad) * math.sin(delta_rad) + 
                    math.cos(lat_rad) * math.cos(delta_rad) * math.cos(h_rad))
        
        if sin_alpha <= 0.001: 
            return None 
        
        alpha_rad = math.asin(sin_alpha)
        comprimento_sombra = altura / math.tan(alpha_rad)
        
        # Azimute Solar
        arg_cos = (math.sin(delta_rad) - math.sin(lat_rad) * math.sin(alpha_rad)) / (math.cos(lat_rad) * math.cos(alpha_rad))
        arg_cos = max(min(arg_cos, 1), -1) 
        gamma_deg = math.degrees(math.acos(arg_cos))
        
        if h_ang > 0: 
            gamma_deg = 360 - gamma_deg
        
        return gamma_deg, (gamma_deg + 180) % 360, comprimento_sombra, math.degrees(alpha_rad)

    def renderizar_layout_comparativo(
            self, lat, lon, inc, azi, alb, h, tec_chave, modo_bifacial, 
            orientacao, usar_obstaculo, config_obstaculo, nome_exibicao, provider_forcado=None):
        # Normalizamos para o cache interno do worker
        lat_fixed = round(float(lat), 4)
        lon_fixed = round(float(lon), 4)
        nome_provider = provider_forcado if provider_forcado else "Auto"
        chave_local = f"{lat_fixed}_{lon_fixed}_{nome_provider}"
        
        # 1. Gerenciamento de Dados
        if chave_local in st.session_state.cache_api_data:
            dados_clima = st.session_state.cache_api_data[chave_local]
        else:
            with st.spinner("Buscando novos dados na NASA..."):
                dados_clima = self.repository.get_standardized_data(lat=lat_fixed, lon=lon_fixed, force_provider=provider_forcado)
                st.session_state.cache_api_data[chave_local] = dados_clima
                st.success(f"✅ Dados carregados via {dados_clima['metadata']['source']}!")

        # 2. Execução dos Cálculos (Dois Cenários)
        with st.spinner("Calculando modelos..."):
            # Cenário A: Seu Projeto
            perez_engine_projeto = self.perez_engine_type(
                lat=lat_fixed,
                lon=lon_fixed,
                inclinacao_deg=inc,
                azimute_deg=azi,
                is_bifacial=modo_bifacial,
                tecnologia_celula=tec_chave,
                albedo=alb,
                altura_instalacao=h,
                orientacao=orientacao
            )

            res_projeto = self.engine.calcular_projeto_solar(
                perez_engine=perez_engine_projeto,
                dados_pre_carregados=dados_clima,
                config_obstaculo=config_obstaculo
            )

            # Cenário B: Padrão (Inclinação 0, Azimute 0)
            perez_engine_padrao = self.perez_engine_type(
                lat=lat_fixed,
                lon=lon_fixed,
                inclinacao_deg=0,
                azimute_deg=0,
                is_bifacial=modo_bifacial,
                tecnologia_celula=tec_chave,
                albedo=alb,
                altura_instalacao=h,
                orientacao=orientacao
            )
            
            res_padrao = self.engine.calcular_projeto_solar(
                perez_engine=perez_engine_padrao,
                dados_pre_carregados=dados_clima,
                config_obstaculo=None
            )
            
            # --- EXIBIÇÃO DE MÉTRICAS E GRÁFICOS ---
            # (O resto do seu código de métricas e Altair permanece igual daqui para baixo)
            label_tipo = "Bifacial" if modo_bifacial else "Monofacial"
            st.subheader(f"Resultados Médios Diários ({label_tipo}) - {nome_exibicao}")
            
            col1, col2, col3 = st.columns(3)
            ganho_vs_padrao = ((res_projeto['media'] / res_padrao['media']) - 1) * 100
            
            col1.metric("HSP Projeto", f"{res_projeto['media']:.3f}", f"{ganho_vs_padrao:.1f}% vs. 0°/0°")
            col2.metric("HSP Padrão (0°/0°)", f"{res_padrao['media']:.3f}")
            col3.metric("Diferença Bruta", f"{res_projeto['media'] - res_padrao['media']:.3f} kWh/m²")

            perda_str = res_projeto.get("perda_sombreamento_estimada", "0%")
            
            # Verificamos se há obstáculo e se a perda não é zero
            if usar_obstaculo and perda_str not in ["0%", "0.0%"]:
                st.error(f"🚨 **Perda por Sombreamento:** {perda_str}")

            meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            df_projeto = pd.DataFrame({"Mês": meses, "HSP": res_projeto["mensal"], "Cenário": "Seu Projeto"})
            df_padrao = pd.DataFrame({"Mês": meses, "HSP": res_padrao["mensal"], "Cenário": "Padrão (0°/0°)"})
            df_comp = pd.concat([df_projeto, df_padrao])

            grafico = alt.Chart(df_comp).mark_bar().encode(
                x=alt.X('Mês:N', sort=None, title="Meses"),
                y=alt.Y('HSP:Q', title="HSP (kWh/m²/dia)"),
                xOffset='Cenário:N',
                color=alt.Color('Cenário:N', scale=alt.Scale(range=['#ff4b4b', '#4b4bff']), title="Cenário"),
                tooltip=['Cenário', 'Mês', alt.Tooltip('HSP', format='.3f')]
            ).properties(
                height=400,
                title=f"Comparativo Mensal: Projeto vs. Referência Plana ({label_tipo})"
            )

            st.altair_chart(grafico, width='stretch')

            with st.expander("Ver Tabela Comparativa Detalhada"):
                # Criamos o dataframe garantindo que os dados venham das variáveis de resultado
                df_table = pd.DataFrame({
                    "Mês": meses,
                    "Seu Projeto": res_projeto["mensal"],
                    "Padrão (0°/0°)": res_padrao["mensal"]
                }).set_index("Mês").T
                
                # O .style.format força o Streamlit a mostrar 3 casas decimais em tudo
                st.table(df_table.style.format("{:.3f}"))

    def renderizar_grafico_sombra(self, meses_lista, mes_v, hora_sim, lat, h, usar_obstaculo, h_obs, d_obs, azi_obs, azi, orientacao="Paisagem"):
        mes_num = meses_lista.index(mes_v) + 1
        dia_ano = datetime(2026, mes_num, 21).timetuple().tm_yday
        
        # Altura de referência para o cálculo do sol/sombra     
        altura_ref = max(0, h_obs - h)
        pos_agora = self.calcular_posicoes(lat, altura_ref, dia_ano, hora_sim)
        az_sol, az_sombra, dist_sombra, alt_sol = pos_agora

        # --- AJUSTES DE ESCALA (Sua regra: 2x a distância) ---
        # Se não houver obstáculo, usamos um padrão de 10m para visualização do painel
        max_r = d_obs * 2 if usar_obstaculo else 10

        fig = go.Figure()

        # =================================================================
        # INCLUSÃO DA TRAJETÓRIA DO SOL (ESTILO SHADOW_APP.PY)
        # =================================================================
        # Criamos o rastro na borda do gráfico (90% do raio máximo)
        rastro_distancia = max_r * 0.9 
        traj_theta = []
        alturaSol = []
        
        # Fazemos a varredura do dia para desenhar o caminho
        for hr_track in np.linspace(5.5, 18.5, 60):
            p_track = self.calcular_posicoes(lat, altura_ref, dia_ano, hr_track)
            if p_track:
                alturaSol.append(p_track[3]) # Guarda a altitude para possível uso futuro
                traj_theta.append(p_track[0]) # Pega o Azimute do sol
        
        if traj_theta:
            fig.add_trace(go.Scatterpolar(
                r=[rastro_distancia] * len(traj_theta), 
                theta=traj_theta,
                mode='lines', 
                name='Trajetória do Sol',
                line=dict(color='gold', dash='dot', width=2) # Pontilhados amarelos
            ))
        # =================================================================

        # --- ELEMENTO 1: O PAINEL (Escala Real 2.278m) ---
        # 1. Ajuste do Tamanho do Painel baseado na orientação
        dimensao_referencia_painel = 2.278 if orientacao == "Retrato" else 1.134

        fig.add_trace(go.Scatterpolar(
            r=[0, dimensao_referencia_painel], 
            theta=[azi, azi],
            mode='lines+markers', 
            name=f'Módulo FV ({orientacao})',
            line=dict(color='blue', width=2),
            marker=dict(
                symbol='arrow',         # Define o símbolo como seta
                size=15,                # Ajuste o tamanho da ponta da seta aqui
                angleref='previous',    # Faz a seta girar automaticamente para o ângulo do azimute
                color='blue'
            )
        ))

        # --- ELEMENTO 2: O OBSTÁCULO E SOMBRA ---
            
        # Sombra projetada: Começa no obstáculo
        fig.add_trace(go.Scatterpolar(
            r=[d_obs, d_obs + dist_sombra], 
            theta=[azi_obs, az_sombra],
            mode='lines', name='Sombra Projetada',
            line=dict(color='rgba(50, 50, 50, 0.4)', width=10)
        ))

        # Marcador do Obstáculo
        fig.add_trace(go.Scatterpolar(
            r=[d_obs], theta=[azi_obs],
            mode='markers+text', name='Obstáculo',
            marker=dict(size=15, color='red', symbol='square')
        ))

        # --- ELEMENTO 3: TRAJETÓRIA DO SOL ---
        traj_theta, traj_r = [], []
        for hr in np.linspace(5.5, 18.5, 60):
            p = self.calcular_posicoes(lat, altura_ref, dia_ano, hr)
            if p:
                # Para o rastro do sol, mapeamos a altitude (90-alt) para caber na escala do gráfico
                # Mas como o gráfico agora é focado em metros, o sol é apenas referencial
                traj_theta.append(p[0])
                traj_r.append(p[0]) # Apenas para rastro direcional

        if pos_agora:
            # Indicador da direção do Sol (seta externa)
            fig.add_trace(go.Scatterpolar(
                r=[d_obs * 1.8], theta=[pos_agora[0]],
                mode='markers', name='Direção do Sol',
                marker=dict(size=12, color='orange', symbol='star')
            ))

        fig.update_layout(
            polar=dict(
                angularaxis=dict(
                    direction="clockwise", 
                    rotation=90, 
                    tickvals=[0, 90, 180, 270], 
                    ticktext=['N', 'L', 'S', 'O']
                ),
                radialaxis=dict(
                    visible=True, 
                    range=[0, max_r], 
                    title="Metros"
                )
            ),
            height=700, 
            template="plotly_white",
            legend=dict(orientation="h", y=-0.2)
        )
        
        st.plotly_chart(fig, width='stretch')