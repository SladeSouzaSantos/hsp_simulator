"""End-to-end FastAPI F3 schema and temporal-solar integration tests."""
from fastapi.testclient import TestClient

from solar3d.backend.api import app

client = TestClient(app)


def sample_panel(id="P1"):
    return {
        "id": id, "name": id, "kind": "panel",
        "position": {"east": 0, "north": 0, "elevation": 1},
        "width": 1.134, "height": 0.04, "depth": 2.278,
        "tilt": 15, "azimuth": 0,
    }


def request(**changes):
    data = {
        "latitude": -5.92520, "longitude": -35.20500,
        "local_date": "2026-11-07", "timezone": "America/Fortaleza",
        "interval_minutes": 15,
        "sample_rows": 4, "sample_columns": 4,
        "objects": [sample_panel()],
    }
    data.update(changes)
    return data


def test_valid_scene_has_aligned_solar_timestamps():
    response = client.post("/solar3d/shading-day", json=request())
    assert response.status_code == 200, response.text
    shading = response.json()
    solar = client.post("/solar3d/solar-day", json=request()).json()
    assert shading["geometry_only"] is True
    assert shading["sampling"]["cells_per_module"] == 16
    assert len(shading["modules"]) == 1
    assert len(shading["modules"][0]["frames"]) == 96
    assert shading["solar_samples_utc"] == [x["utc_time"] for x in solar["samples"]]
    fractions = [f["blocked_fraction"] for f in shading["modules"][0]["frames"]]
    assert None in fractions
    assert 0.0 in fractions
    assert shading["modules"][0]["mean_blocked_fraction_direct_eligible"] == 0


def test_invalid_scene_returns_422_instead_of_truncation():
    assert client.post("/solar3d/shading-day", json=request(objects=[])).status_code == 422
    assert client.post("/solar3d/shading-day", json=request(
        objects=[sample_panel(), sample_panel()]
    )).status_code == 422
    invalid = sample_panel()
    # NaN is not JSON-compliant. Use a serializable invalid dimension.
    invalid["width"] = -3
    assert client.post("/solar3d/shading-day", json=request(objects=[invalid])).status_code == 422


def test_scene_compute_budget_is_enforced():
    modules = [sample_panel("P" + str(i)) for i in range(48)]
    obstacles = [
        {"id": "W" + str(i), "name": "Wall", "kind": "obstacle",
         "position": {"east": i, "north": 4, "elevation": 1},
         "width": 1, "depth": 0.3, "height": 2,
         "tilt": 0, "azimuth": 0}
        for i in range(48)
    ]
    response = client.post("/solar3d/shading-day", json=request(
        objects=modules + obstacles, sample_rows=12, sample_columns=12, interval_minutes=5,
    ))
    assert response.status_code == 422
