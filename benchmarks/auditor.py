import os
import json
import pandas as pd
from core.app import SolarEngine
from tests.test_scenarios import SCENARIOS

class SolarAuditor:
    def __init__(self, engine: SolarEngine):
        self.engine = engine

    def rodar_benchmark_sombra(self, lat=-5.8125, lon=-35.1875):
        cenario = SCENARIOS["validacao_sombra"]
        print(f"🚀 Iniciando Auditoria: {cenario['descricao']}")
        
        # 1. Pré-carrega dados (Otimização que validamos nos testes)
        cache_clima = self.engine.repository.get_standardized_data(lat, lon)
        
        resultados_csv = []
        
        for caso in cenario["casos"]:
            # Prepara a config de obstáculo para o motor
            config = {
                "altura_obstaculo": caso["h_obs"],
                "distancia_obstaculo": caso["d_obs"],
                "referencia_azimutal_obstaculo": caso["azi_obs"],
                "largura_obstaculo": 10.0
            } if caso["h_obs"] > 0 else None

            # Executa o cálculo usando o motor oficial
            res = self.engine.calcular_projeto_solar(
                lat=lat, lon=lon,
                inclinacao=15, azimute=0,
                dados_pre_carregados=cache_clima,
                config_obstaculo=config
            )

            # Formata para o CSV
            resultados_csv.append({
                "Cenário": caso["label"],
                "H_Obs": caso["h_obs"],
                "D_Obs": caso["d_obs"],
                "HSP_Liquido": res["media"],
                "HSP_Bruto": res["media_sem_sombra"],
                "Perda_%": res["perda_sombreamento_estimada"]
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
                coords['latitude'], coords['longitude'], 
                inclinacao=0, azimute=0, is_bifacial=False,
                dados_pre_carregados=dados_clima
            )["media"]

            for inc_str, ref_data in inclinações.items():
                inc = int(inc_str)
                if inc == 0: continue 

                # Cálculo simulado no ângulo alvo
                sim_alvo = self.engine.calcular_projeto_solar(
                    coords['latitude'], coords['longitude'], 
                    inclinacao=inc, azimute=0, is_bifacial=False,
                    dados_pre_carregados=dados_clima
                )["media"]
                
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
    