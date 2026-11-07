"""F5.2 experimental electrical monthly shading loss by series string and MPPT.

This is a *nameplate-anchored piecewise I-V approximation*, not a calibrated
single-diode circuit. A generic 3-substring bypass topology is ASSUMED only
with explicit opt-in. No claim of PVsyst parity or bankable production.
Unlike F5 potential sums, modules in series share a current and parallel
strings at an MPPT share a voltage. Monthly losses compare identical
weather/equipment with vs without *external* 3D shadows.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from pydantic import Field, model_validator
import pvlib

from solar3d.backend.energy import EnergyRequest, _load_weather
from solar3d.backend.shading import direction_towards_sun, fraction_blocked

N_CURRENT = 84
N_VOLTAGE = 112
BYPASS_DROP_V = 0.55


class MonthlyLossRequest(EnergyRequest):
    sample_rows: Literal[3, 6] = 6
    sample_columns: Literal[2, 4] = 4
    assume_generic_three_substrings: bool = False

    @model_validator(mode="after")
    def explicit_topology(self):
        if not self.assume_generic_three_substrings:
            raise ValueError(
                "Modelo elétrico preliminar exige aceite explícito: "
                "3 substrings genéricas por módulo, sem calibração de células"
            )
        # Bounds above the inherited 12-panel budget limit the complexity.
        return self


def _poa(req: MonthlyLossRequest, weather: pd.DataFrame, panels: list) -> dict:
    times = weather.index + pd.Timedelta(minutes=30)
    sun = pvlib.solarposition.get_solarposition(times, req.latitude, req.longitude)
    zen = np.asarray(sun["apparent_zenith"], dtype=float)
    az = np.asarray(sun["azimuth"], dtype=float)
    elev = np.asarray(sun["apparent_elevation"], dtype=float)
    extra = np.asarray(pvlib.irradiance.get_extra_radiation(times), dtype=float)
    air = np.asarray(pvlib.atmosphere.get_relative_airmass(zen), dtype=float)
    cache: dict[tuple[float, float], tuple[np.ndarray, np.ndarray]] = {}
    output = {}
    for panel in panels:
        k = (panel.tilt, panel.azimuth)
        if k not in cache:
            result = pvlib.irradiance.get_total_irradiance(
                surface_tilt=panel.tilt, surface_azimuth=panel.azimuth,
                solar_zenith=zen, solar_azimuth=az,
                dni=weather["dni"].to_numpy(dtype=float),
                ghi=weather["ghi"].to_numpy(dtype=float),
                dhi=weather["dhi"].to_numpy(dtype=float), dni_extra=extra,
                airmass=air, albedo=req.albedo, model=req.model,
            )
            cache[k] = (
                np.clip(np.nan_to_num(np.asarray(result["poa_global"], dtype=float)), 0, None),
                np.clip(np.nan_to_num(np.asarray(result["poa_direct"], dtype=float)), 0, None),
            )
        poa_total, poa_direct = cache[k]
        # For each generic vertical strip, fraction from F3 is evaluated
        # on the exact same module mask, not inferred from whole-module loss.
        # This grouping is *not* a physical cell-wiring map.
        shade = np.zeros((len(weather), 3), dtype=float)
        for index, (el, a) in enumerate(zip(elev, az)):
            if el <= 0 or poa_direct[index] <= 0 or not np.isfinite(el):
                continue
            _, mask = fraction_blocked(
                panel, req.objects,
                direction_towards_sun(float(a), float(el)),
                columns=req.sample_columns, rows=req.sample_rows,
                meshes=req.meshes,
            )
            if mask is None:
                continue
            cells = np.asarray(mask, dtype=float).reshape(req.sample_rows, req.sample_columns)
            # Each section corresponds to a third of the face along depth.
            shade[index] = cells.reshape(3, req.sample_rows // 3, req.sample_columns).mean(axis=(1, 2))
        diffuse_and_ground = np.clip(poa_total - poa_direct, 0, None)
        shaded_poa = np.maximum(0, diffuse_and_ground[:, None] +
                                poa_direct[:, None] * (1 - shade))
        unshaded_poa = np.repeat(poa_total[:, None], 3, axis=1)
        output[panel.id] = (unshaded_poa, shaded_poa, shade)
    return output


def _module_substring_voltages(
    spec, poa: np.ndarray, temp_air: np.ndarray, wind: np.ndarray,
    current: np.ndarray,
) -> np.ndarray:
    """Convert nameplate Voc/Vmp/Isc/Imp into piecewise V(I) for 3 substrings.

    POA: (hours,3); current: (hours,points). Each substring is an assumed
    identical 1/3-series portion, clamped to -0.55V in reverse-bypass state.
    The steepness near MPP is analytically anchored to STC Vmp/Imp but does
    not reproduce manufacturer's dark IV or the diode reverse characteristics.
    """
    n = poa.shape[0]
    cell_temp = pvlib.temperature.faiman(
        poa, temp_air[:, None], wind[:, None])
    delta = cell_temp - 25.
    scale = np.maximum(poa / 1000., 0.)
    isc = spec.isc_a * scale * (1 + spec.alpha_isc_pct_c / 100 * delta)
    imp = spec.imp_a * scale * (1 + spec.alpha_isc_pct_c / 100 * delta)
    # Qualitative log-irradiance voltage sensitivity, NOT calibrated coefficient.
    # At complete darkness, all forward voltage collapses to zero.
    log_suns = np.log(np.clip(scale, 1e-4, None))
    voc = np.maximum(0, (spec.voc_v *
        (1 + spec.beta_voc_pct_c / 100 * delta) +
        0.035 * spec.voc_v * log_suns) / 3)
    vmp = np.maximum(0, (spec.vmp_v *
        (1 + spec.beta_vmp_pct_c / 100 * delta) +
        0.035 * spec.vmp_v * log_suns) / 3)
    vmp = np.minimum(vmp, voc * 0.98)
    voc = np.where(scale > 1e-5, voc, 0)
    vmp = np.where(scale > 1e-5, vmp, 0)

    # Strips/hours are vectorized; each substring's voltage adds in series.
    i = current[:, :, None]
    iscb = np.maximum(isc[:, None, :], 1e-8)
    impb = np.maximum(imp[:, None, :], 1e-8)
    vocb = voc[:, None, :]
    vmpb = vmp[:, None, :]
    knee_power = np.maximum(1., vmpb / np.maximum(vocb - vmpb, 1e-6))
    forward = np.where(
        i <= impb,
        vocb - (vocb - vmpb) * np.power(np.clip(i / impb, 0, 1), knee_power),
        vmpb * (iscb - i) / np.maximum(iscb - impb, 1e-8),
    )
    voltage = np.where(i > iscb, -BYPASS_DROP_V, forward)
    voltage = np.where(scale[:, None, :] <= 1e-5,
                       np.where(i > 0, -BYPASS_DROP_V, 0.), voltage)
    return voltage.sum(axis=2)


def _string_curves(req, string, panel_specs, poa, weather, variant):
    n = len(weather)
    irradiation = [poa[mid][variant] for mid in string.module_ids]
    max_suns = np.max(np.stack(irradiation, axis=0), axis=(0, 2))
    max_isc = max(panel_specs[mid].isc_a for mid in string.module_ids)
    t = np.linspace(0, 1.02, N_CURRENT)
    current = (max_isc * np.maximum(max_suns / 1000, 1e-8))[:, None] * t[None, :]
    # Do not assign all substrings identical irradiance under partial shadow.
    voltage = np.zeros((n, N_CURRENT), dtype=float)
    air = weather["temp_air"].to_numpy(dtype=float)
    wind = weather["wind_speed"].to_numpy(dtype=float)
    for mid in string.module_ids:
        voltage += _module_substring_voltages(panel_specs[mid], poa[mid][variant], air, wind, current)
    return current, voltage


def _curve_mpp(current: np.ndarray, voltage: np.ndarray):
    power = np.maximum(0, current * voltage)
    idx = np.argmax(power, axis=1)
    return power[np.arange(len(power)), idx]


def _tracker_power(curves, tracker) -> np.ndarray:
    """Maximum of P(V)=V sum_string I_string(V) at a common MPPT voltage.

    Both parallel strings see the same operating voltage. The MPPT current
    is capped by its input limit (idealized clipping, not device dynamics).
    """
    n = len(curves[0][0])
    voltages = np.linspace(tracker.min_voltage_v, tracker.max_voltage_v, N_VOLTAGE)
    power = np.zeros(n, dtype=float)
    for time_index in range(n):
        currents_total = np.zeros(N_VOLTAGE, dtype=float)
        for current, voltage in curves:
            # Monotone decreasing V(I); reverse for interpolation.
            iv = np.maximum.accumulate(voltage[time_index, ::-1])
            ii = current[time_index, ::-1]
            # Remove repeated voltage steps from bypass plateaus; np.interp
            # requires strictly increasing abscissas to be unambiguous.
            unique_v, unique_indices = np.unique(iv, return_index=True)
            unique_i = ii[unique_indices]
            # Prevent false power beyond the open circuit voltage.
            currents_total += np.maximum(
                0, np.interp(voltages, unique_v, unique_i,
                             left=unique_i[0], right=0))
        power[time_index] = np.max(
            voltages * np.minimum(currents_total, tracker.max_input_current_a))
    return power


def _monthly(values: np.ndarray, index: pd.DatetimeIndex):
    rows = []
    for month in sorted(set(index.month)):
        mask = index.month == month
        ref = float(values[0][mask].sum()) / 1000.
        shade = float(values[1][mask].sum()) / 1000.
        delta = ref - shade
        rows.append({
            "month_utc": int(month), "hours": int(mask.sum()),
            "reference_kwh": round(ref, 5),
            "shaded_kwh": round(shade, 5),
            "loss_kwh": round(delta, 5),
            "loss_percent": round(100 * delta / ref, 4) if ref > 0 else None,
        })
    return rows


def monthly_losses(req: MonthlyLossRequest) -> dict:
    weather, metadata = _load_weather(req)
    panels = [obj for obj in req.objects if obj.kind == "panel"]
    catalog = {mod.id: mod for mod in req.design.module_catalog}
    specs = {obj.id: catalog[req.design.module_model_ids[obj.id]] for obj in panels}
    # Reuse exactly the same geometry and weather in both scenarios.
    radiance = _poa(req, weather, panels)
    strings = {}
    variant_curves = {}
    for string in req.design.strings:
        reference = _string_curves(req, string, specs, radiance, weather, 0)
        shaded = _string_curves(req, string, specs, radiance, weather, 1)
        variant_curves[string.id] = (reference, shaded)
        strings[string.id] = {
            "id": string.id, "mppt_id": string.mppt_id,
            "interpretation": "independent_string_mpp_hypothesis",
            "monthly": _monthly(
                (_curve_mpp(*reference), _curve_mpp(*shaded)), weather.index),
        }
    mppts = {}
    trackers = {mppt.id: mppt for mppt in req.design.inverter.mppts}
    total_reference = np.zeros(len(weather), dtype=float)
    total_shaded = np.zeros(len(weather), dtype=float)
    for id, tracker in trackers.items():
        assigned = [string for string in req.design.strings if string.mppt_id == id]
        if assigned:
            reference = _tracker_power([variant_curves[s.id][0] for s in assigned], tracker)
            shaded = _tracker_power([variant_curves[s.id][1] for s in assigned], tracker)
        else:
            reference = np.zeros(len(weather))
            shaded = np.zeros(len(weather))
        total_reference += reference
        total_shaded += shaded
        mppts[id] = {
            "id": id, "string_ids": [s.id for s in assigned],
            "interpretation": "common_mppt_voltage_approximate_global_mpp",
            "monthly": _monthly((reference, shaded), weather.index),
        }
    dc_monthly = _monthly((total_reference, total_shaded), weather.index)
    ref = float(total_reference.sum()) / 1000
    shade = float(total_shaded.sum()) / 1000
    # Real inverter clipping/AC allocation is NOT solved here. No AC by MPPT.
    return {
        "model": "F5_2_MONTHLY_STRING_MPPT_PIECEWISE_IV_V1",
        "calibrated": False, "validated_electrical_yield": False,
        "physical_model": "nameplate_piecewise_iv_generic_three_bypass_substrings",
        "period": {
            "start_utc": weather.index[0].isoformat(),
            "end_utc": weather.index[-1].isoformat(),
            "hours": len(weather),
            "full_year": metadata["full_utc_calendar_year"],
        },
        "weather": metadata,
        "summary": {
            "dc_reference_kwh": round(ref, 5),
            "dc_shaded_kwh": round(shade, 5),
            "dc_loss_kwh": round(ref - shade, 5),
            "dc_loss_percent": round(100 * (ref - shade) / ref, 4) if ref > 0 else None,
        },
        "monthly": dc_monthly,
        "strings": list(strings.values()),
        "mppts": list(mppts.values()),
        "warnings": [
            "Perdas de energia DC estimadas pelo modelo elétrico aproximado NÃO calibrado.",
            "3 substrings iguais, organizadas em faixas transversais ao comprimento: "
            "não representa automaticamente half-cut/TOPCon nem ligação real de diodos.",
            "I-V por pontos Voc/Vmp/Isc/Imp; forma entre pontos e tensão de bypass supostas.",
            "MPPT ideal busca MPP global no intervalo nominal e limita corrente, "
            "sem dinâmica, entrada por string, variação de eficiência ou clipping AC.",
            "Somente obstrução do feixe direto; céu difuso e terreno não obstruídos.",
            "Passo meteorológico horário, amostragem espacial discreta; "
            "perdas percentuais calculadas por razão entre energias no MESMO mês.",
            "Não usar como resultado comercial sem calibrar módulos e verificar em campo/PVsyst.",
        ],
    }
