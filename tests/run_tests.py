import os
import json
import pandas as pd
from core.app import calcular_projeto_solar
from tests.test_scenarios import SCENARIOS
from utils.constants import CELL_TECHNOLOGY_REFERENCE
from utils.exporter import SolarExporter
from services.nasa_gateway import NasaPowerGateway
from services.solar_service import SolarDataService

def run_simulation():
    lat, lon = -7.562, -37.688
    
    PLACA_CADASTRADA = {
        "modelo": "Astro N5 CHSM72N(DG)/F-BH",
        "tecnologia": "TOPCON",
        "comprimento": 2.278,
        "largura": 1.134,        
        "orientacao": "retrato"
    }
    
    dimensao_L = (
        PLACA_CADASTRADA["comprimento"] 
        if PLACA_CADASTRADA["orientacao"] == "retrato" 
        else PLACA_CADASTRADA["largura"]
    )
    
    all_results = []
    
    # --- PRÉ-CARREGAMENTO ---
    print(f"Buscando dados meteorológicos para {lat}, {lon}...")
    gateway = NasaPowerGateway(lat, lon)
    dados_clima = SolarDataService.standardize_data(gateway.fetch_climatology())

    print(f"\nINICIANDO TESTE TÉCNICO - PLACA: {PLACA_CADASTRADA['modelo']}")
    print(f"TECNOLOGIA: {PLACA_CADASTRADA['tecnologia']} | FATOR B: {CELL_TECHNOLOGY_REFERENCE[PLACA_CADASTRADA['tecnologia']]['fator_conservador']}")

    for nome_chave, config in SCENARIOS.items():
        print(f"\n{'='*105}")
        print(f" EXECUÇÃO: {config['descricao']}")
        print(f"{'='*105}")
        
        alturas = config.get('alturas_teste', [config.get('altura', 1.5)])
        albedos = config.get('albedos_teste', [config.get('albedo', 0.4)])
        
        # Captura a configuração de obstáculo se existir no cenário
        obs_config = config.get('obstacle_config', None)
        
        header = f"{'ALB.':>5} | {'ALT.':>6} | {'INC.':>5} | {'AZI.':>5} | {'MONO HSP':>9} | {'BIFAC HSP':>9} | {'GANHO %':>8} | {'PERDA SOMBRA'}"
        print(header)
        print("-" * 105)

        for alb in albedos:
            for h in alturas:
                for inc in config['inclinacoes']:
                    for azi in config['azimutes']:
                        # --- CÁLCULO MONOFACIAL ---
                        res_mono = calcular_projeto_solar(
                            lat, lon, inc, azi, alb, h, 
                            tecnologia=PLACA_CADASTRADA["tecnologia"], 
                            panel_width=dimensao_L, 
                            is_bifacial=False, 
                            dados_pre_carregados=dados_clima,
                            obstacle_config=obs_config # NOVO PARÂMETRO
                        )
                        
                        # --- CÁLCULO BIFACIAL ---
                        res_bi = calcular_projeto_solar(
                            lat, lon, inc, azi, alb, h, 
                            tecnologia=PLACA_CADASTRADA["tecnologia"], 
                            panel_width=dimensao_L, 
                            is_bifacial=True, 
                            dados_pre_carregados=dados_clima,
                            obstacle_config=obs_config # NOVO PARÂMETRO
                        )
                        
                        m_val = res_mono["media"]
                        b_val = res_bi["media"]
                        perda_sombra = res_bi.get("perda_sombreamento_estimada", "0%")
                        ganho = ((b_val / m_val) - 1) * 100 if m_val > 0 else 0
                        
                        all_results.append({
                            "modelo": PLACA_CADASTRADA["modelo"],
                            "cenario": nome_chave,
                            "albedo": alb,
                            "altura_m": h,
                            "inclinacao_deg": inc,
                            "azimute_deg": azi,
                            "hsp_monofacial": round(m_val, 3),
                            "hsp_bifacial": round(b_val, 3),
                            "ganho_percentual": round(ganho, 2),
                            "perda_sombra": perda_sombra
                        })
                        
                        print(f"{alb:>5.1f} | {h:>5}m | {inc:>4}° | {azi:>4}° | {m_val:>9.3f} | {b_val:>9.3f} | {ganho:>7.1f}% | {perda_sombra:>12}")
        
    if all_results:
        SolarExporter.export_to_csv("SIMULACAO_HSP_BIFACIAL", all_results)
        
    print(f"\n[FIM] Simulação concluída. Verifique a pasta 'data/' para os resultados.")

