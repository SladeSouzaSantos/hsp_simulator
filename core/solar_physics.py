"""Hourly plane-of-array transposition. Inputs in W/m²; hourly UTC samples.

No monthly daily totals are ever passed as instantaneous irradiance.
"""
import numpy as np
import pandas as pd


def validate_weather(df):
    if not isinstance(df, pd.DataFrame) or not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError('Série horária deve ser um DataFrame indexado por timestamp')
    if df.index.tz is None or df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError('Horários devem possuir fuso, ser únicos e crescentes')
    if len(df) < 8760 or not np.allclose(df.index.to_series().diff().dropna().dt.total_seconds().to_numpy(), 3600):
        raise ValueError('Série precisa ter um ano completo com intervalos contínuos de 1h')
    for key in ('ghi','dhi','dni'):
        if key not in df:
            raise ValueError(f'Campo obrigatório ausente: {key}')
        v = pd.to_numeric(df[key], errors='coerce').to_numpy()
        if not np.isfinite(v).all() or (v < -0.01).any() or (v > 1500).any():
            raise ValueError(f'{key} inválido (valores ausentes ou fora de W/m²)')
    return df.copy()


def compute_poa(weather, latitude, longitude, tilt, azimuth, albedo=0.2,
                model='perez', bifaciality=None, obstacle=None,
                module_height=0.2, module_length=2.278, module_width=1.134):
    import pvlib
    df = validate_weather(weather)
    if model not in ('perez', 'haydavies', 'isotropic'):
        raise ValueError('Modelo inválido')
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and 0 <= tilt <= 90 and 0 <= azimuth <= 360 and 0 <= albedo <= 1):
        raise ValueError('Latitude, longitude, inclinação, azimute ou albedo inválidos')
    # NASA POWER timestamps mark interval starts. Position is computed at mid-hour.
    times = df.index + pd.Timedelta(minutes=30)
    pos = pvlib.location.Location(latitude, longitude, tz='UTC').get_solarposition(times)
    zen = pos['apparent_zenith'].to_numpy()
    solar_az = pos['azimuth'].to_numpy()
    ghi, dhi, dni = [df[k].to_numpy(dtype=float) for k in ('ghi','dhi','dni')]
    extra = np.asarray(pvlib.irradiance.get_extra_radiation(times))
    airmass = np.asarray(pvlib.atmosphere.get_relative_airmass(zen))

    def get(t, az):
        d = pvlib.irradiance.get_total_irradiance(
            t, az, zen, solar_az, dni, ghi, dhi, dni_extra=extra,
            airmass=airmass, albedo=albedo, model=model)
        return {k: np.clip(np.nan_to_num(np.asarray(d[k], dtype=float), nan=0., posinf=0.), 0, None)
                for k in ('poa_global','poa_direct','poa_sky_diffuse','poa_ground_diffuse')}

    front = get(tilt, azimuth)
    # Geometric identity: on a horizontal surface POA must be measured GHI,
    # even if satellite/modelled DNI+DHI differ from GHI at some timestamps.
    if tilt == 0:
        front['poa_global'] = ghi.copy()
        front['poa_direct'] = np.clip(ghi - dhi, 0, None)
        front['poa_sky_diffuse'] = np.minimum(dhi, ghi)
        front['poa_ground_diffuse'] = np.zeros_like(ghi)
    shadow = np.zeros(len(df))
    if obstacle:
        from .perez_engines.shadow_engine import ShadowEngine
        shadow = ShadowEngine.hourly_direct_loss(
            90 - zen, solar_az, obstacle, module_height, module_length, tilt,
            module_width, azimuth)
    # Preserva o POA de referência do pvlib e subtrai só a fração obstruída
    # do feixe direto. Difusa e albedo permanecem sem correção de vista do céu.
    front_shaded = np.clip(front['poa_global'] - front['poa_direct'] * shadow,
                           0, front['poa_global'])
    rear = np.zeros(len(df))
    if bifaciality is not None:
        if not 0 <= bifaciality <= 1:
            raise ValueError('Bifacialidade fora de [0, 1]')
        # Exposed isolated rear plane, NOT a model of row-shading or true module yield.
        rear = bifaciality * get(180 - tilt, (azimuth + 180) % 360)['poa_global']
    result = pd.DataFrame(index=df.index)
    result['frontal'] = front_shaded
    result['frontal_sem_sombra'] = front['poa_global']
    result['traseira_equivalente'] = rear
    result['equivalente'] = front_shaded + rear
    result['equivalente_sem_sombra'] = front['poa_global'] + rear
    result['horizontal'] = ghi
    return result


def summarize_poa(poa):
    keys = ['frontal', 'frontal_sem_sombra', 'traseira_equivalente', 'equivalente', 'equivalente_sem_sombra', 'horizontal']
    # Monthly profiles computed as daily sums, THEN calendar-month average.
    daily = poa[keys].resample('D').sum() / 1000.0
    counts = poa['equivalente'].resample('D').count()
    daily = daily[counts == 24]
    monthly = daily.groupby(daily.index.month).mean().reindex(range(1,13))
    if daily.empty or monthly.isnull().values.any():
        raise ValueError('Série não contém observações completas dos 12 meses')
    values = lambda k: [round(float(v), 3) for v in monthly[k]]
    mean = lambda k: round(float(daily[k].mean()), 3)
    loss = max(0., (poa['frontal_sem_sombra'] - poa['frontal']).sum())
    baseline = poa['frontal_sem_sombra'].sum()
    monthly_baseline = monthly['frontal_sem_sombra']
    monthly_loss_pct = [round(100. * max(0., float(base - received)) / float(base), 2)
                        if float(base) > 0 else 0.
                        for base, received in zip(monthly_baseline, monthly['frontal'])]
    return {
        'media': mean('equivalente'), 'mensal': values('equivalente'),
        'media_sem_sombra': mean('equivalente_sem_sombra'),
        'mensal_sem_sombra': values('equivalente_sem_sombra'),
        'hsp_frontal_media': mean('frontal'), 'hsp_frontal_mensal': values('frontal'),
        'hsp_frontal_mensal_sem_sombra': values('frontal_sem_sombra'),
        'perda_sombreamento_mensal_pct': monthly_loss_pct,
        'hsp_traseira_equivalente_media': mean('traseira_equivalente'),
        'hsp_traseira_equivalente_mensal': values('traseira_equivalente'),
        'hsp_horizontal_media': mean('horizontal'),
        'perda_sombreamento_estimada': f'{100 * loss / baseline if baseline > 0 else 0:.1f}%'
    }
