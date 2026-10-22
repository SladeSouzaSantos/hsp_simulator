"""Benchmark horário: motor HSP x cálculo de referência direto com pvlib.

Todos os cálculos de plano inclinado utilizam a MESMA série horária
GHI/DHI/DNI em W/m². SunData é apenas referência climática externa:
seus períodos, fontes e modelos podem diferir da NASA POWER/PVGIS.

ATENÇÃO: ``perez_legacy`` é um alias do motor pvlib, não é mais um
segundo modelo independente. Este benchmark verifica o *encadeamento*
do motor contra uma chamada direta ao pvlib; não é validação PVsyst.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from core.perez_engines.perez_engine import PerezEngine
from core.solar_physics import validate_weather
from services.deps import Dependencies

ROOT = Path(__file__).resolve().parents[1]
SUNDATA_FILE = ROOT / 'tests' / 'fixtures' / 'amostragem_sundata.json'
OUTPUT_DIR = ROOT / 'benchmarks' / 'documents'
CITIES = {
    'Natal': (-5.79448, -35.21101),
    'Caico': (-6.45, -37.09),
    'Petrolina': (-9.38, -40.50),
    'Manaus': (-3.11, -60.02),
    'Porto Alegre': (-30.03, -51.23),
    'Sao Jose dos Campos': (-23.17, -45.88),
}
TILTS_GRID = (0, 15, 20, 45, 90)
AZIMUTHS_GRID = (0, 45, 90, 135, 180, 225, 270, 360)


def _pvlib_reference_hsp(hourly: pd.DataFrame, lat: float, lon: float,
                         tilt: float, azimuth: float, *, albedo: float = 0.2) -> float:
    """Referência direta ao pvlib, sem chamar SolarEngine ou compute_poa.

    Repete DELIBERADAMENTE as mesmas convenções horárias usadas no motor:
    timestamps UTC marcando início de cada intervalo, posição a +30 min,
    irradiâncias em W/m², integração dos dias completos de 24 horas.
    Assim verifica o contrato/encadeamento da aplicação, não a física do
    próprio algoritmo Perez da biblioteca, que é compartilhado.
    """
    import pvlib

    weather = validate_weather(hourly)
    if tilt == 0:
        poa = weather['ghi'].to_numpy(dtype=float)
    else:
        midpoint = weather.index + pd.Timedelta(minutes=30)
        sol = pvlib.location.Location(lat, lon, tz='UTC').get_solarposition(midpoint)
        zenith = sol['apparent_zenith'].to_numpy(dtype=float)
        sun_azimuth = sol['azimuth'].to_numpy(dtype=float)
        result = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azimuth,
            solar_zenith=zenith,
            solar_azimuth=sun_azimuth,
            dni=weather['dni'].to_numpy(dtype=float),
            ghi=weather['ghi'].to_numpy(dtype=float),
            dhi=weather['dhi'].to_numpy(dtype=float),
            dni_extra=np.asarray(pvlib.irradiance.get_extra_radiation(midpoint)),
            airmass=np.asarray(pvlib.atmosphere.get_relative_airmass(zenith)),
            albedo=albedo,
            model='perez',
        )
        poa = np.clip(
            np.nan_to_num(np.asarray(result['poa_global'], dtype=float), nan=0., posinf=0.),
            0., None,
        )
    hourly_poa = pd.Series(poa, index=weather.index)
    per_day = hourly_poa.resample('D').sum().div(1000.)
    complete_days = hourly_poa.resample('D').count() == 24
    if not complete_days.any():
        raise ValueError('Não há dias completos na série meteorológica')
    return float(per_day.loc[complete_days].mean())


def _load_hourly(repo, lat: float, lon: float, source: str,
                 synthetic: bool) -> dict:
    if synthetic:
        # Somente ensaio determinístico, NUNCA comparação científica com SunData.
        from tests.fixtures.hourly_weather import climate_fixture
        return climate_fixture(lat, lon)
    return repo.get_standardized_data(lat, lon, force_provider=source)


def _run_engine(climate: dict, lat: float, lon: float,
                tilt: int, azimuth: int) -> float:
    engine = PerezEngine(lat=lat, lon=lon, inclinacao_deg=tilt,
                         azimute_deg=azimuth, model='perez', albedo=0.2,
                         is_bifacial=False)
    return float(engine.calcular_hsp_corrigido_inc_azi(climate)['media'])


def _pct(value: float, reference: float) -> float:
    return 100. * (value / reference - 1.) if reference else float('nan')


def run_mass_comparison(*, cities: Iterable[str] | None = None,
                        source: str = 'NASA POWER',
                        synthetic: bool = False,
                        repository=None,
                        output_dir: Path = OUTPUT_DIR) -> pd.DataFrame:
    """Compara casos SunData contra a transposição em dados horários reais.

    A comparação com SunData usa duas métricas: desvio absoluto (mistura
    diferenças meteorológicas e de modelos) e desvio após normalização pelo
    GHI horizontal do próprio SunData (isola parcialmente o fator de transposição).
    """
    import json
    with SUNDATA_FILE.open(encoding='utf-8') as file:
        sundata = json.load(file)
    repo = repository if repository is not None else Dependencies.get_solar_repository()
    selected = list(CITIES) if cities is None else list(cities)
    rows = []

    print('=' * 114)
    print('HSP SIMULATOR — comparativo horário: engine x pvlib; SunData como referência EXTERNA')
    print(f'Fonte: {"CÉU CLARO SINTÉTICO — NÃO VALIDAR PRECISÃO" if synthetic else source}; Perez; monofacial; albedo 0,20; azimute 0°=Norte')
    print(f'{"Cidade":<20} {"Inc":>4} {"SunData":>9} {"Engine":>9} {"PVLib":>9} {"Delta E-P":>11} {"Erro SD":>10} {"Erro Transp":>12}')
    print('-' * 114)
    for city in selected:
        if city not in CITIES:
            raise ValueError(f'Cidade inválida: {city}; opções: {list(CITIES)}')
        if city not in sundata:
            print(f'[AVISO] Sem dados SunData para {city}; ignorando.')
            continue
        lat, lon = CITIES[city]
        # OBTENÇÃO UMA VEZ POR CIDADE; mantém hourly até o fim.
        climate = _load_hourly(repo, lat, lon, source, synthetic)
        if 'hourly' not in climate:
            raise ValueError(f'Fonte {source} não forneceu série horária para {city}; não é válido usar médias mensais')
        weather = validate_weather(climate['hourly'])
        weather_source = climate.get('metadata', {}).get('source', source)
        ghi_horizontal = float(weather['ghi'].resample('D').sum().div(1000.).loc[
            weather['ghi'].resample('D').count() == 24].mean())
        sundata_horizontal = float(sundata[city]['0']['Anual'])
        for tilt_text, sd in sundata[city].items():
            tilt = int(tilt_text)
            target = float(sd['Anual'])
            hsp_engine = _run_engine(climate, lat, lon, tilt, 0)
            hsp_reference = _pvlib_reference_hsp(weather, lat, lon, tilt, 0)
            scaled_to_sundata = sundata_horizontal * hsp_engine / ghi_horizontal
            row = {
                'Cidade': city,
                'Latitude': lat,
                'Longitude': lon,
                'Inclinacao': tilt,
                'Azimute_Geografico': 0,
                'Fonte_Meteorologica': weather_source,
                'Anos': climate.get('metadata', {}).get('years', 'fixture sintética'),
                'HSP_SunData': round(target, 3),
                'HSP_Horizontal_Fonte': round(ghi_horizontal, 4),
                'HSP_Minha_Engine': round(hsp_engine, 3),
                'HSP_PVLib': round(hsp_reference, 3),
                'Delta_Engine_PVLib_Pct': round(_pct(hsp_engine, hsp_reference), 3),
                'Erro_Engine_vs_SunData_Pct': round(_pct(hsp_engine, target), 2),
                'HSP_Escala_SunData_GHI': round(scaled_to_sundata, 3),
                'Erro_Fator_Transposicao_SunData_Pct': round(_pct(scaled_to_sundata, target), 2),
                'Dados_Sinteticos': synthetic,
            }
            rows.append(row)
            print(f'{city:<20} {tilt:>3}° {target:>9.3f} {hsp_engine:>9.3f} {hsp_reference:>9.3f} '
                  f'{row["Delta_Engine_PVLib_Pct"]:>+10.3f}% '
                  f'{row["Erro_Engine_vs_SunData_Pct"]:>+9.2f}% '
                  f'{row["Erro_Fator_Transposicao_SunData_Pct"]:>+11.2f}%')
    if not rows:
        raise RuntimeError('Nenhum cenário executado; CSV não será criado.')
    table = pd.DataFrame(rows)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / 'BENCHMARK_ENGINE_VS_PVLIB.csv'
    table.to_csv(path, index=False, encoding='utf-8-sig')
    print('-' * 114)
    print('MAE Engine vs pvlib (p.p.):', round(table['Delta_Engine_PVLib_Pct'].abs().mean(), 3))
    print('MAE vs SunData (%, bases meteorológicas distintas):',
          round(table['Erro_Engine_vs_SunData_Pct'].abs().mean(), 2))
    print('MAE de fator de transposição vs SunData (%):',
          round(table['Erro_Fator_Transposicao_SunData_Pct'].abs().mean(), 2))
    print('Relatório:', path)
    return table


def run_orientation_grid(*, city: str = 'Natal', source: str = 'NASA POWER',
                         synthetic: bool = False, repository=None,
                         output_dir: Path = OUTPUT_DIR) -> pd.DataFrame:
    """40 combinações independentes do slider, cruzadas com pvlib direto."""
    if city not in CITIES:
        raise ValueError('Cidade inválida: ' + city)
    repo = repository if repository is not None else Dependencies.get_solar_repository()
    lat, lon = CITIES[city]
    climate = _load_hourly(repo, lat, lon, source, synthetic)
    if 'hourly' not in climate:
        raise ValueError('Benchmark de orientação exige GHI/DHI/DNI horários (W/m²).')
    hourly = validate_weather(climate['hourly'])
    rows = []
    for tilt in TILTS_GRID:
        for azimuth in AZIMUTHS_GRID:
            engine = _run_engine(climate, lat, lon, tilt, azimuth)
            ref = _pvlib_reference_hsp(hourly, lat, lon, tilt, azimuth)
            rows.append({'Cidade':city, 'Inclinacao':tilt, 'Azimute':azimuth,
                         'HSP_Engine':round(engine,3), 'HSP_PVLib':round(ref,3),
                         'Delta_Engine_PVLib_Pct':round(_pct(engine, ref),3),
                         'Fonte_Meteorologica':climate.get('metadata',{}).get('source', source),
                         'Dados_Sinteticos':synthetic})
    table = pd.DataFrame(rows)
    for tilt in TILTS_GRID:
        values = table.loc[table['Inclinacao'] == tilt].set_index('Azimute')['HSP_Engine']
        if abs(float(values.loc[0]) - float(values.loc[360])) > 0.001:
            raise AssertionError(f'0° != 360° para inclinação={tilt}')
        if tilt == 0 and values.max() - values.min() > 0.001:
            raise AssertionError('Plano horizontal varia com azimute')
    out = Path(output_dir) / 'BENCHMARK_ORIENTACOES_ENGINE_VS_PVLIB.csv'
    out.parent.mkdir(parents=True,exist_ok=True)
    table.to_csv(out, index=False, encoding='utf-8-sig')
    print('\nMatriz de orientação — ' + city)
    print(table.pivot(index='Inclinacao', columns='Azimute', values='HSP_Engine').to_string())
    print('40 cenários; plano horizontal e 0°=360°: OK. Relatório:', out)
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city', choices=tuple(CITIES), help='Cidade específica (padrão: todas)')
    parser.add_argument('--source', default='NASA POWER', choices=('NASA POWER', 'PVGIS'),
                        help='Fonte horária explícita; evita fallback silencioso')
    parser.add_argument('--synthetic', action='store_true',
                        help='Usa céu claro sintético para verificar o código, não para validação científica')
    parser.add_argument('--grid', action='store_true',
                        help='Além do SunData, executa 40 orientações da cidade selecionada (padrão Natal)')
    args = parser.parse_args(argv)
    run_mass_comparison(cities=[args.city] if args.city else None,
                        source=args.source, synthetic=args.synthetic)
    if args.grid:
        run_orientation_grid(city=args.city or 'Natal', source=args.source,
                             synthetic=args.synthetic)
    print('\nNOTA: PerezEngine e PerezEnginePVLib hoje usam a MESMA implementação pvlib. '
          'Concordância neste relatório NÃO equivale à validação independente com PVsyst.')


if __name__ == '__main__':
    main()
