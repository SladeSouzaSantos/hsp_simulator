"""F4.2 PVMismatch IV exploratory benchmark; never used as real yield."""
from fastapi.testclient import TestClient
from solar3d.backend.api import app

client = TestClient(app)


def test_generic_iv_model_responds_with_real_traces():
    base = client.post("/solar3d/electrical/iv-experiment", json={
        "modules_in_series": 2,
        "blocked_cell_indices": [],
    })
    assert base.status_code == 200, base.text
    body = base.json()
    assert body["experimental"] is True
    assert body["model_calibrated_to_equipment"] is False
    assert len(body["reference"]["v_v"]) >= 10
    assert body["reference"]["pmp_w"] > 0
    assert abs(body["difference_pct"]) < 0.5


def test_shading_decreases_generic_string_pmp():
    response = client.post("/solar3d/electrical/iv-experiment", json={
        "modules_in_series": 2,
        "blocked_cell_indices": list(range(30)),
        "blocked_irradiance_suns": 0.05,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["reference"]["pmp_w"] > data["shaded"]["pmp_w"] > 0
    assert data["difference_pct"] > 0
    assert all(k in data["shaded"] for k in ("v_v", "i_a", "p_w"))


def test_invalid_cell_layout_is_rejected():
    response = client.post("/solar3d/electrical/iv-experiment", json={
        "blocked_cell_indices": [72],
    })
    assert response.status_code == 422
    response = client.post("/solar3d/electrical/iv-experiment", json={
        "modules_in_series": 2, "shaded_module_index": 3,
    })
    assert response.status_code == 422
