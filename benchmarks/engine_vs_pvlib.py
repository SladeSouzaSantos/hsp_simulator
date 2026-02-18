import json
import os
import csv
import pandas as pd
from datetime import datetime
from core.app import SolarEngine
from core.solar_engine_factory import SolarPerezEngineFactory
from services.deps import Dependencies

def run_mass_comparison():
    # 1. Setup do Ambiente
    repo = Dependencies.get_solar_repository()
    # A SolarEngine aqui servirá como orquestradora se necessário
    main_engine = SolarEngine(repository=repo)
    
    try:
        with open('tests/fixtures/amostragem_sundata.json', 'r', encoding='utf-8') as f:
            fixtures = json.load(f)
    except FileNotFoundError:
        print("[ERRO] Fixture SunData não encontrada.")
        return

    # Cidades para teste de estresse
    coordenadas = {
        "Natal": {"lat": -5.79, "lon": -35.21},
        "Caico": {"lat": -6.45, "lon": -37.09},
        "Petrolina": {"lat": -9.38, "lon": -40.50},
        "Manaus": {"lat": -3.11, "lon": -60.02},
        "Porto Alegre": {"lat": -30.03, "lon": -51.23},
        "Sao Jose dos Campos": {"lat": -23.17, "lon": -45.88}
    }

    report_data = []
    meses_ordem = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    print("=" * 100)
    print(f"{'Cidade':<15} | {'Inc':<3} | {'Gabarito':<8} | {'Sua Eng':<8} | {'PVLib':<8} | {'Erro Sua%':<9} | {'Erro PVL%'}")
    print("-" * 100)

    for cidade, coords in coordenadas.items():
        if cidade not in fixtures: continue
        
        # Busca dados reais via Repositório (NASA/INPE)
        dados_base_0 = fixtures[cidade]["0"]

        dados_clima = {
            "hsp_global": [float(dados_base_0[m]) for m in meses_ordem],
            "hsp_diffuse": [float(dados_base_0[m]) * 0.3 for m in meses_ordem], # Estimativa de difusa
            "temp_max": [30.0] * 12,
            "wind_speed": [3.0] * 12
        }
        
        for inc_str, dados_gabarito in fixtures[cidade].items():
            inc = int(inc_str)
            
            # --- TRATAMENTO DO GABARITO ---
            if isinstance(dados_gabarito, dict):
                # Prioriza a chave "Anual" que existe no seu JSON
                if "Anual" in dados_gabarito:
                    hsp_real = float(dados_gabarito["Anual"])
                else:
                    # Fallback caso a chave mude (calcula média dos meses numéricos)
                    meses_vals = [v for k, v in dados_gabarito.items() if k != "Anual" and isinstance(v, (int, float))]
                    hsp_real = sum(meses_vals) / len(meses_vals) if meses_vals else 0
            else:
                hsp_real = float(dados_gabarito)

            # --- MOTOR 1: SUA IMPLEMENTAÇÃO (PEREZ NATIVO) ---
            engine_type = SolarPerezEngineFactory.get_engine_type(motor_type="perez_legacy")
            my_perez = engine_type(lat=coords['lat'], lon=coords['lon'], inclinacao_deg=inc, azimute_deg=0)
            res_my = my_perez.calcular_hsp_corrigido_inc_azi(dados_clima)
            hsp_my = res_my["media"]

            # --- MOTOR 2: PVLIB WRAPPER ---
            pvlib_type = SolarPerezEngineFactory.get_engine_type(motor_type="perez_pvlib")
            pv_perez = pvlib_type(lat=coords['lat'], lon=coords['lon'], inclinacao_deg=inc, azimute_deg=0)
            res_pv = pv_perez.calcular_hsp_corrigido_inc_azi(dados_clima)
            hsp_pv = res_pv["media"]

            # --- CÁLCULO DE ERROS ---
            erro_my = ((hsp_my - hsp_real) / hsp_real) * 100
            erro_pv = ((hsp_pv - hsp_real) / hsp_real) * 100

            print(f"{cidade:<15} | {inc:>3}° | {hsp_real:<8.2f} | {hsp_my:<8.2f} | {hsp_pv:<8.2f} | {erro_my:>+8.2f}% | {erro_pv:>+8.2f}%")

            report_data.append({
                "Cidade": cidade,
                "Inclinacao": inc,
                "HSP_SunData": round(hsp_real, 3),
                "HSP_Minha_Engine": round(hsp_my, 3),
                "HSP_PVLib": round(hsp_pv, 3),
                "Erro_Minha_Pct": round(erro_my, 2),
                "Erro_PVLib_Pct": round(erro_pv, 2)
            })

    # --- EXPORTAÇÃO ---
    doc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
    os.makedirs(doc_dir, exist_ok=True)
    df = pd.DataFrame(report_data)
    df.to_csv(os.path.join(doc_dir, "BENCHMARK_ENGINE_VS_PVLIB.csv"), index=False)
    
    print("-" * 100)
    print(f"📊 Média Erro Absoluto (Sua): {df['Erro_Minha_Pct'].abs().mean():.2f}%")
    print(f"📊 Média Erro Absoluto (PVLib): {df['Erro_PVLib_Pct'].abs().mean():.2f}%")

