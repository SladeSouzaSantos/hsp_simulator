"""Regression tests for validators moved into the benchmarks Python package.

These checks do not require pvlib or external HTTP requests.
"""
from pathlib import Path

from benchmarks import comparar_hsp_pvgis as external
from benchmarks import verificar_matriz_hsp as matrix


def test_both_validators_use_same_repository_root():
    root = Path(__file__).resolve().parents[2]
    assert matrix.ROOT == root
    assert external.ROOT == root
    assert matrix.OUTPUT == external.CSV_IN
    assert external.CSV_OUT.parent == root / 'benchmarks' / 'documents'


def test_redundant_geometries_do_not_trigger_extra_pvgis_requests():
    assert external.canonical_geometry(0, 315) == (0, 0)
    assert external.canonical_geometry(15, 0) == external.canonical_geometry(15, 360)
    geoms = {external.canonical_geometry(t, a)
             for t in matrix.TILTS for a in matrix.AZIMUTHS}
    assert len(geoms) == 29


def test_expected_matrix_input_format():
    # The shipped reference CSV uses the documented schema. No network call.
    rows = external.read_matrix(external.CSV_IN)
    assert len(rows) == 40
    assert {r['tilt'] for r in rows} == {0, 15, 20, 45, 90}
    assert {r['azimuth'] for r in rows} == {0, 45, 90, 135, 180, 225, 270, 360}


def test_old_root_scripts_and_split_markdown_are_not_required():
    root = Path(__file__).resolve().parents[2]
    assert not (root / 'verificar_matriz_hsp.py').exists()
    assert not (root / 'comparar_hsp_pvgis.py').exists()
    assert not (root / 'AUDITORIA_E_LIMITACOES.md').exists()
    assert not (root / 'GUIA_VALIDACAO_HSP.md').exists()
