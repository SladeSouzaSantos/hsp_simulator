"""F5 deterministic no-network hourly POA and DC/AC proxy tests."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from solar3d.backend.api import app

client = TestClient(app)


def request(wall=False, hours=24):
    epoch = datetime(2023, 6, 21, tzinfo=timezone.utc)
    weather = []
    for i in range(hours):
        t = epoch + timedelta(hours=i)
        day = 9 <= (t.hour + 3) % 24 <= 16
        weather.append({
            "timestamp_utc": t.isoformat(),
            "ghi": 750 if day else 0,
            "dni": 850 if day else 0,
            "dhi": 120 if day else 0,
            "temp_air": 28, "wind_speed": 2,
        })
    panel = {"id": "M01", "name": "M01", "kind": "panel",
             "position": {"east": 0, "north": 0, "elevation": 1},
             "width": 1.1, "height": 0.05, "depth": 2.0,
             "azimuth": 0, "tilt": 10}
    objects = [panel]
    if wall:
        objects.append({"id": "box", "name": "Overhead", "kind": "obstacle",
                        "position": {"east": 0, "north": 0, "elevation": 3.0},
                        "width": 20, "height": 0.2, "depth": 20,
                        "azimuth": 0, "tilt": 0})
    return {
        "latitude": -5.9, "longitude": -35.2, "source": "uploaded", "weather": weather,
        "schema_version": 1, "objects": objects, "meshes": [],
        "design": {
            "module_catalog": [{"id": "Demo", "manufacturer": "Example", "model": "Example",
                "pmax_w": 500, "voc_v": 48, "vmp_v": 40,
                "isc_a": 13, "imp_a": 12.5,
                "beta_voc_pct_c": -0.3, "beta_vmp_pct_c": -0.35,
                "alpha_isc_pct_c": 0.04, "gamma_pmax_pct_c": -0.32,
                "verified_datasheet": True}],
            "module_model_ids": {"M01": "Demo"},
            "inverter": {"id": "inv", "manufacturer": "Ex", "model": "Ex",
                "max_dc_voltage_v": 600, "rated_ac_power_w": 5000,
                "verified_datasheet": True,
                "mppts": [{"id": "MPPT1", "min_voltage_v": 20,
                          "max_voltage_v": 550, "max_input_current_a": 20,
                          "max_short_circuit_current_a": 25,
                          "max_parallel_strings": 1}]},
            "strings": [{"id": "S1", "mppt_id": "MPPT1", "module_ids": ["M01"]}],
            "min_cell_temp_c": 0, "max_cell_temp_c": 65,
        },
        "sample_rows": 2, "sample_columns": 2,
    }


def test_short_period_is_labelled_not_annual():
    response = client.post("/solar3d/energy/simulate", json=request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["full_year"] is False
    assert result["validated_electrical_yield"] is False
    assert result["summary"]["reference_dc_potential_kwh"] > 0
    assert result["summary"]["proxy_difference_percent"] == 0
    assert result["weather"]["sample_count"] == 24
    assert len(result["monthly"]) == 1


def test_overhead_shade_reduces_direct_beam_only():
    reference = client.post("/solar3d/energy/simulate", json=request()).json()
    shaded_response = client.post("/solar3d/energy/simulate", json=request(wall=True))
    assert shaded_response.status_code == 200, shaded_response.text
    shaded = shaded_response.json()
    assert shaded["summary"]["shaded_dc_potential_kwh"] < reference["summary"]["reference_dc_potential_kwh"]
    assert shaded["summary"]["reference_dc_potential_kwh"] == reference["summary"]["reference_dc_potential_kwh"]
    assert shaded["summary"]["proxy_difference_percent"] > 0


def test_invalid_or_incomplete_hourly_inputs_rejected():
    invalid = request()
    invalid["weather"][1]["timestamp_utc"] = invalid["weather"][0]["timestamp_utc"]
    response = client.post("/solar3d/energy/simulate", json=invalid)
    assert response.status_code == 422
    invalid = request()
    invalid["design"]["strings"] = []
    assert client.post("/solar3d/energy/simulate", json=invalid).status_code == 422


def test_unverified_equipment_requires_explicit_research_mode():
    invalid = request()
    invalid["design"]["inverter"]["verified_datasheet"] = False
    assert client.post("/solar3d/energy/simulate", json=invalid).status_code == 422
    invalid["allow_unverified_for_research"] = True
    assert client.post("/solar3d/energy/simulate", json=invalid).status_code == 200
