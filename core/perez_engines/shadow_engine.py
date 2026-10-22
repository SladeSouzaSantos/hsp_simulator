"""Geometria de obstrução da radiação DIRETA por uma tela vertical finita.

O módulo é um retângulo 3D, centro (0, 0, module_height), comprimento na
rampa e largura transversal. O obstáculo é uma tela vertical, sobre o solo,
centrada no azimute geográfico informado, perpendicular à direção radial.
``distancia_obstaculo`` é medida na horizontal desde a BORDA mais próxima do
módulo até o plano do obstáculo, nunca a partir do centro.

Calcula, sem pixels nem amostragem de área, a interseção exata do retângulo
com três semiplanos lineares que delimitam a sombra de um obstáculo retangular.
NÃO calcula obstrução da abóbada difusa, albedo, fileiras, nem perdas elétricas.
"""
from __future__ import annotations

import math
import numpy as np


def _clip_halfplane(polygon, a: float, b: float, c: float):
    """Recorta polígono convexo pela desigualdade a*s + b*w + c <= 0."""
    if not polygon:
        return []
    result = []
    prev = polygon[-1]
    pv = a * prev[0] + b * prev[1] + c
    for cur in polygon:
        cv = a * cur[0] + b * cur[1] + c
        prev_in, cur_in = pv <= 1.e-10, cv <= 1.e-10
        if prev_in != cur_in:
            # Interpolação em (s,w) da interseção com a linha de fronteira.
            factor = pv / (pv - cv)
            result.append((prev[0] + factor * (cur[0] - prev[0]),
                           prev[1] + factor * (cur[1] - prev[1])))
        if cur_in:
            result.append(cur)
        prev, pv = cur, cv
    return result


def _area(polygon):
    if len(polygon) < 3:
        return 0.0
    return abs(sum(polygon[i][0] * polygon[(i + 1) % len(polygon)][1] -
                   polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
                   for i in range(len(polygon))) / 2)


