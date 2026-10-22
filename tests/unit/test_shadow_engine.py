import numpy as np
from core.perez_engines.shadow_engine import ShadowEngine

OBSTACLE={'altura_obstaculo':4.,'distancia_obstaculo':2.,
          'largura_obstaculo':10.,'referencia_azimutal_obstaculo':0.}

def test_obstacle_away_from_sun_no_shadow():
    x=ShadowEngine.hourly_direct_loss(np.array([25.,25.]),np.array([180.,220.]),OBSTACLE)
    assert np.array_equal(x,np.zeros(2))

def test_higher_sun_casts_shorter_shadow():
    v=ShadowEngine.hourly_direct_loss(np.array([10.,60.]), np.array([0.,0.]),OBSTACLE)
    assert 0 <= v[1] <= v[0] <= 1

def test_obstacle_below_module_zero_shadow():
    o={**OBSTACLE,'altura_obstaculo':.1}
    assert ShadowEngine.hourly_direct_loss([20],[0],o,module_height=.2)[0]==0
