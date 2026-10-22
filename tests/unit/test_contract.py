import pytest
from pydantic import ValidationError
from schemas.schemas import ProjetoSolarRequest
from core.solar_engine_factory import SolarPerezEngineFactory

def test_azimuth_and_tilt_validation():
    with pytest.raises(ValidationError):
        ProjetoSolarRequest(latitude=-5,longitude=-35,azimute_graus=361)
    with pytest.raises(ValidationError):
        ProjetoSolarRequest(latitude=-5,longitude=-35,inclinacao_graus=92)

def test_bifacial_off_by_default():
    d=ProjetoSolarRequest(latitude=-5,longitude=-35)
    assert d.is_bifacial is False

def test_legacy_engine_disabled_without_replacing_contract():
    assert SolarPerezEngineFactory.get_engine_type('perez_legacy')
    with pytest.raises(ValueError): SolarPerezEngineFactory.get_engine_type('whatever')
