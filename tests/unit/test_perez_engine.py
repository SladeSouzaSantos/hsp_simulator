"""Perez engine tests with valid hourly GHI, DHI, DNI, never monthly HSP as W/m²."""
import pytest

pytest.importorskip('pvlib')
from core.perez_engines.perez_engine import PerezEngine
from tests.fixtures.hourly_weather import climate_fixture


@pytest.fixture(scope='module')
def hourly_climate():
    return climate_fixture(-7.0, -35.0)


@pytest.fixture
def base_params():
    return {
        'lat': -7.0, 'lon': -35.0, 'is_bifacial': True,
        'albedo': 0.2, 'altura_instalacao': 1.0,
        'comprimento_modulo': 2.278, 'largura_modulo': 1.134,
        'inclinacao_deg': 15, 'azimute_deg': 0,
    }


def test_ganho_bifacial_zero_quando_desativado(base_params, hourly_climate):
    mono = PerezEngine(**{**base_params, 'is_bifacial': False})
    bi = PerezEngine(**base_params)
    monofacial = mono.calcular_hsp_corrigido_inc_azi(hourly_climate)
    bifacial = bi.calcular_hsp_corrigido_inc_azi(hourly_climate)
    assert monofacial['hsp_traseira_equivalente_media'] == 0
    assert bifacial['hsp_traseira_equivalente_media'] > 0
    assert bifacial['hsp_frontal_media'] == monofacial['hsp_frontal_media']
    assert bifacial['media'] > monofacial['media']


def test_perez_com_inclinacao_zero(base_params, hourly_climate):
    # Monofacial horizontal POA must reproduce input GHI exactly (within rounding).
    params = {**base_params, 'inclinacao_deg': 0, 'is_bifacial': False}
    result = PerezEngine(**params).calcular_hsp_corrigido_inc_azi(hourly_climate)
    assert result['media'] == result['hsp_horizontal_media']
    assert result['mensal'] == pytest.approx([
        round(x, 3) for x in hourly_climate['hsp_global']
    ], abs=0.001)


def test_dados_mensais_nao_fingem_ser_serie_horaria(base_params):
    with pytest.raises(ValueError, match='série horária'):
        PerezEngine(**base_params).calcular_hsp_corrigido_inc_azi({
            'hsp_global': [5.0] * 12, 'hsp_diffuse': [1.0] * 12,
        })
