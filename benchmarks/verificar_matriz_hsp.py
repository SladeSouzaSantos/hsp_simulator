"""Auditoria de 40 configurações para HSP Simulator v2.0 (branch dev).

Uso: a partir da raiz, executar `python -m benchmarks.verificar_matriz_hsp`.
Força NASA POWER e usa exatamente o intervalo padrão configurado no provider
(NASA_START_YEAR / NASA_END_YEAR; 2022-2024 se ausentes).
NÃO altera o repositório nem faz deploy; escreve CSV local.
"""
import csv
import math
from pathlib import Path
import sys

from core.solar_physics import compute_poa, summarize_poa
from services.deps import Dependencies

LAT = -5.79448
LON = -35.21101
TILTS = (0, 15, 20, 45, 90)
AZIMUTHS = (0, 45, 90, 135, 180, 225, 270, 360)
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "documents" / "MATRIZ_HSP_AZIMUTE_NATAL.csv"


def main():
    repo = Dependencies.get_solar_repository()
    dados = repo.get_standardized_data(LAT, LON, force_provider="NASA POWER")
    weather = dados["hourly"]
    print("Fonte:", dados["metadata"])
    print("Latitude:", LAT, "Longitude:", LON)
    print("Condições: Perez, monofacial, albedo 0.20, sem sombra")
    print("".ljust(76, "-"))
    rows = []
    for inc in TILTS:
        for azi in AZIMUTHS:
            poa = compute_poa(weather, LAT, LON, inc, azi,
                albedo=0.20, model="perez", bifaciality=None, obstacle=None)
            d = summarize_poa(poa)
            row = {
                "inclinacao_graus":inc, "azimute_graus":azi,
                "hsp_frontal_kwh_m2_dia":d["hsp_frontal_media"],
                "hsp_horizontal_kwh_m2_dia":d["hsp_horizontal_media"],
                "diferenca_horizontal_kwh_m2_dia":round(d["hsp_frontal_media"]-d["hsp_horizontal_media"],3),
            }
            rows.append(row)
            print(f"inclinação={inc:2d}º  azimute={azi:3d}º  HSP={row['hsp_frontal_kwh_m2_dia']:.3f}  "+
                  f"horizontal={row['hsp_horizontal_kwh_m2_dia']:.3f}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("\nTABELA (kWh/m²/dia):")
    print("Inclinação | " + " | ".join(f"{az:>6}º" for az in AZIMUTHS))
    for inc in TILTS:
        row = [r for r in rows if r["inclinacao_graus"]==inc]
        print(f"{inc:>9}º | " + " | ".join(f"{r['hsp_frontal_kwh_m2_dia']:>7.3f}" for r in row))
    violations=[]
    for inc in TILTS:
        vals={r["azimute_graus"]:r["hsp_frontal_kwh_m2_dia"] for r in rows if r["inclinacao_graus"]==inc}
        if not math.isclose(vals[0],vals[360],abs_tol=0.001):
            violations.append(f"inclinação {inc}º: 0º != 360º ({vals[0]} vs {vals[360]})")
    flat=[r for r in rows if r["inclinacao_graus"]==0]
    for r in flat:
        if not math.isclose(r["hsp_frontal_kwh_m2_dia"],r["hsp_horizontal_kwh_m2_dia"],abs_tol=0.001):
            violations.append(f"horizontal azimute {r['azimute_graus']}º: HSP != GHI")
    # Verificação independente da convenção física do azimute.
    # Ao meio-dia solar aproximado de junho, o Sol está ao norte de Natal;
    # em dezembro, ao sul. Uma face 0° deve apresentar menor AOI em junho,
    # enquanto uma face 180° apresenta menor AOI em dezembro.
    import pandas as pd
    import pvlib
    for date_utc, preferred in (("2024-06-21T15:00:00Z", "norte"),
                                ("2024-12-21T15:00:00Z", "sul")):
        t = pd.DatetimeIndex([pd.Timestamp(date_utc)])
        sp = pvlib.solarposition.get_solarposition(t, LAT, LON)
        zen = float(sp["apparent_zenith"].iloc[0])
        solar_az = float(sp["azimuth"].iloc[0])
        aoi_n = float(pvlib.irradiance.aoi(45, 0, zen, solar_az))
        aoi_s = float(pvlib.irradiance.aoi(45, 180, zen, solar_az))
        print(f"Sol em {date_utc[:10]}: azimute solar={solar_az:.1f}º "
              f"AOI norte(0º)={aoi_n:.1f}º AOI sul(180º)={aoi_s:.1f}º")
        if preferred == "norte" and not aoi_n < aoi_s:
            violations.append("em junho, AOI da face Norte não ficou menor que Sul")
        if preferred == "sul" and not aoi_s < aoi_n:
            violations.append("em dezembro, AOI da face Sul não ficou menor que Norte")
    if violations:
        print("\nINCONSISTÊNCIAS:")
        for v in violations: print("-",v)
        return 1
    print("\nPASSOU: plano horizontal invariável, e azimutes 0º=360º para as cinco inclinações.")
    print("Convenção de superfície do pvlib: 0º = Norte, 90º = Leste, 180º = Sul, 270º = Oeste.")
    print("CSV salvo em:", OUTPUT)
    return 0

if __name__ == "__main__":
    sys.exit(main())
