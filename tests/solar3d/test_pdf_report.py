from fastapi.testclient import TestClient
from solar3d.backend.api import app

client = TestClient(app)


def example():
    return {
        "model": "F5_PVWATTS_MODULE_POTENTIAL_V1",
        "validated_electrical_yield": False,
        "full_year": False,
        "period": {"start_utc": "2023-01-01T00:00Z", "end_utc": "2023-01-01T23:00Z",
                   "hours": 24},
        "weather": {"source": "uploaded"},
        "summary": {"reference_ac_proxy_kwh": 20.5, "shaded_ac_proxy_kwh": 17,
                    "proxy_difference_percent": 17.073,
                    "reference_dc_potential_kwh": 22.4,
                    "shaded_dc_potential_kwh": 18.7},
        "monthly": [{"month_utc": 1, "hours": 24,
                     "dc_reference_potential_w_kwh": 22.4,
                     "dc_shaded_potential_w_kwh": 18.7,
                     "ac_reference_proxy_w_kwh": 20.5,
                     "ac_shaded_proxy_w_kwh": 17}],
    }


def test_pdf_report_is_generated_with_experimental_disclaimer():
    r = client.post("/solar3d/reports/pdf", json=example())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1700


def test_pdf_does_not_accept_claim_of_validated_yield():
    p = example()
    p["validated_electrical_yield"] = True
    assert client.post("/solar3d/reports/pdf", json=p).status_code == 422


def test_pdf_rejects_invalid_amounts():
    p = example()
    p["summary"]["shaded_ac_proxy_kwh"] = -3
    assert client.post("/solar3d/reports/pdf", json=p).status_code == 422
