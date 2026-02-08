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
    
    # --- PRÉ-CARREGAMENTO (FORA DOS LOOPS) ---
    print(f"Buscando dados meteorológicos para {lat}, {lon}...")
    gateway = NasaPowerGateway(lat, lon)
    # Buscamos e já padronizamos uma única vez
    dados_clima = SolarDataService.standardize_data(gateway.fetch_climatology())

    print(f"\nINICIANDO TESTE TÉCNICO - PLACA: {PLACA_CADASTRADA['modelo']}")
    print(f"TECNOLOGIA: {PLACA_CADASTRADA['tecnologia']} | FATOR B: {CELL_TECHNOLOGY_REFERENCE[PLACA_CADASTRADA['tecnologia']]['fator_conservador']}")

    for nome_chave, config in SCENARIOS.items():
        print(f"\n{'='*85}")
        print(f" EXECUÇÃO: {config['descricao']}")
        print(f"{'='*85}")
        
        alturas = config.get('alturas_teste', [config.get('altura', 1.5)])
        albedos = config.get('albedos_teste', [config.get('albedo', 0.4)])
        
        header = f"{'ALB.':>5} | {'ALT.':>6} | {'INC.':>5} | {'AZI.':>5} | {'MONO HSP':>9} | {'BIFAC HSP':>9} | {'GANHO %':>8}"
        print(header)
        print("-" * 85)

        for alb in albedos:
            for h in alturas:
                for inc in config['inclinações']:
                    for azi in config['azimutes']:
                        # Passamos o 'dados_pre_carregados' para o app.py não bater na NASA novamente
                        res_mono = calcular_projeto_solar(
                            lat, lon, inc, azi, alb, h, 
                            tecnologia=PLACA_CADASTRADA["tecnologia"], 
                            panel_width=dimensao_L, 
                            is_bifacial=False, 
                            dados_pre_carregados=dados_clima
                        )
                        
                        res_bi = calcular_projeto_solar(
                            lat, lon, inc, azi, alb, h, 
                            tecnologia=PLACA_CADASTRADA["tecnologia"], 
                            panel_width=dimensao_L, 
                            is_bifacial=True, 
                            dados_pre_carregados=dados_clima
                        )
                        
                        m_val = res_mono["media"]
                        b_val = res_bi["media"]
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
                            "ganho_percentual": round(ganho, 2)
                        })
                        
                        print(f"{alb:>5.1f} | {h:>5}m | {inc:>4}° | {azi:>4}° | {m_val:>9.3f} | {b_val:>9.3f} | {ganho:>7.1f}%")
        
    if all_results:
        SolarExporter.export_to_csv("SIMULACAO_HSP_BIFACIAL", all_results)
        
    print(f"\n[FIM] Simulação concluída. Verifique a pasta 'data/' para os resultados.")

if __name__ == "__main__":
    run_simulation()