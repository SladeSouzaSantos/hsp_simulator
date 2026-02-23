import os
import json
import pandas as pd
from core.app import SolarEngine
from core.solar_engine_factory import SolarPerezEngineFactory
from services.providers import InpeLabrenProvider, NasaPowerProvider, PvgisProvider
from tests.test_scenarios import SCENARIOS

class SolarAuditor:
    def __init__(self, engine: SolarEngine):
        self.engine = engine

    def rodar_benchmark_sombra(self, lat=-5.8125, lon=-35.1875):
        cenario = SCENARIOS["validacao_sombra"]
        print(f"🚀 Iniciando Auditoria: {cenario['descricao']}")
        
        resultados_csv = []
        
        for caso in cenario["casos"]:
            config = {
                "altura_obstaculo": caso["h_obs"],
                "distancia_obstaculo": caso["d_obs"],
                "referencia_azimutal_obstaculo": caso["azi_obs"],
                "largura_obstaculo": 10.0
            } if caso["h_obs"] > 0 else None

            # CORREÇÃO: Instancia o motor com os parâmetros fixos do teste
            perez_type = SolarPerezEngineFactory.get_engine_type()
            inc_cenario = caso.get("inclinacao_painel", 15)
            azi_cenario = caso.get("azimute_painel", 0)
            perez = perez_type(lat=lat, lon=lon, inclinacao_deg=inc_cenario, azimute_deg=azi_cenario)

            # Executa o cálculo injetando o motor configurado
            res = self.engine.calcular_projeto_solar(
                perez_engine=perez,
                config_obstaculo=config
            )
            
            resultados_csv.append({
                "Cenario": caso.get("nome", f"H{caso['h_obs']} D{caso['d_obs']}"), # Usa a altura e distância como nome se 'nome' faltar
                "H_Obstaculo": caso["h_obs"],
                "D_Obs": caso["d_obs"],
                "HSP_Liquido": res["kWh/m²/dia"]["real"]["media"],
                "Perda_Sombra": res["perda_sombreamento_estimada"]
            })

        return resultados_csv

    def validar_transposicao_cresesb(self):
        """
        Valida o fator de ganho geométrico comparando com a amostragem do SunData (CRESESB).
        Isso atesta se a lógica de inclinação está calibrada com o mundo real.
        """
        # Caminhos baseados na raiz do projeto
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        loc_path = os.path.join(project_root, 'data', 'localidades.json')
        gabarito_path = os.path.join(project_root, 'tests', 'fixtures', 'amostragem_sundata.json')

        if not os.path.exists(gabarito_path):
            print(f"[ERRO] Gabarito não encontrado em: {gabarito_path}")
            return []

        with open(loc_path, 'r', encoding='utf-8') as f:
            locs = json.load(f)
        with open(gabarito_path, 'r', encoding='utf-8') as f:
            gabarito = json.load(f)

        print(f"\n{'CIDADE':<15} | {'ANG':>3} | {'ESTIMADO':>10} | {'REAL':>10} | {'DIFERENÇA'}")
        print("-" * 65)

        perez_type = SolarPerezEngineFactory.get_engine_type()

        results = []

        for cidade_nome, inclinações in gabarito.items():
            # Busca coordenadas nas localidades
            coords = None
            for estado in locs.values():
                for c in estado['cidades']:
                    if c['nome'].strip().lower() == cidade_nome.strip().lower():
                        coords = c
                        break
                if coords: break
            
            if not coords: continue

            # Otimização: Busca clima uma vez por cidade
            dados_clima = self.engine.repository.get_standardized_data(coords['latitude'], coords['longitude'])

            # Base real 0° (Referência)
            real_sundata_0 = inclinações.get("0", {}).get("Anual")
            
            # Cálculo simulado 0° para achar o fator de escala
            sim_0 = self.engine.calcular_projeto_solar(
                perez_engine=perez_type(lat=coords['latitude'], lon=coords['longitude'], inclinacao_deg=0, azimute_deg=0, is_bifacial=False),
                dados_pre_carregados=dados_clima
            )["kWh/m²/dia"]["real"]["media"]

            for inc_str, ref_data in inclinações.items():
                inc = int(inc_str)
                if inc == 0: continue 

                # Cálculo simulado no ângulo alvo
                sim_alvo = self.engine.calcular_projeto_solar(
                    perez_engine=perez_type(lat=coords['latitude'], lon=coords['longitude'], inclinacao_deg=inc, azimute_deg=0, is_bifacial=False),
                    dados_pre_carregados=dados_clima
                )["kWh/m²/dia"]["real"]["media"]
                
                # A mágica da Transposição:
                fator_transposicao = sim_alvo / sim_0
                hsp_estimado = real_sundata_0 * fator_transposicao
                hsp_real_angulo = ref_data.get("Anual")
                
                erro_pct = ((hsp_estimado / hsp_real_angulo) - 1) * 100

                print(f"{cidade_nome:<15} | {inc:>3}° | {hsp_estimado:>10.2f} | {hsp_real_angulo:>10.2f} | {erro_pct:>+8.2f}%")
                
                results.append({
                    "Cidade": cidade_nome,
                    "Angulo": inc,
                    "HSP_Estimado": round(hsp_estimado, 3),
                    "HSP_Real_Gabarito": hsp_real_angulo,
                    "Erro_Logica_Percentual": round(erro_pct, 2)
                })

        return results
    
    def comparar_provedores_por_capital(self, lat, lon, cidade_nome):
        relatorio = []
        # Lista de provedores que você quer testar
        provedores = [InpeLabrenProvider(), NasaPowerProvider(), PvgisProvider()]
        
        print(f"\n🌍 Comparando dados para: {cidade_nome}")
        
        for p in provedores:
            try:
                # Força a busca diretamente no provedor específico
                dados = p.get_solar_data(lat, lon)
                hsp_anual = sum(dados["hsp_global"]) / 12
                
                relatorio.append({
                    "Provedor": p.__class__.__name__,
                    "HSP_Anual": round(hsp_anual, 3),
                    "Fonte": dados["metadata"]["source"]
                })
                print(f"   - {p.__class__.__name__}: {hsp_anual:.2f} kWh/m²/dia")
            except Exception as e:
                print(f"   - {p.__class__.__name__}: Falhou ({e})")
                
        return relatorio