def run_legacy_vs_pvlib_stress_test():
    # 1. Configuração de Variáveis e Step
    step = 5 # Variável de controle de resolução
    azimutes = range(0, 361, step)
    inclinacoes = range(0, 91, step)
    
    coordenadas = {
        "Natal": {"lat": -5.79, "lon": -35.21},
        "Caico": {"lat": -6.45, "lon": -37.09},
        "Petrolina": {"lat": -9.38, "lon": -40.50},
        "Manaus": {"lat": -3.11, "lon": -60.02},
        "Porto Alegre": {"lat": -30.03, "lon": -51.23},
        "Sao Jose dos Campos": {"lat": -23.17, "lon": -45.88}
    }

    # 2. Setup do Repositório (NASA POWER)
    repo = Dependencies.get_solar_repository()
    report_data = []

    print(f"🚀 Iniciando Comparativo: Legacy vs PVLib | Step: {step}°")
    print("=" * 90)
    print(f"{'Cidade':<15} | {'Azi':<4} | {'Inc':<4} | {'Legacy':<8} | {'PVLib':<8} | {'Delta %'}")
    print("-" * 90)

    for cidade, coords in coordenadas.items():
        # Busca dados da NASA uma única vez por cidade
        dados_clima = repo.get_standardized_data(coords['lat'], coords['lon'])
        
        for azi in azimutes:
            for inc in inclinacoes:
                # --- MOTOR 1: PEREZ LEGACY ---
                legacy_type = SolarPerezEngineFactory.get_engine_type(motor_type="perez_legacy")
                engine_legacy = legacy_type(lat=coords['lat'], lon=coords['lon'], inclinacao_deg=inc, azimute_deg=azi)
                hsp_legacy = engine_legacy.calcular_hsp_corrigido_inc_azi(dados_clima)["media"]

                # --- MOTOR 2: PEREZ PVLIB ---
                pvlib_type = SolarPerezEngineFactory.get_engine_type(motor_type="perez_pvlib")
                engine_pvlib = pvlib_type(lat=coords['lat'], lon=coords['lon'], inclinacao_deg=inc, azimute_deg=azi)
                hsp_pvlib = engine_pvlib.calcular_hsp_corrigido_inc_azi(dados_clima)["media"]

                # Cálculo de divergência entre os motores
                delta_pct = ((hsp_legacy - hsp_pvlib) / hsp_pvlib) * 100 if hsp_pvlib > 0 else 0

                report_data.append({
                    "Cidade": cidade,
                    "Azimute": azi,
                    "Inclinacao": inc,
                    "HSP_Legacy": round(hsp_legacy, 3),
                    "HSP_PVLib": round(hsp_pvlib, 3),
                    "Divergencia_Pct": round(delta_pct, 2)
                })

        print(f"✅ {cidade} finalizada.")

    # 3. Exportação para CSV
    df = pd.DataFrame(report_data)
    output_path = "benchmarks/documents/COMPARATIVO_LEGACY_VS_PVLIB_NASA.csv"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print("-" * 90)
    print(f"📊 Relatório gerado em: {output_path}")
    print(f"🔍 Divergência Média Global: {df['Divergencia_Pct'].abs().mean():.2f}%")

if __name__ == "__main__":
    run_mass_comparison()
    run_legacy_vs_pvlib_stress_test()