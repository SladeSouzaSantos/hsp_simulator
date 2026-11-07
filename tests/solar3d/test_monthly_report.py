"""F5.2 monthly MPPT PDF structural contract and claim safety."""
from fastapi.testclient import TestClient

from solar3d.backend.api import app

client = TestClient(app)


def payload():
    month = {"month_utc": 1, "hours": 24, "reference_kwh": 12.0,
             "shaded_kwh": 10.0, "loss_kwh": 2.0, "loss_percent": 16.6667}
    return {
        "model": "F5_2_MONTHLY_STRING_MPPT_PIECEWISE_IV_V1",
        "calibrated": False, "validated_electrical_yield": False,
        "period": {"start_utc": "2023-01-01T00:00:00Z",
                   "end_utc": "2023-01-01T23:00:00Z",
                   "hours": 24, "full_year": False},
        "weather": {"source": "upload"},
        "summary": {"dc_reference_kwh": 12.0, "dc_shaded_kwh": 10.0,
                    "dc_loss_kwh": 2.0, "dc_loss_percent": 16.6667},
        "monthly": [month],
        "strings": [{"id": "S1", "mppt_id": "MPPT1", "monthly": [month]}],
        "mppts": [{"id": "MPPT1", "string_ids": ["S1"], "monthly": [month]}],
    }


def test_pdf_comprises_monthly_mppt_and_string_rows():
    response = client.post("/solar3d/losses/report/pdf", json=payload())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 2000


def test_pdf_does_not_accept_claims_of_calibrated_yield():
    data = payload()
    data["calibrated"] = True
    assert client.post("/solar3d/losses/report/pdf", json=data).status_code == 422
    data = payload()
    data["validated_electrical_yield"] = True
    assert client.post("/solar3d/losses/report/pdf", json=data).status_code == 422


def test_pdf_rejects_inconsistent_months_and_invalid_numbers():
    data = payload()
    data["mppts"][0]["monthly"][0]["month_utc"] = 2
    assert client.post("/solar3d/losses/report/pdf", json=data).status_code == 422
    data = payload()
    data["summary"]["dc_reference_kwh"] = -1
    assert client.post("/solar3d/losses/report/pdf", json=data).status_code == 422
