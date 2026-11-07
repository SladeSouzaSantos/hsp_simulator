"""F4 deterministic topology, electrical nameplate and safety checks."""
from fastapi.testclient import TestClient

from solar3d.backend.api import app

client = TestClient(app)


def panel_spec():
    return dict(id="DEMO-550", manufacturer="EXEMPLO", model="550W (ilustrativo)",
                pmax_w=550, voc_v=49, vmp_v=41, isc_a=14.2, imp_a=13.42,
                beta_voc_pct_c=-0.28, beta_vmp_pct_c=-0.35,
                alpha_isc_pct_c=0.04, verified_datasheet=False)


def mppt(id):
    return dict(id=id, min_voltage_v=100, max_voltage_v=550,
                max_input_current_a=20, max_short_circuit_current_a=25,
                max_parallel_strings=2)


def request():
    return {"panel_ids": ["M01", "M02", "M03", "M04", "M05", "M06"],
            "design": {
                "module_catalog": [panel_spec()],
                "module_model_ids": {f"M0{i}": "DEMO-550" for i in range(1, 7)},
                "inverter": {"id": "DEMO-INV", "manufacturer": "EXEMPLO",
                             "model": "5kW (ilustrativo)", "max_dc_voltage_v": 600,
                             "rated_ac_power_w": 5000,
                             "mppts": [mppt("MPPT1"), mppt("MPPT2")],
                             "verified_datasheet": False},
                "strings": [
                    {"id": "S1", "mppt_id": "MPPT1", "module_ids": ["M01", "M02", "M03"]},
                    {"id": "S2", "mppt_id": "MPPT2", "module_ids": ["M04", "M05", "M06"]}],
                "min_cell_temp_c": 0, "max_cell_temp_c": 65,
            }}


def validate(payload):
    return client.post("/solar3d/electrical/validate", json=payload)


def test_demo_topology_is_only_preliminary_not_certified():
    response = validate(request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "review_required"
    assert result["ready_for_energy_simulation"] is False
    assert result["summary"]["connected_panel_count"] == 6
    assert result["summary"]["nameplate_connected_dc_w"] == 3300
    assert result["strings"][0]["voc_cold_v"] > 3 * 49
    assert result["strings"][0]["vmp_hot_v"] < 3 * 41
    assert {i["code"] for i in result["issues"]} >= {"MODULE_UNVERIFIED", "INVERTER_UNVERIFIED"}


def test_duplicated_panel_between_strings_is_rejected():
    data = request()
    data["design"]["strings"][1]["module_ids"][0] = "M01"
    result = validate(data).json()
    assert result["status"] == "invalid"
    assert "MULTIPLE_STRING_ASSIGNMENT" in {i["code"] for i in result["issues"]}


def test_missing_module_models_and_empty_strings():
    data = request()
    del data["design"]["module_model_ids"]["M02"]
    data["design"]["strings"][0]["module_ids"] = []
    codes = {i["code"] for i in validate(data).json()["issues"]}
    assert {"EMPTY_STRING", "MODEL_UNASSIGNED", "UNCONNECTED_PANEL"} <= codes


def test_low_mppt_voltage_at_hot_cell_temp_fails():
    data = request()
    data["design"]["inverter"]["mppts"][0]["min_voltage_v"] = 145
    assert "MPPT_MIN_VMP" in {i["code"] for i in validate(data).json()["issues"]}


def test_cold_voltage_absolute_inverter_limit_fails():
    data = request()
    data["design"]["inverter"]["max_dc_voltage_v"] = 150
    data["design"]["inverter"]["mppts"][0]["max_voltage_v"] = 140
    data["design"]["inverter"]["mppts"][1]["max_voltage_v"] = 140
    codes = {i["code"] for i in validate(data).json()["issues"]}
    assert "INVERTER_MAX_VOC" in codes


def test_parallel_current_limits_and_string_count():
    data = request()
    data["design"]["strings"][1]["mppt_id"] = "MPPT1"
    codes = {i["code"] for i in validate(data).json()["issues"]}
    assert "MPPT_MAX_INPUT_CURRENT" in codes
    assert "MPPT_MAX_SHORT_CURRENT" in codes
    data["design"]["inverter"]["mppts"][0]["max_parallel_strings"] = 1
    assert "MPPT_MAX_STRINGS" in {i["code"] for i in validate(data).json()["issues"]}


def test_mixed_module_specification_in_series_not_accepted():
    data = request()
    other = {**panel_spec(), "id": "OTHER", "model": "Other"}
    data["design"]["module_catalog"].append(other)
    data["design"]["module_model_ids"]["M02"] = "OTHER"
    assert "MIXED_MODULES_IN_SERIES" in {i["code"] for i in validate(data).json()["issues"]}


def test_identical_module_can_not_be_repeated_within_string():
    data = request()
    data["design"]["strings"][0]["module_ids"] = ["M01", "M02", "M01"]
    assert "DUPLICATE_IN_STRING" in {i["code"] for i in validate(data).json()["issues"]}


def test_data_contract_rejects_nonsensical_equipment_values():
    data = request()
    data["design"]["module_catalog"][0]["vmp_v"] = 60
    assert validate(data).status_code == 422
    data = request()
    data["design"]["inverter"]["mppts"][0]["max_parallel_strings"] = 0
    assert validate(data).status_code == 422


def test_unknown_mppt_and_orphan_mappings_reported():
    data = request()
    data["design"]["strings"][0]["mppt_id"] = "MPPT_DOES_NOT_EXIST"
    data["design"]["module_model_ids"]["DELETED"] = "DEMO-550"
    codes = {i["code"] for i in validate(data).json()["issues"]}
    assert {"UNKNOWN_MPPT", "STALE_MODEL_ASSIGNMENT"} <= codes
