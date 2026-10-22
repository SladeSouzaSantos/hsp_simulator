"""Compara a matriz de HSP do projeto com a irradiacao horaria no plano do PVGIS.

Execute a partir da raiz do hsp_simulator (ambiente com pvlib instalado):
    python -m benchmarks.comparar_hsp_pvgis --max-new-calls 3
    python -m benchmarks.comparar_hsp_pvgis

A comparacao absoluta usa bancos meteorologicos diferentes e NAO valida a
precisao da transposicao isoladamente; veja o fator de transposicao FT.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import math
import sys
import time
from pathlib import Path

LAT, LON = -5.79448, -35.21101
ROOT = Path(__file__).resolve().parents[1]
CSV_IN = ROOT / 'benchmarks/documents/MATRIZ_HSP_AZIMUTE_NATAL.csv'
CSV_OUT = ROOT / 'benchmarks/documents/COMPARATIVO_HSP_PVGIS_NATAL.csv'
CACHE = ROOT / 'benchmarks/documents/cache_pvgis_validacao'
PVGIS_URL = 'https://re.jrc.ec.europa.eu/api/v5_3/'


def canonical_geometry(tilt: int, azimuth: int) -> tuple[int, int]:
    # Geometria fisica redundante: plano horizontal nao tem azimute;
    # 360 graus e 0 graus descrevem a mesma face.
    return (tilt, 0 if tilt == 0 else azimuth % 360)


def read_matrix(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f'Matriz ausente: {path}. Execute python -m benchmarks.verificar_matriz_hsp')
    result = []
    with path.open('r', newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            tilt = int(row['inclinacao_graus'])
            az = int(row['azimute_graus'])
            result.append({
                'tilt': tilt, 'azimuth': az,
                'local_hsp': float(row['hsp_frontal_kwh_m2_dia']),
                'local_ghi': float(row['hsp_horizontal_kwh_m2_dia']),
            })
    expected = {(t, a) for t in (0, 15, 20, 45, 90) for a in (0, 45, 90, 135, 180, 225, 270, 360)}
    actual = {(r['tilt'], r['azimuth']) for r in result}
    if actual != expected or len(result) != 40:
        raise ValueError(f'A matriz deve possuir exatamente 40 combinacoes unicas; encontrados {len(result)} registros, {len(actual)} pares')
    if any(r['local_ghi'] <= 0 for r in result):
        raise ValueError('HSP horizontal invalida no CSV')
    return result


def cache_path(year: int, t: int, a: int, database: str | None) -> Path:
    db = database or 'automatico'
    return CACHE / f'natal_lat-5p79448_lon-35p21101_{year}_{db}_inc{t}_az{a}.json'


def read_reference(year: int, t: int, a: int, database: str | None, timeout: int) -> dict:
    """Retorna HSP do PVGIS, usando azimute pvlib 0=N, 90=L, 180=S, 270=O.

    O wrapper do pvlib converte automaticamente para PVGIS (aspect=az-180).
    IMPORTANTE: nao subtrair 180 graus manualmente neste metodo.
    """
    import pandas as pd
    from pvlib.iotools import get_pvgis_hourly

    kwargs = dict(
        latitude=LAT, longitude=LON, start=year, end=year,
        surface_tilt=t, surface_azimuth=a,
        components=False, pvcalculation=False,
        outputformat='json', usehorizon=False,
        map_variables=True, timeout=timeout, url=PVGIS_URL,
    )
    if database:
        kwargs['raddatabase'] = database
    response = get_pvgis_hourly(**kwargs)
    data, metadata = response[0], response[1]
    if 'poa_global' not in data.columns:
        raise ValueError(f'PVGIS nao retornou poa_global; colunas={list(data.columns)}')
    points = pd.to_numeric(data['poa_global'], errors='coerce')
    if points.isna().any() or (points < 0).any() or (points > 1500).any():
        raise ValueError('Serie PVGIS possui amostras ausentes/invalidas')
    dates = pd.to_datetime(data.index, utc=True)
    expected = (366 if calendar.isleap(year) else 365) * 24
    if len(points) != expected or (dates.year != year).any():
        raise ValueError(f'Esperadas {expected} horas em {year}, PVGIS retornou {len(points)}')
    if dates.has_duplicates or not (dates.to_series().diff().dropna().dt.total_seconds() == 3600).all():
        raise ValueError('Amostras PVGIS nao sao horarios continuos de 1h')
    month_data = {f'{m:02d}': round(float(points[dates.month == m].sum() / 1000 / calendar.monthrange(year, m)[1]), 5)
                  for m in range(1, 13)}
    return {'year': year, 'tilt': t, 'azimuth': a, 'hsp': float(points.sum() / 1000 / (expected / 24)),
            'monthly_hsp': month_data, 'hours': expected,
            'database_request': database or 'automatico', 'metadata': str(metadata)[:600]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Benchmark externo da matriz NASA/pvlib contra PVGIS hourly POA')
    parser.add_argument('--year', type=int, default=2020, help='Ano PVGIS (2020 por padrao, evitando cobertura incerta de anos recentes)')
    parser.add_argument('--database', default=None, help='Banco PVGIS opcional (ex.: PVGIS-ERA5)')
    parser.add_argument('--max-new-calls', type=int, default=None, help='Limita downloads NOVOS; ideal para teste inicial: 3')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--delay', type=float, default=1.0, help='Intervalo entre requisicoes')
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--matrix', type=Path, default=CSV_IN)
    parser.add_argument('--output', type=Path, default=CSV_OUT)
    args = parser.parse_args(argv)
    if not 2010 <= args.year <= 2024:
        parser.error('Use ano PVGIS entre 2010 e 2024; a disponibilidade real varia conforme o banco')
    matrix = read_matrix(args.matrix)
    unique = sorted({canonical_geometry(r['tilt'], r['azimuth']) for r in matrix})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f'Matriz local: {len(matrix)} cenarios; PVGIS: {len(unique)} geometrias unicas (0=360 e horizontal redundantes).')
    print('Fonte local: NASA POWER 2022-2024 por padrao; referencia PVGIS:', args.year)
    print('IMPORTANTE: comparar preferencialmente FT (POA/GHI), nao apenas HSP absoluta.')
    downloaded = 0
    ref = {}
    for t, a in unique:
        path = cache_path(args.year, t, a, args.database)
        if path.exists():
            try:
                record = json.loads(path.read_text('utf-8'))
                if (record['tilt'], record['azimuth'], record['year']) != (t, a, args.year):
                    raise ValueError('Cache nao corresponde a geometria')
                ref[(t, a)] = record
                print(f'CACHE  incl={t:2d}° azi={a:3d}° -> {record["hsp"]:.4f}')
                continue
            except (KeyError, ValueError, json.JSONDecodeError):
                print(f'Cache invalido, refazendo {path.name}')
        if args.max_new_calls is not None and downloaded >= args.max_new_calls:
            continue
        for attempt in range(1, args.retries + 2):
            try:
                record = read_reference(args.year, t, a, args.database, args.timeout)
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf-8')
                ref[(t, a)] = record
                downloaded += 1
                print(f'PVGIS  incl={t:2d}° azi={a:3d}° -> {record["hsp"]:.4f}')
                break
            except Exception as e:
                print(f'FALHA  inc={t} az={a} tentativa {attempt}: {type(e).__name__}: {e}', file=sys.stderr)
                if attempt <= args.retries:
                    time.sleep(min(4.0 * attempt, 12.0))
        time.sleep(args.delay)

    pv_horiz = ref.get((0, 0), {}).get('hsp')
    out = []
    for r in matrix:
        t, a = canonical_geometry(r['tilt'], r['azimuth'])
        p = ref.get((t, a), {}).get('hsp')
        local_ft = r['local_hsp'] / r['local_ghi']
        pv_ft = (p / pv_horiz) if p is not None and pv_horiz is not None and pv_horiz > 0 else None
        diff_ft_pct = ((local_ft / pv_ft - 1) * 100) if pv_ft and pv_ft > 0 else None
        out.append({
            'incl_graus': r['tilt'], 'az_geo_graus': r['azimuth'],
            'az_pvgis_aspect_graus': (r['azimuth'] % 360) - 180,
            'local_hsp_kwh_m2_dia': round(r['local_hsp'], 4),
            'local_ghi_kwh_m2_dia': round(r['local_ghi'], 4),
            'local_ft': round(local_ft, 5),
            'pvgis_hsp_kwh_m2_dia': round(p, 4) if p is not None else '',
            'pvgis_ghi_kwh_m2_dia': round(pv_horiz, 4) if pv_horiz is not None else '',
            'pvgis_ft': round(pv_ft, 5) if pv_ft is not None else '',
            'desvio_hsp_pct': round((r['local_hsp'] / p - 1) * 100, 3) if p else '',
            'desvio_relativo_ft_pct': round(diff_ft_pct, 3) if diff_ft_pct is not None else '',
            'status': 'COMPARADO' if pv_ft is not None else 'PENDENTE',
        })

    with args.output.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    compared = [r for r in out if r['status'] == 'COMPARADO']
    print(f'\nCOMPARADOS: {len(compared)}/40; geometrias PVGIS disponiveis: {len(ref)}/{len(unique)}')
    if compared:
        print('Principais diferencas do FT (fator de transposicao; valores de referencia meteorologica DIFERENTES):')
        for item in sorted(compared, key=lambda x: abs(float(x['desvio_relativo_ft_pct'])), reverse=True)[:12]:
            print(f'  inc={item["incl_graus"]:2d}° azi={item["az_geo_graus"]:3d}° '
                  f'FT_local={item["local_ft"]:.4f} FT_PVGIS={item["pvgis_ft"]:.4f} '
                  f'desvio_rel_FT={item["desvio_relativo_ft_pct"]:+.2f}%')
        mae = sum(abs(float(r['desvio_relativo_ft_pct'])) for r in compared)/len(compared)
        print(f'Erro medio absoluto relativo do fator de transposicao: {mae:.2f}%')
    print(f'\nCSV salvo em: {args.output}')
    if len(compared) < 40:
        print('INCOMPLETO: repita o comando. Resultados validos ja baixados ficam em cache.')
        return 2
    print('COMPLETO: 40 orientacoes comparadas com PVGIS, mas ainda falta validacao com MESMA meteorologia no PVsyst.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
