"""Geographical regression using synthetic annual clear-sky input at EACH real city.

The SunData fixture is only used to select city/tilt test cases, NOT to provide
horizontal GHI for an inclined plane, which would invalidate the benchmark.
These assertions check finite physical behavior, not agreement with SunData.
"""
import json
from pathlib import Path
import pytest

pytest.importorskip('pvlib')
from core.perez_engines.perez_engine import PerezEngine
from tests.fixtures.hourly_weather import climate_fixture

GEO = {
    'Natal': (-5.79, -35.21),
    'Caico': (-6.45, -37.09),
    'Petrolina': (-9.38, -40.50),
    'Manaus': (-3.11, -60.02),
    'Porto Alegre': (-30.03, -51.23),
    'Sao Jose dos Campos': (-23.17, -45.88),
}
FIXTURE_PATH = Path(__file__).parents[1] / 'fixtures' / 'amostragem_sundata.json'
SUNDATA = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
CASES = [(city, int(tilt)) for city, inclinations in SUNDATA.items() for tilt in inclinations]


@pytest.mark.parametrize('cidade,inclinacao', CASES)
def test_estresse_motor_com_cidades_reais(cidade, inclinacao):
    lat, lon = GEO[cidade]
    climate = climate_fixture(lat, lon)
    result = PerezEngine(
        lat=lat, lon=lon, inclinacao_deg=inclinacao, azimute_deg=0,
        albedo=0.2, is_bifacial=False,
    ).calcular_hsp_corrigido_inc_azi(climate)
    assert len(result['mensal']) == 12
    assert all(0 < month < 15 for month in result['mensal'])
    assert 0 < result['media'] < 15
    assert result['hsp_traseira_equivalente_media'] == 0
    if inclinacao == 0:
        assert result['mensal'] == pytest.approx([
            round(value, 3) for value in climate['hsp_global']
        ], abs=0.001)