def run_deep_validation():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    loc_path = os.path.join(project_root, 'data', 'localidades.json')
    gabarito_path = os.path.join(project_root, 'data', 'amostragem_sundata.json')

    if not os.path.exists(loc_path) or not os.path.exists(gabarito_path):
        print("❌ Erro: Arquivos não encontrados.")
        return

    with open(loc_path, 'r', encoding='utf-8') as f:
        locs = json.load(f)
    with open(gabarito_path, 'r', encoding='utf-8') as f:
        gabarito = json.load(f)

    # Lista para armazenar os dados do CSV
    export_data = []

    print("\n" + "="*110)
    print(f"{'CIDADE':<15} | {'ANG':>3} | {'NASA (API)':>10} | {'SUN_DATA':>10} | {'ERRO API%':>9} | {'G.ANG API%':>10} | {'G.ANG SUN%':>10}")
    print("-" * 110)

    for cidade_nome, inclinações in gabarito.items():
        coords = None
        for estado in locs.values():
            for c in estado['cidades']:
                if c['nome'].strip().lower() == cidade_nome.strip().lower():
                    coords = c
                    break
        
        if not coords: continue

        gateway = NasaPowerGateway(coords['latitude'], coords['longitude'])
        dados_clima = SolarDataService.standardize_data(gateway.fetch_climatology())

        api_ref_0 = None
        sun_ref_0 = None
        sorted_incs = sorted(inclinações.keys(), key=int)

        for inc_str in sorted_incs:
            inc = int(inc_str)
            
            res = calcular_projeto_solar(
                coords['latitude'], coords['longitude'], 
                inclinacao=inc, azimute=0, albedo=0.2, altura=1.5,
                tecnologia="TOPCON", is_bifacial=False, 
                dados_pre_carregados=dados_clima
            )

            hsp_api = res["media"]
            hsp_sun = inclinações[inc_str].get("Anual", 0)
            erro_fontes = ((hsp_api / hsp_sun) - 1) * 100 if hsp_sun > 0 else 0

            # Cálculos de Ganho Angular
            val_g_ang_api = 0.0
            val_g_ang_sun = 0.0

            if inc == 0:
                api_ref_0 = hsp_api
                sun_ref_0 = hsp_sun
                g_ang_api_str = "---"
                g_ang_sun_str = "---"
            else:
                val_g_ang_api = ((hsp_api / api_ref_0) - 1) * 100 if api_ref_0 else 0
                val_g_ang_sun = ((hsp_sun / sun_ref_0) - 1) * 100 if sun_ref_0 else 0
                g_ang_api_str = f"{val_g_ang_api:>+6.1f}%"
                g_ang_sun_str = f"{val_g_ang_sun:>+6.1f}%"

            # Print no terminal
            print(f"{cidade_nome:<15} | {inc:>3}° | {hsp_api:>10.2f} | {hsp_sun:>10.2f} | {erro_fontes:>8.1f}% | {g_ang_api_str:>10} | {g_ang_sun_str:>10}")

            # Adiciona à lista de exportação (convertendo strings de % para números para facilitar análise no Excel)
            export_data.append({
                "Cidade": cidade_nome,
                "Angulo": inc,
                "HSP_NASA_API": round(hsp_api, 3),
                "HSP_SUN_DATA": round(hsp_sun, 3),
                "Erro_Fontes_Percent": round(erro_fontes, 2),
                "Ganho_Angular_API_Percent": round(val_g_ang_api, 2) if inc != 0 else 0,
                "Ganho_Angular_SunData_Percent": round(val_g_ang_sun, 2) if inc != 0 else 0
            })

    # Exportação Final usando Pandas
    if export_data:
        df = pd.DataFrame(export_data)
        output_path = os.path.join(project_root, 'data', 'ANALISE_COMPLETA_VALIDACAO.csv')
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print("\n" + "="*110)
        print(f"✅ Análise exportada com sucesso para: {output_path}")

