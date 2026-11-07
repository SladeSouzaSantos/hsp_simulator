from fastapi.testclient import TestClient
from solar3d.backend.api import app

client = TestClient(app)


def minimal_module(**changes):
    m = dict(manufacturer="Jetion Solar", modelName="JT690SLk(B)",
             powerWp=690, vOc=49.7, vMp=41.8, iSc=17.31, iMp=16.51,
             tempCoefVoc=-0.24, tempCoefIsc=0.04, tempCoefPmax=-0.24)
    m.update(changes)
    return m


def minimal_inverter(**changes):
    i = dict(manufacturer="AUXSOL", modelName="ASN-6SL-G2", mpptCount=2,
             maxInputVoltage=550, nominalPowerKw=6, minMpptVoltage=40,
             maxMpptVoltage=520)
    i.update(changes)
    return i


def payload(**changes):
    p = dict(format="greencity-os-equipment-v1", source_revision="main",
             modules=[minimal_module()], inverters=[minimal_inverter()])
    p.update(changes)
    return p


def test_missing_vmp_coefficient_is_not_inferred_from_pmax():
    r = client.post("/solar3d/catalog/import/greencity", json=payload())
    assert r.status_code == 200
    result = r.json()
    assert result["totals"] == {"entries": 2, "reviewable": 0, "blocked": 2}
    assert "tempCoefVmp" in " ".join(result["entries"][0]["problems"])
    assert "tempCoefPmax" in " ".join(result["entries"][0]["problems"])
    assert "stringsPerMppt" in " ".join(result["entries"][1]["problems"])


def test_complete_module_is_reviewable_but_not_verified():
    result = client.post("/solar3d/catalog/import/greencity", json=payload(
        modules=[minimal_module(tempCoefVmp=-0.35)], inverters=[],
    )).json()
    item = result["entries"][0]
    assert item["status"] == "review"
    assert item["data"]["verified_datasheet"] is False
    assert item["data"]["vmp_v"] == 41.8
    assert item["data"]["beta_vmp_pct_c"] == -0.35


def test_per_mppt_asymmetric_limits_are_preserved():
    item = client.post("/solar3d/catalog/import/greencity", json=payload(
        modules=[],
        inverters=[minimal_inverter(mpptConfigurationJson={
            "inputCurrentsA": [20, 16],
            "shortCircuitCurrentsA": [28, 22.5],
            "stringsPerMppt": [2, 1],
            "totalDcInputs": 3,
        })],
    )).json()["entries"][0]
    assert item["status"] == "review"
    assert item["data"]["mppts"][0]["max_input_current_a"] == 20
    assert item["data"]["mppts"][1]["max_input_current_a"] == 16
    assert item["data"]["mppts"][1]["max_parallel_strings"] == 1
    assert item["data"]["verified_datasheet"] is False


def test_duplicate_model_and_invalid_export_rejected():
    result = client.post("/solar3d/catalog/import/greencity", json=payload(
        modules=[minimal_module(tempCoefVmp=-0.35), minimal_module(tempCoefVmp=-0.35)],
        inverters=[],
    )).json()
    assert result["entries"][0]["status"] == "review"
    assert result["entries"][1]["status"] == "blocked"
    assert client.post("/solar3d/catalog/import/greencity",
                       json={"format": "unexpected", "modules": []}).status_code == 422
