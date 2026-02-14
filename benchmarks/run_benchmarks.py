from core.app import SolarEngine
from services.deps import Dependencies
from benchmarks.auditor import SolarAuditor
from utils.exporter import SolarExporter

# Inicializa o ecossistema oficial
repo = Dependencies.get_solar_repository()
engine = SolarEngine(repository=repo)
auditor = SolarAuditor(engine)

def main():
    print("="*60)
    print("       HSP SIMULATOR: SISTEMA DE AUDITORIA UNIFICADO")
    print("="*60)
    
    # --- TESTE 1: SENSIBILIDADE DE SOMBRA ---
    # Valida a geometria de obstáculos (muros, prédios, postes)
    print("\n[1/2] Executando Auditoria de Sombra...")
    dados_sombra = auditor.rodar_benchmark_sombra()
    SolarExporter.export_to_csv("BENCHMARK_SOMBRA_FINAL.csv", dados_sombra)
    
    # --- TESTE 2: VALIDAÇÃO CRESESB (TRANSPOSIÇÃO) ---
    # Valida se a matemática de Perez/Hay-Davies bate com dados reais do SunData
    print("\n[2/2] Validando Transposição contra Gabarito CRESESB...")
    try:
        dados_cresesb = auditor.validar_transposicao_cresesb()
        if dados_cresesb:
            SolarExporter.export_to_csv("VALIDACAO_CRESESB_ATTESTED.csv", dados_cresesb)
        else:
            print("[AVISO] Nenhum dado retornado da validação CRESESB.")
    except Exception as e:
        print(f"[ERRO] Falha na validação CRESESB: {e}")

    print("\n" + "="*60)
    print("✅ Auditoria Completa: Relatórios gerados na pasta /data")
    print("="*60)

if __name__ == "__main__":
    main()