"""F5.2 sampled per-MPPT series/parallel IV loss estimates (offline)."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from solar3d.backend.api import app

client = TestClient(app)


def request(wall=False, two_mppts=False, parallel=False, hours=48):
    start = datetime(2023, 6, 21, tzinfo=timezone.utc)
    weather = []
    for idx in range(hours):
        t = start + timedelta(hours=idx)
        solar = 11 <= t.hour <= 20  # UTC approximates Natal's daylight
        weather.append({
            "timestamp_utc": t.isoformat(),
            "ghi": 850 if solar else 0,
            "dni": 950 if solar else 0,
            "dhi": 150 if solar else 0,
            "temp_air": 27,
            "wind_speed": 1.6,
        })
    panel = lambda id, east: {
        "id": id, "name": id, "kind": "panel",
        "position": {"east": east, "north": 0, "elevation": 1.5},
        "width": 1.1, "height": 0.045, "depth": 2.0,
        "azimuth": 0, "tilt": 10,
    }
    objects = [panel("M01", -3), panel("M02", 3)]
    if wall:
        objects.append({
            "id": "W01", "name": "Test overhang",
            "kind": "obstacle", "position": {"east": -3, "north": 0, "elevation": 3.2},
            "width": 3, "height": 0.2, "depth": 4,
            "azimuth": 0, "tilt": 0,
        })
    strings = [
        {"id": "S1", "mppt_id": "P1", "module_ids": ["M01"]},
        {"id": "S2", "mppt_id": "P2" if two_mppts else "P1", "module_ids": ["M02"]},
    ]
    return {
        "schema_version": 1, "latitude": -5.9, "longitude": -35.2,
        "source": "uploaded", "weather": weather, "objects": objects, "meshes": [],
        "model": "haydavies", "sample_rows": 3, "sample_columns": 2,
        "assume_generic_three_substrings": True,
        "design": {
            "module_catalog": [
                {"id": "Demo", "manufacturer": "EXAMPLE", "model": "EXAMPLE500",
                 "pmax_w": 500, "voc_v": 48, "vmp_v": 40, "isc_a": 13,
                 "imp_a": 12.5, "beta_voc_pct_c": -0.3,
                 "beta_vmp_pct_c": -0.35, "alpha_isc_pct_c": 0.04,
                 "gamma_pmax_pct_c": -0.32, "verified_datasheet": False},
            ],
            "module_model_ids": {"M01": "Demo", "M02": "Demo"},
            "inverter": {
                "id": "INVERTER", "manufacturer": "EXAMPLE",
                "model": "EXAMPLE5K", "max_dc_voltage_v": 600,
                "rated_ac_power_w": 5000,
                "verified_datasheet": False,
                "mppts": [
                    {"id": "P1", "min_voltage_v": 20, "max_voltage_v": 500,
                     "max_input_current_a": 40,
                     "max_short_circuit_current_a": 45,
                     "max_parallel_strings": 2},
                    {"id": "P2", "min_voltage_v": 20, "max_voltage_v": 500,
                     "max_input_current_a": 40,
                     "max_short_circuit_current_a": 45,
                     "max_parallel_strings": 2},
                ],
            },
            "strings": strings,
            "min_cell_temp_c": 0, "max_cell_temp_c": 65,
        },
        "allow_unverified_for_research": True,
    }


def run(data):
    return client.post("/solar3d/losses/monthly", json=data)


def test_requires_explicit_generic_bypass_assumption():
    body = request()
    body["assume_generic_three_substrings"] = False
    response = run(body)
    assert response.status_code == 422


def test_no_shadow_loss_zero_at_each_mppt_and_string():
    result = run(request()).json()
    assert result["model"] == "F5_2_MONTHLY_STRING_MPPT_PIECEWISE_IV_V1"
    assert result["calibrated"] is False
    assert result["period"]["full_year"] is False
    assert result["summary"]["dc_reference_kwh"] > 0
    assert result["summary"]["dc_loss_kwh"] == pytest.approx(0, abs=1e-5)
    assert len(result["monthly"]) == 1
    assert len(result["strings"]) == 2
    assert len(result["mppts"]) == 2
    assert all(x["monthly"][0]["loss_kwh"] == 0 for x in result["strings"])
    assert all(x["monthly"][0]["loss_kwh"] == 0 for x in result["mppts"])


def test_partial_obstruction_changes_mppt_and_string_monthly_loss():
    response = run(request(wall=True, two_mppts=True))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["summary"]["dc_loss_kwh"] > 0
    assert result["summary"]["dc_loss_percent"] > 0
    str1, str2 = result["strings"]
    assert str1["monthly"][0]["loss_kwh"] > 0
    assert str2["monthly"][0]["loss_kwh"] == pytest.approx(0, abs=1e-5)
    mppt1, mppt2 = result["mppts"]
    assert mppt1["monthly"][0]["loss_kwh"] > 0
    assert mppt2["monthly"][0]["loss_kwh"] == pytest.approx(0, abs=1e-5)
    total = sum(item["monthly"][0]["loss_kwh"] for item in result["mppts"])
    assert result["summary"]["dc_loss_kwh"] == pytest.approx(total, abs=5e-4)


def test_parallel_strings_sharing_mppt_have_single_common_voltage():
    data = request(wall=True)
    response = run(data)
    assert response.status_code == 200, response.text
    result = response.json()
    mppt = result["mppts"][0]
    assert mppt["string_ids"] == ["S1", "S2"]
    assert mppt["monthly"][0]["loss_kwh"] > 0
    # Independent string MPP values cannot be mistaken for the parallel
    # MPPT common-voltage result.
    assert mppt["interpretation"].startswith("common_mppt_voltage")


def test_rejects_invalid_electrical_assignment_and_bad_resolution():
    data = request()
    data["design"]["strings"][0]["module_ids"] = ["M01", "M02"]
    assert run(data).status_code == 422
    data = request()
    data["sample_rows"] = 2
    assert run(data).status_code == 422
