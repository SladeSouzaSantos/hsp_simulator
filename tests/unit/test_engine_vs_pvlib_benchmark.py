"""Regressões para evitar o retorno indevido ao contrato mensal no benchmark."""

from unittest.mock import Mock
import pandas as pd
import pytest

from benchmarks import engine_vs_pvlib as benchmark


def fake_climate():
    times = pd.date_range('2023-01-01', '2024-01-01', freq='h', inclusive='left', tz='UTC')
    weather = pd.DataFrame({'ghi': 250.0, 'dhi': 70.0, 'dni': 300.0}, index=times)
    return {'hourly': weather, 'hsp_global': [6.] * 12,
            'hsp_diffuse': [2.] * 12,
            'metadata': {'source': 'TESTE HORARIO', 'years': '2023'}}


def test_comparativo_usa_hourly_e_busca_uma_vez_por_cidade(monkeypatch, tmp_path):
    climate = fake_climate()
    repo = Mock()
    repo.get_standardized_data.return_value = climate
    seen = []

    def engine(data, lat, lon, tilt, azimuth):
        assert data is climate
        assert data['hourly'].shape == (8760, 3)
        seen.append((tilt, azimuth))
        return 5.25

    monkeypatch.setattr(benchmark, '_run_engine', engine)
    monkeypatch.setattr(benchmark, '_pvlib_reference_hsp',
                        lambda weather, lat, lon, tilt, azimuth: 5.25)
    table = benchmark.run_mass_comparison(cities=['Natal'], repository=repo,
                                          output_dir=tmp_path)
    assert len(table) == 4
    assert seen == [(0, 0), (4, 0), (6, 0), (16, 0)]
    repo.get_standardized_data.assert_called_once_with(
        *benchmark.CITIES['Natal'], force_provider='NASA POWER')
    assert (tmp_path / 'BENCHMARK_ENGINE_VS_PVLIB.csv').is_file()
    assert (table['Delta_Engine_PVLib_Pct'] == 0).all()
    assert set(table['Fonte_Meteorologica']) == {'TESTE HORARIO'}


def test_entrada_mensal_rejeitada_sem_falsificar_horarios(tmp_path):
    repo = Mock()
    repo.get_standardized_data.return_value = {
        'hsp_global': [5.5] * 12, 'hsp_diffuse': [1.5] * 12,
    }
    with pytest.raises(ValueError, match='série horária'):
        benchmark.run_mass_comparison(cities=['Natal'], repository=repo,
                                      output_dir=tmp_path)
    assert not (tmp_path / 'BENCHMARK_ENGINE_VS_PVLIB.csv').exists()


def test_grade_cobre_40_cenarios_e_equivalencia_azimutal(monkeypatch, tmp_path):
    repo = Mock()
    repo.get_standardized_data.return_value = fake_climate()

    def simulator(data, lat, lon, tilt, azimuth):
        return 6. if tilt == 0 else 5. - tilt / 100. + (azimuth % 360) / 1000.

    monkeypatch.setattr(benchmark, '_run_engine', simulator)
    monkeypatch.setattr(benchmark, '_pvlib_reference_hsp',
                        lambda weather, lat, lon, tilt, azimuth: simulator(None, lat, lon, tilt, azimuth))
    table = benchmark.run_orientation_grid(city='Natal', repository=repo,
                                           output_dir=tmp_path)
    assert len(table) == 40
    assert sorted(table['Inclinacao'].unique()) == [0, 15, 20, 45, 90]
    assert sorted(table['Azimute'].unique()) == [0, 45, 90, 135, 180, 225, 270, 360]
    assert (tmp_path / 'BENCHMARK_ORIENTACOES_ENGINE_VS_PVLIB.csv').is_file()
    repo.get_standardized_data.assert_called_once()


def test_pvlib_direto_igual_a_engine_para_mesma_serie_horaria():
    pytest.importorskip('pvlib')
    from tests.fixtures.hourly_weather import climate_fixture
    lat, lon = benchmark.CITIES['Natal']
    climate = climate_fixture(lat, lon)
    for tilt, azimuth in [(0, 90), (15, 0), (45, 270), (90, 180)]:
        engine = benchmark._run_engine(climate, lat, lon, tilt, azimuth)
        direct = benchmark._pvlib_reference_hsp(climate['hourly'], lat, lon, tilt, azimuth)
        assert engine == pytest.approx(direct, abs=0.002)
