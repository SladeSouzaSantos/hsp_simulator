import json
import os
import pvlib
import numpy as np
import csv
from datetime import datetime
from core.perez_engines.perez_engine import PerezEngine

def run_mass_comparison():
    # 1. Carregar Dados da Fixture
    with open('tests/fixtures/amostragem_sundata.json', 'r', encoding='utf-8') as f:
        fixtures = json.load(f)
    
    coordenadas = {
        "Natal": {"lat": -5.79, "lon": -35.21},
        "Caico": {"lat": -6.45, "lon": -37.09},
        "Petrolina": {"lat": -9.38, "lon": -40.50},
        "Manaus": {"lat": -3.11, "lon": -60.02},
        "Porto Alegre": {"lat": -30.03, "lon": -51.23},
        "Sao Jose dos Campos": {"lat": -23.17, "lon": -45.88}
    }

    report_data = []
    erros_eng_abs = []
    erros_pv_abs = []

    header_terminal = (f"{'Cidade':<20} | {'Incl.':<5} | {'SunData':<7} | "
                       f"{'Eng HSP':<7} | {'PVL HSP':<7} | {'Erro Eng%':<9} | {'Erro PVL%'}")
    
    print("\n" + "="*85)
    print(header_terminal)
    print("-" * 85)

    for cidade, dados_cidade in fixtures.items():
        lat = coordenadas.get(cidade, 0)["lat"]
        lon = coordenadas.get(cidade, 0)["lon"]
        ghi_mensal = [v for k, v in dados_cidade["0"].items() if k != "Anual"]
        
        for incl, valores in dados_cidade.items():
            if incl == "0": continue 
            
            target_sd = valores["Anual"]
            incl_int = int(incl)

            # --- CÁLCULO PVLIB ---
            pv_results = []
            for ghi in ghi_mensal:
                dhi, dni = ghi * 0.3, ghi * 0.7
                res_pv = pvlib.irradiance.get_total_irradiance(
                    surface_tilt=incl_int, surface_azimuth=0,
                    solar_zenith=abs(lat - incl_int), solar_azimuth=0,
                    dni=dni, ghi=ghi, dhi=dhi, dni_extra=1367, model='perez'
                )
                pv_results.append(res_pv['poa_global'])
            hsp_pvlib = np.mean(pv_results)

            # --- CÁLCULO SUA ENGINE ---
            engine = PerezEngine(lat=lat, lon=lon, is_bifacial=False)
            dados_in = {'hsp_global': ghi_mensal, 'hsp_diffuse': [g*0.3 for g in ghi_mensal]}
            res_eng = engine.calcular_hsp_corrigido_inc_azi(dados_in, incl_int, 0)
            hsp_eng = res_eng['media_sem_sombra']
            
            err_eng = ((hsp_eng / target_sd) - 1) * 100
            err_pv = ((hsp_pvlib / target_sd) - 1) * 100
            
            erros_eng_abs.append(abs(err_eng))
            erros_pv_abs.append(abs(err_pv))
            
            # Armazenar dados para os arquivos
            item = {
                "Cidade": cidade, "Incl": f"{incl}°", "SunData": target_sd,
                "Eng_HSP": round(hsp_eng, 3), "PVL_HSP": round(hsp_pvlib, 3),
                "Erro_Eng_Pct": round(err_eng, 2), "Erro_PVL_Pct": round(err_pv, 2)
            }
            report_data.append(item)
            
            print(f"{cidade:<20} | {incl + '°':<5} | {target_sd:<7.2f} | "
                  f"{hsp_eng:<7.3f} | {hsp_pvlib:<7.3f} | {err_eng:>+9.2f}% | {err_pv:>+9.2f}%")

    media_final_eng = np.mean(erros_eng_abs)
    media_final_pv = np.mean(erros_pv_abs)

    footer = f"ERRO MÉDIO ABSOLUTO:        ENGINE: {media_final_eng:.2f}% | PVLIB: {media_final_pv:.2f}%"
    print("-" * 85); print(footer); print("=" * 85 + "\n")

    # --- CONFIGURAÇÃO DE DIRETÓRIO ---
    doc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
    if not os.path.exists(doc_dir):
        os.makedirs(doc_dir)

    nome_base = "RELATORIO_TECNICO_PRECISAO_SOLAR"
    
    # Exportação CSV
    with open(os.path.join(doc_dir, f'{nome_base}.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=report_data[0].keys())
        writer.writeheader()
        writer.writerows(report_data)

    # Exportação MD
    with open(os.path.join(doc_dir, f'{nome_base}.md'), 'w', encoding='utf-8') as f:
        f.write(f"# {nome_base.replace('_', ' ')}\n\n")
        f.write(f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        f.write(f"- **Erro Médio Engine:** {media_final_eng:.2f}%\n")
        f.write(f"- **Erro Médio PVLib:** {media_final_pv:.2f}%\n\n")
        f.write("| Cidade | Incl. | SunData | Eng HSP | PVL HSP | Erro Eng% | Erro PVL% |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for r in report_data:
            f.write(f"| {r['Cidade']} | {r['Incl']} | {r['SunData']} | {r['Eng_HSP']} | {r['PVL_HSP']} | {r['Erro_Eng_Pct']}% | {r['Erro_PVL_Pct']}% |\n")

    print(f"✅ Relatórios científicos gerados em: benchmarks/documents/")

if __name__ == "__main__":
    run_mass_comparison()