def run_transposition_test():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    loc_path = os.path.join(project_root, 'data', 'localidades.json')
    gabarito_path = os.path.join(project_root, 'data', 'amostragem_sundata.json')

    with open(loc_path, 'r', encoding='utf-8') as f:
        locs = json.load(f)
    with open(gabarito_path, 'r', encoding='utf-8') as f:
        gabarito = json.load(f)

    print("\n" + "="*100)
    print(f"{'CIDADE':<15} | {'ANG':>3} | {'REAL 0°':>8} | {'ESTIMADO':>10} | {'REAL ANG':>10} | {'DIFERENÇA'}")
    print("-" * 100)

    results = []

    for cidade_nome, inclinações in gabarito.items():
        coords = None
        for estado in locs.values():
            for c in estado['cidades']:
                if c['nome'].strip().lower() == cidade_nome.strip().lower():
                    coords = c
                    break
        if not coords: continue

        gateway = NasaPowerGateway(coords['latitude'], coords['longitude'])
        dados_clima = SolarDataService.standardize_data(gateway.fetch_climatology())

        # Passo 1: Pegar a base real de 0 graus do SunData
        real_sundata_0 = inclinações.get("0", {}).get("Anual")
        
        # Passo 2: Calcular o valor simulado a 0 para criar o fator de proporção
        sim_0 = calcular_projeto_solar(coords['latitude'], coords['longitude'], 0, 0, 0.2, 1.5, "TOPCON", False, dados_clima)["media"]

        for inc_str, ref_data in inclinações.items():
            inc = int(inc_str)
            if inc == 0: continue # Pula a referência

            # Passo 3: Calcular o valor simulado para o ângulo alvo
            sim_alvo = calcular_projeto_solar(coords['latitude'], coords['longitude'], inc, 0, 0.2, 1.5, "TOPCON", False, dados_clima)["media"]
            
            # Passo 4: O fator de ganho do seu motor
            fator_transposicao = sim_alvo / sim_0
            
            # Passo 5: Aplicar o seu fator à base real do SunData
            hsp_estimado = real_sundata_0 * fator_transposicao
            hsp_real_angulo = ref_data.get("Anual")
            
            erro_transp = ((hsp_estimado / hsp_real_angulo) - 1) * 100

            print(f"{cidade_nome:<15} | {inc:>3}° | {real_sundata_0:>8.2f} | {hsp_estimado:>10.2f} | {hsp_real_angulo:>10.2f} | {erro_transp:>+8.2f}%")
            
            results.append({
                "Cidade": cidade_nome,
                "Angulo": inc,
                "Base_0_Real": real_sundata_0,
                "Estimado_pela_API": round(hsp_estimado, 3),
                "Real_no_Gabarito": hsp_real_angulo,
                "Erro_da_Logica_%": round(erro_transp, 2)
            })

    if results:
        df = pd.DataFrame(results)
        df.to_csv(os.path.join(project_root, 'data', 'TESTE_TRANSPOSICAO_PURA.csv'), index=False, encoding='utf-8-sig')
        print("="*100)
        print("✅ Teste de transposição concluído e salvo em 'data/'.")

def run_shadow_debug_test():
    print("\n" + "="*50)
    print("🔍 TESTE DE SENSIBILIDADE DE SOMBRA")
    print("="*50)
    
    config = SCENARIOS["validacao_sombra"]
    lat, lon = config["lat"], config["lon"]
    
    # Pré-carregamento dos dados para ser rápido
    gateway = NasaPowerGateway(lat, lon)
    dados_clima = SolarDataService.standardize_data(gateway.fetch_climatology())
    
    results = []
    
    for caso in config["casos"]:
        # Monta a config de obstáculo (ou None se h=0)
        obs_config = None
        if caso["h_obs"] > 0:
            obs_config = {
                'height': caso["h_obs"],
                'distance': caso["d_obs"],
                'azimuth': caso["azi_obs"]
            }
            
        res = calcular_projeto_solar(
            lat=lat, lon=lon, inclinacao=config["inclinacoes"], azimute=config["azimutes"],
            albedo=0.2, altura=0.2, tecnologia="TOPCON",
            is_bifacial=True, panel_width=2.278,
            dados_pre_carregados=dados_clima,
            obstacle_config=obs_config
        )
        
        perda_str = res.get("perda_sombreamento_estimada", "0%")
        
        print(f"[{caso['label']}] -> Alt: {caso['h_obs']}m | Dist: {caso['d_obs']}m | Azi_Obs: {caso['azi_obs']}°")
        print(f"   >>> Perda: {perda_str} | HSP Médio: {res['media']}\n")
        
        results.append({
            "Cenário": caso["label"],
            "Altura_Obs": caso["h_obs"],
            "Dist_Obs": caso["d_obs"],
            "Azi_Obs": caso["azi_obs"],
            "Perda_%": perda_str,
            "HSP_Final": res["media"]
        })

    # Opcional: Salvar em CSV para análise
    df = pd.DataFrame(results)
    df.to_csv("data/DEBUG_SOMBRA.csv", index=False)
    print("✅ Debug de sombra concluído e salvo em 'data/DEBUG_SOMBRA.csv'.")

if __name__ == "__main__":
    while True:
        print("\n" + "="*50)
        print("        PAINEL DE TESTES E VALIDAÇÃO SOLAR")
        print("="*50)
        print(" [1] Simulação Técnica (Cenários/Bifacial)")
        print(" [2] Comparativo de Fontes (SunData vs NASA)")
        print(" [3] Teste de Transposição Pura (Lógica da API)")
        print(" [4] Debug de Sombra (Teste de Sensibilidade)")
        print(" [5] Executar Todos os Testes")
        print(" [0] Sair")
        print("="*50)
        
        escolha = input("Selecione uma opção: ").strip()

        if escolha == "1":
            run_simulation()
        elif escolha == "2":
            run_deep_validation()
        elif escolha == "3":
            run_transposition_test()
        elif escolha == "4":
            run_shadow_debug_test()
        elif escolha == "5":
            print("\n🚀 Iniciando bateria completa de testes...")
            run_simulation()
            run_deep_validation()
            run_transposition_test()
            run_shadow_debug_test()
            print("\n✅ Todos os relatórios foram gerados na pasta 'data/'.")
        elif escolha == "0":
            print("\nEncerrando... Até logo!")
            break
        else:
            print("\n⚠️ Opção inválida! Tente novamente.")