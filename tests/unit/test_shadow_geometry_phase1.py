"""Casos geométricos com área conhecida; independentes de pvlib ou rede."""
import math

import numpy as np
import pandas as pd
import pytest

from core.perez_engines.shadow_engine import ShadowEngine
from core.solar_physics import summarize_poa


def obst(height=3.5, distance=2., width=10., az=0.):
    return {'altura_obstaculo': height, 'distancia_obstaculo': distance,
            'largura_obstaculo': width, 'referencia_azimutal_obstaculo': az}


def shadow(alt=45., solar_az=0., obstacle=None, *, tilt=0., center=1.,
           panel_length=2., panel_width=2., panel_az=0.):
    return float(ShadowEngine.hourly_direct_loss(
        [alt], [solar_az], obstacle or obst(), module_height=center,
        module_length=panel_length, tilt=tilt, module_width=panel_width,
        module_azimuth=panel_az)[0])


def test_horizontal_retangulo_largo_25_porcento():
    # Painel 2m na direção N-S, 2m de largura, h=1m, muro N a 2m da borda.
    # Com elevação solar 45°, o raio atinge o muro em z=1+(3-y).
    # Para H=3,5m, a sombra ocupa y>=0,5m: 0,5/2=25%.
    assert shadow() == pytest.approx(0.25, abs=1.e-9)


def test_largura_fisica_altera_area_nao_apenas_janela_angular():
    assert shadow(obstacle=obst(width=.4)) == pytest.approx(.05, abs=1.e-9)
    assert shadow(obstacle=obst(width=.01)) == pytest.approx(.00125, abs=1.e-9)
    assert shadow(obstacle=obst(width=10.)) > shadow(obstacle=obst(width=.4))


def test_modulo_vertical_tem_intersecao_geometrica_adequada():
    # Vertical voltado Norte, centro a 1,5m, topo em 2,5m, base em 0,5m.
    # Muro N a 2m, sol a 45°, incidência no muro z + 2. Se H=3m,
    # somente a faixa z<=1m é sombreada: (1-0,5)/2=25%.
    assert shadow(obstacle=obst(height=3.), tilt=90., center=1.5) == pytest.approx(.25, abs=1.e-9)


def test_sol_oposto_ou_sem_elevacao_nao_sombreia():
    assert shadow(solar_az=180.) == 0
    assert shadow(alt=0.) == 0
    assert shadow(alt=-10.) == 0
    assert shadow(alt=90.) == 0  # Raio vertical não alcança uma tela externa.
    assert shadow(obstacle=obst(height=0)) == 0


def test_obstaculo_muito_baixo_ou_longe_nao_sombreia():
    assert shadow(obstacle=obst(height=1.1)) == 0
    assert shadow(obstacle=obst(distance=100, height=4.)) == 0


def test_largura_poste_nunca_equivale_a_muro_largo():
    kwargs = dict(tilt=15., center=1., panel_length=2., panel_width=2.)
    a = shadow(obstacle=obst(height=10, width=.01, distance=1.), **kwargs)
    b = shadow(obstacle=obst(height=10, width=20, distance=1.), **kwargs)
    assert 0 < a < .01 and b == pytest.approx(1., abs=1.e-9)


def test_azimutes_0_e_360_iguais_e_simetrias():
    result = ShadowEngine.hourly_direct_loss(
        np.array([15, 30, 45, 75]), [0, 30, 345, 180], obst(),
        module_height=1., module_length=2., module_width=2., tilt=20.)
    other = ShadowEngine.hourly_direct_loss(
        np.array([15, 30, 45, 75]), [360, 390, -15, 180],
        obst(az=360), module_height=1., module_length=2., module_width=2., tilt=20.,
        module_azimuth=360.)
    assert np.allclose(result, other, atol=1e-12)
    assert np.all(np.isfinite(result))
    assert np.all((result >= 0) & (result <= 1))


def test_centro_subsolo_corrigido_explicitamente():
    required = 2.278 * math.sin(math.radians(15)) / 2
    assert ShadowEngine.effective_center_height(.2, 2.278, 15) == pytest.approx(required)
    assert ShadowEngine.effective_center_height(1., 2.278, 15) == 1.


@pytest.mark.parametrize('key,value', [('distancia_obstaculo',0),
                                       ('largura_obstaculo',0), ('altura_obstaculo',-1),
                                       ('referencia_azimutal_obstaculo',361)])
def test_geometria_invalida_rejeitada(key, value):
    with pytest.raises(ValueError):
        shadow(obstacle={**obst(), key: value})


def test_series_em_lote_compativeis_formato_antes():
    positions = np.linspace(0., 90., 9000)
    r = ShadowEngine.hourly_direct_loss(positions, np.zeros(len(positions)), obst(),
                                        module_height=1., module_length=2., tilt=15., module_width=2.)
    assert len(r) == len(positions)
    assert np.isfinite(r).all()
    assert ((r>=0)&(r<=1)).all()


def test_perda_mensal_sombra_sem_mudar_referencia_ou_contrato():
    idx = pd.date_range('2023-01-01','2024-01-01',freq='h',inclusive='left',tz='UTC')
    df = pd.DataFrame(index=idx)
    df['frontal_sem_sombra'] = 300.
    df['frontal'] = 270.
    df['traseira_equivalente'] = 0.
    df['equivalente'] = df['frontal']
    df['equivalente_sem_sombra'] = df['frontal_sem_sombra']
    df['horizontal'] = 300.
    result = summarize_poa(df)
    assert result['perda_sombreamento_estimada'] == '10.0%'
    assert result['perda_sombreamento_mensal_pct'] == [10.]*12
    assert result['hsp_frontal_mensal_sem_sombra'] == [7.2]*12
    assert result['mensal_sem_sombra'] == [7.2]*12
    assert result['mensal'] == [6.48]*12