class ShadowEngine:
    @staticmethod
    def effective_center_height(module_height: float, module_length: float, tilt: float) -> float:
        """Impede a borda inferior do módulo de ficar abaixo do solo.

        Compatibilidade: o campo antigo permite 0,20 m de centro com um módulo
        de 2,278 m e 15°, que penetraria o solo. Somente para o cálculo das
        sombras, eleva-se o plano ao mínimo geometricamente possível. O ajuste
        deve aparecer nos metadados/README; para projeto real informe centro
        suficientemente alto, pois elevar o módulo altera as perdas.
        """
        h = float(module_height)
        if not math.isfinite(h) or h < 0:
            raise ValueError('Altura do centro do módulo deve ser finita e não negativa')
        return max(h, 0.5 * module_length * math.sin(math.radians(tilt)))

    @staticmethod
    def hourly_direct_loss(altitude, solar_azimuth, obstacle, module_height=0.2,
                           module_length=2.278, tilt=15, module_width=1.134,
                           module_azimuth=0.):
        """Retorna fração [0,1] da ÁREA frontal sombreada em cada instante.

        Azimutes em graus geográficos, 0=N, 90=L, 180=S, 270=O. Suporta array
        numpy ou entradas escalares (a saída é ndarray de mesma forma). A face
        do módulo é modelada como um retângulo, não uma fileira ou string.
        """
        alt, az = np.broadcast_arrays(np.asarray(altitude, dtype=float),
                                       np.asarray(solar_azimuth, dtype=float))
        if not np.isfinite(alt).all() or not np.isfinite(az).all():
            raise ValueError('Posição solar inválida (NaN/inf)')
        length, width = float(module_length), float(module_width)
        beta = float(tilt)
        panel_az = float(module_azimuth)
        if not all(math.isfinite(x) for x in (length, width, beta, panel_az)):
            raise ValueError('Geometria do módulo não finita')
        if length <= 0 or width <= 0 or not 0 <= beta <= 90 or not 0 <= panel_az <= 360:
            raise ValueError('Comprimento/largura, inclinação ou azimute do módulo inválidos')

        height = float(obstacle['altura_obstaculo'])
        distance = float(obstacle['distancia_obstaculo'])
        obs_width = float(obstacle.get('largura_obstaculo', 10.0))
        obs_az = float(obstacle['referencia_azimutal_obstaculo'])
        if not all(math.isfinite(x) for x in (height, distance, obs_width, obs_az)):
            raise ValueError('Parâmetros do obstáculo não finitos')
        if height < 0 or distance <= 0 or obs_width <= 0 or not 0 <= obs_az <= 360:
            raise ValueError('Altura, distância, largura ou azimute do obstáculo inválidos')
        output = np.zeros(alt.shape, dtype=float)
        if height == 0:
            return output

        center_h = ShadowEngine.effective_center_height(module_height, length, beta)
        tilt_rad = math.radians(beta)
        cos_t, sin_t = math.cos(tilt_rad), math.sin(tilt_rad)
        delta = math.radians(panel_az - obs_az)
        # A base s aponta para a borda elevada (para trás da direção frontal).
        # w percorre a largura; n aponta do centro para a tela.
        # P_xy(s,w)·n = an*s + bn*w ; P_xy(s,w)·t = at*s + bt*w.
        an = -cos_t * math.cos(delta)
        bn = -math.sin(delta)
        at = -cos_t * math.sin(delta)
        bt = math.cos(delta)
        half_l, half_w = length / 2, width / 2
        # A tela está exatamente 'distance' além da borda mais próxima do painel.
        wall_normal_distance = distance + abs(an) * half_l + abs(bn) * half_w
        panel_polygon = [(-half_l, -half_w), (half_l, -half_w),
                         (half_l, half_w), (-half_l, half_w)]

        flat_out = output.flat
        for i, (solar_alt, sun_azi) in enumerate(zip(alt.flat, az.flat)):
            if solar_alt <= 0 or solar_alt >= 90.0 + 1e-8:
                continue
            # Somente o semiespaço que contém a tela pode obstruir a luz.
            relative = math.radians((sun_azi - obs_az + 180) % 360 - 180)
            cos_relative = math.cos(relative)
            if cos_relative <= 1.e-9:
                continue
            tangent_ratio = math.tan(relative)
            vertical_ratio = math.tan(math.radians(min(solar_alt, 89.999999))) / cos_relative

            # Interseção do raio módulo→Sol com a tela:
            # q_t = (at - kt*an)s + (bt - kt*bn)w + kt*D
            # q_z = (sinβ - kz*an)s - kz*bn*w + h + kz*D
            # Sombra se |q_t| <= Wobs/2 e q_z <= Hobs (q_z>=0 é garantido).
            lateral_a, lateral_b = at - tangent_ratio * an, bt - tangent_ratio * bn
            lateral_c = tangent_ratio * wall_normal_distance
            upper_a, upper_b = sin_t - vertical_ratio * an, -vertical_ratio * bn
            upper_c = center_h + vertical_ratio * wall_normal_distance - height
            lateral_span = abs(lateral_a) * half_l + abs(lateral_b) * half_w
            upper_span = abs(upper_a) * half_l + abs(upper_b) * half_w
            if upper_c - upper_span >= -1.e-10 or \
                    lateral_c - lateral_span >= obs_width / 2 or \
                    lateral_c + lateral_span <= -obs_width / 2:
                continue
            if upper_c + upper_span <= 0 and abs(lateral_c) + lateral_span <= obs_width / 2:
                flat_out[i] = 1.
                continue
            poly = _clip_halfplane(panel_polygon, lateral_a, lateral_b,
                                   lateral_c - obs_width / 2)
            poly = _clip_halfplane(poly, -lateral_a, -lateral_b,
                                   -lateral_c - obs_width / 2)
            poly = _clip_halfplane(poly, upper_a, upper_b, upper_c)
            flat_out[i] = min(1., max(0., _area(poly) / (length * width)))
        return output

    def estimar_perda_sombreamento(self, altitude_sol_deg, azimute_sol_deg,
                altura_instalacao_modulo=0, comprimento_modulo=2.278,
                largura_modulo=1.134, orientacao='Retrato', config_obstaculo=None,
                inclinacao_deg=15, azimute_modulo_deg=0):
        """Assinatura antiga preservada; agora leva em conta as duas dimensões."""
        if not config_obstaculo:
            return 0.
        length = comprimento_modulo if orientacao == 'Retrato' else largura_modulo
        width = largura_modulo if orientacao == 'Retrato' else comprimento_modulo
        return float(self.hourly_direct_loss(
            [altitude_sol_deg], [azimute_sol_deg], config_obstaculo,
            altura_instalacao_modulo, length, inclinacao_deg, width,
            azimute_modulo_deg)[0])
