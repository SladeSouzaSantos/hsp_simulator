"""Contract and geographical sanity checks for the isolated Solar 3D API."""
from fastapi.testclient import TestClient

from solar3d.backend.api import app

client = TestClient(app)


def payload(**changes):
    data = {
        "latitude": -5.92520,
        "longitude": -35.20500,
        "local_date": "2026-11-07",
        "timezone": "America/Fortaleza",
        "interval_minutes": 15,
    }
    data.update(changes)
    return data


def test_solar_day_returns_96_local_samples():
    response = client.post("/solar3d/solar-day", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert len(body["samples"]) == 96
    assert body["visual_only"] is True
    noon = next(s for s in body["samples"] if s["local_time"][11:16] == "12:00")
    assert noon["elevation_deg"] > 0
    assert 0 <= noon["azimuth_deg"] < 360


def test_day_cycle_contains_night_and_day():
    data = client.post("/solar3d/solar-day", json=payload()).json()["samples"]
    assert min(x["elevation_deg"] for x in data) < 0
    assert max(x["elevation_deg"] for x in data) > 50


def test_dst_day_uses_timezone_not_fixed_utc_offset():
    response = client.post("/solar3d/solar-day", json=payload(
        latitude=40.71,
        longitude=-74.00,
        local_date="2026-03-08",
        timezone="America/New_York",
    ))
    assert response.status_code == 200
    assert len(response.json()["samples"]) == 92


def test_input_validation():
    assert client.post("/solar3d/solar-day", json=payload(latitude=91)).status_code == 422
    assert client.post("/solar3d/solar-day", json=payload(timezone="Invalid/Nowhere")).status_code == 422
    assert client.post("/solar3d/solar-day", json=payload(interval_minutes=17)).status_code == 422


def test_health_independent():
    assert client.get("/health").json()["service"] == "solar3d-geometry"
