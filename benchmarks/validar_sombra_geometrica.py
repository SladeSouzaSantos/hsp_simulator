"""Auditoria geométrica offline da Fase 1; independe de pvlib e de API externa.

Execute: python -m benchmarks.validar_sombra_geometrica
Grava benchmarks/documents/VALIDACAO_SOMBRA_GEOMETRICA.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

from core.perez_engines.shadow_engine import ShadowEngine

OUTPUT = Path(__file__).resolve().parent / 'documents' / 'VALIDACAO_SOMBRA_GEOMETRICA.csv'


def run():
    # Referências matematicamente deriváveis por interseção de retângulos:
    cases = [
        ('Horizontal, muro largo, 25% de área', 0., 1., 3.5, 10., 0.25),
        ('Horizontal, poste 40 cm, 5% de área', 0., 1., 3.5, .4, 0.05),
        ('Horizontal, poste 1 cm, 0,125% de área', 0., 1., 3.5, .01, .00125),
        ('Vertical, muro largo, 25% de área', 90., 1.5, 3., 10., 0.25),
        ('Vertical, muro largo, 75% de área', 90., 1.5, 4., 10., 0.75),
        ('Horizontal, muro baixo, nenhuma sombra', 0., 1., 1.1, 10., 0.),
    ]
    results = []
    for name, tilt, center, h_ob, w_ob, expected in cases:
        config = {'altura_obstaculo': h_ob, 'distancia_obstaculo': 2.,
                  'largura_obstaculo': w_ob, 'referencia_azimutal_obstaculo': 0.}
        value = float(ShadowEngine.hourly_direct_loss([45.], [0.], config,
            module_height=center, module_length=2., tilt=tilt,
            module_width=2., module_azimuth=0.)[0])
        ok = abs(value-expected) <= 1e-9
        print(f'{"PASSOU" if ok else "FALHOU"} {name}: calculado={value:.6f}; esperado={expected:.6f}')
        results.append({'cenario':name, 'inclinacao_deg':tilt, 'altura_centro_m':center,
            'altura_obstaculo_m':h_ob,'largura_obstaculo_m':w_ob,
            'fracao_sombra_calculada':round(value,8),
            'fracao_sombra_analitica':expected,'passou':ok})
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]))
        writer.writeheader();writer.writerows(results)
    print(f'CSV: {OUTPUT}')
    return 0 if all(r['passou'] for r in results) else 1

if __name__ == '__main__':
    raise SystemExit(run())
