"""Deterministic test-only annual hourly weather constructed using pvlib clear-sky.

This fixture does NOT represent measured NASA, INPE or SunData data, and is not
used to claim agreement with PVsyst. All hourly irradiances are in W/m².
"""
from functools import lru_cache
import pandas as pd


@lru_cache(maxsize=16)
def _clear_sky_annual(lat: float, lon: float, year: int) -> pd.DataFrame:
    import pvlib
    timestamps = pd.date_range(
        f'{year}-01-01', f'{year + 1}-01-01', freq='h',
        inclusive='left', tz='UTC',
    )
    # The physics engine evaluates solar position at the center of each 1h bin.
    location = pvlib.location.Location(lat, lon, tz='UTC')
    weather = location.get_clearsky(
        timestamps + pd.Timedelta(minutes=30), model='ineichen'
    )[['ghi', 'dhi', 'dni']]
    weather.index = timestamps
    return weather


def hourly_weather(lat=-5.79448, lon=-35.21101, year=2023) -> pd.DataFrame:
    """Return a copy so tests can freely manipulate a fixture in isolation."""
    return _clear_sky_annual(float(lat), float(lon), int(year)).copy()


def climate_fixture(lat=-5.79448, lon=-35.21101, year=2023) -> dict:
    """Match the production provider contract; monthly HSP derived from hourly data."""
    hourly = hourly_weather(lat, lon, year)
    daily = hourly[['ghi', 'dhi']].resample('D').sum() / 1000
    monthly = daily.groupby(daily.index.month).mean().reindex(range(1, 13))
    return {
        'hourly': hourly,
        'hsp_global': monthly['ghi'].tolist(),
        'hsp_diffuse': monthly['dhi'].tolist(),
        'temp_avg': [25.0] * 12,
        'temp_max': [30.0] * 12,
        'temp_min': [20.0] * 12,
        'metadata': {
            'source': 'fixture-clear-sky',
            'temporal_resolution': 'hourly',
            'time_standard': 'UTC',
            'units': 'W/m²',
            'synthetic': True,
        },
    }
