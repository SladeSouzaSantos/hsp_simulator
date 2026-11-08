"""Unshaded hourly POA contract; test offline against the existing HSP engine."""
from datetime import datetime
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest

from api import app, get_engine
from core.hourly_resource import HourlyResourceRequest, select_calendar_year, resource_hourly
from core.solar_physics import compute_poa
from tests.fixtures.hourly_weather import climate_fixture, hourly_weather


class FakeRepository:
    def __init__(self, weather=None):
        self.data = climate_fixture() if weather is None else dict(hourly=weather,
            metadata={"source": "fixture", "time_standard": "UTC"})

    def get_standardized_data(self, lat, lon, force_provider=None):
        return self.data


class FakeEngine:
    def __init__(self):
        self.repository = FakeRepository()


@pytest.fixture
def client():
    app.dependency_overrides[get_engine] = FakeEngine
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_hourly_resource_matches_original_poa_without_shadow():
    payload = dict(latitude=-5.79448, longitude=-35.21101, ano_utc=2023,
                   inclinacao_graus=15, azimute_graus=35, mes_utc=1)
    result = resource_hourly(HourlyResourceRequest(**payload), FakeRepository())
    assert result["sem_obstaculos"] is True
    assert result["sem_perdas_eletricas"] is True
    assert result["periodo"]["horas_retornadas"] == 31*24
    reference = compute_poa(hourly_weather(), -5.79448, -35.21101, 15, 35,
                            albedo=0.2, model="perez")
    for index, sample in enumerate(result["amostras"]):
        assert sample["poa_total_w_m2"] == pytest.approx(
            reference["frontal_sem_sombra"].iloc[index], abs=0.0002)
        assert sample["poa_direta_w_m2"] >= 0
        assert sample["poa_total_w_m2"] >= 0
    assert len(result["hsp_referencia_mensal_kwh_m2_dia"]) == 12


def test_horizontal_poa_is_exact_ghi(client):
    r = client.post("/recurso-solar/horario", json={
        "latitude": -5.79448, "longitude": -35.21101,
        "inclinacao_graus": 0, "mes_utc": 2,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["amostras"]) == 28*24
    for sample in body["amostras"]:
        assert sample["poa_total_w_m2"] == pytest.approx(sample["ghi_w_m2"], abs=0.0002)


def test_auto_selects_complete_year_and_does_not_invent_partial_annual():
    data = hourly_weather()
    combined = pd.concat([data.iloc[:500], hourly_weather(year=2024)])
    df, year = select_calendar_year(combined, None)
    assert year == 2024
    assert len(df) == 8784
    with pytest.raises(ValueError, match="Não existe ano"):
        select_calendar_year(combined, 2023)


def test_rejects_unavailable_year_and_invalid_inputs(client):
    r = client.post("/recurso-solar/horario", json={
        "latitude": -5.79448, "longitude": -35.21101, "ano_utc": 2019})
    assert r.status_code == 422, r.text
    r = client.post("/recurso-solar/horario", json={
        "latitude": -5.79448, "longitude": -35.21101, "mes_utc": 13})
    assert r.status_code == 422
    r = client.post("/recurso-solar/horario", json={
        "latitude": -5.79448, "longitude": -35.21101,
        "fonte_dados": "INPE/LABREN Atlas 2017"})
    assert r.status_code == 422
    # No geometry or electrical payload accepted in this resource schema.
    assert "config_obstaculo" not in app.openapi()["components"]["schemas"]["HourlyResourceRequest"]["properties"]


def test_legacy_route_keeps_obstacle_contract():
    schema = app.openapi()["components"]["schemas"]
    assert "config_obstaculo" in schema["ProjetoSolarRequest"]["properties"]
    assert "config_obstaculo" in schema["ItemArranjoRequest"]["properties"]
