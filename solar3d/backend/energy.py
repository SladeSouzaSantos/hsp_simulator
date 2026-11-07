"""F5 exploratory PVWatts POA + module-potential time-series comparison.

This is not an electrical string/mismatch solver. Module DC values are
independent irradiance-based potential; their sums are circuit-level *upper
bound proxies*. The AC proxy is from PVWatts applied to potential, not a
validated MPPT operating point. The results must NOT be sold as a prediction
of actual system energy before PVMismatch/datasheet calibration.
"""
from __future__ import annotations

from datetime import datetime
import calendar
from typing import Literal

from pydantic import BaseModel, Field, model_validator
import numpy as np
import pandas as pd
import pvlib

from solar3d.backend.electrical import (
    ElectricalDesign, ElectricalValidationRequest, check_electrical_design,
)
from solar3d.backend.shading import SceneObject, direction_towards_sun, fraction_blocked
from solar3d.backend.mesh import MeshObstacle


class WeatherHour(BaseModel):
    timestamp_utc: datetime
    ghi: float = Field(ge=0, le=1600, allow_inf_nan=False)
    dni: float = Field(ge=0, le=1600, allow_inf_nan=False)
    dhi: float = Field(ge=0, le=1600, allow_inf_nan=False)
    temp_air: float = Field(ge=-60, le=70, allow_inf_nan=False)
    wind_speed: float = Field(ge=0, le=70, allow_inf_nan=False)

    @model_validator(mode="after")
    def require_tz(self):
        if self.timestamp_utc.tzinfo is None or self.timestamp_utc.utcoffset() is None:
            raise ValueError("timestamp_utc deve conter fuso")
        return self


class EnergyRequest(BaseModel):
    schema_version: Literal[1] = 1
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    source: Literal["uploaded", "nasa-power", "pvgis-tmy"] = "uploaded"
    weather_year: int = Field(default=2023, ge=2001, le=2025)
    weather: list[WeatherHour] | None = Field(default=None, max_length=8784)
    objects: list[SceneObject] = Field(min_length=1, max_length=50)
    meshes: list[MeshObstacle] = Field(default_factory=list, max_length=6)
    design: ElectricalDesign
    sample_rows: Literal[2, 4] = 2
    sample_columns: Literal[2, 4] = 2
    model: Literal["isotropic", "haydavies", "perez"] = "haydavies"
    albedo: float = Field(default=0.2, ge=0, le=1, allow_inf_nan=False)
    allow_unverified_for_research: bool = False

    @model_validator(mode="after")
    def validate_request(self):
        panel_ids = {x.id for x in self.objects if x.kind == "panel"}
        if not panel_ids:
            raise ValueError("Não há painéis na cena")
        if len(panel_ids) > 12:
            raise ValueError("F5 síncrono aceita até 12 painéis; amplie com worker assíncrono")
        if len({x.id for x in self.objects}) != len(self.objects):
            raise ValueError("ID de objeto duplicado")
        if len({m.id for m in self.meshes}) != len(self.meshes):
            raise ValueError("ID de malha duplicado")
        if panel_ids & {m.id for m in self.meshes}:
            raise ValueError("ID de módulo e malha sobreposto")
        if self.source == "uploaded" and not self.weather:
            raise ValueError("Informe série horária UTC para source=uploaded")
        if self.source != "uploaded" and self.weather is not None:
            raise ValueError("Fonte externa não aceita weather enviado simultaneamente")
        if not self.allow_unverified_for_research:
            if not self.design.inverter.verified_datasheet:
                raise ValueError("Confirme datasheet do inversor ou habilite modo experimental")
            by_id = {m.id: m for m in self.design.module_catalog}
            for panel_id in panel_ids:
                name = self.design.module_model_ids.get(panel_id)
                if not name or name not in by_id or not by_id[name].verified_datasheet:
                    raise ValueError(f"Confirme datasheet do módulo {panel_id} ou habilite modo experimental")
        check = check_electrical_design(ElectricalValidationRequest(
            panel_ids=sorted(panel_ids), design=self.design))
        if check["status"] == "invalid":
            raise ValueError("Topologia inválida. Corrija /solar3d/electrical/validate antes de simular")
        if any(i["code"] == "UNCONNECTED_PANEL" for i in check["issues"]):
            raise ValueError("Todos os módulos devem estar ligados para simulação")
        catalog = {m.id: m for m in self.design.module_catalog}
        for panel_id in panel_ids:
            module = catalog.get(self.design.module_model_ids.get(panel_id, ""))
            if module is None or module.gamma_pmax_pct_c is None:
                raise ValueError("gamma_pmax_pct_c obrigatório para cada modelo na F5")
        return self


def _load_weather(req: EnergyRequest) -> tuple[pd.DataFrame, dict]:
    if req.source == "uploaded":
        weather = req.weather or []
        times = pd.DatetimeIndex([pd.Timestamp(x.timestamp_utc).tz_convert("UTC") for x in weather])
        frame = pd.DataFrame([dict(ghi=x.ghi, dni=x.dni, dhi=x.dhi,
                                   temp_air=x.temp_air, wind_speed=x.wind_speed)
                              for x in weather], index=times)
        metadata = {"source": "uploaded", "years": sorted(set(times.year.tolist()))}
    elif req.source == "nasa-power":
        from services.providers.nasa_power_provider import NasaPowerProvider
        frame = NasaPowerProvider().fetch_solar_data(req.latitude, req.longitude)
        frame = frame[frame.index.year == req.weather_year].copy()
        metadata = {"source": "NASA POWER", "years": [req.weather_year]}
    else:
        from services.providers.pvgis_provider import PvgisProvider
        frame = PvgisProvider().fetch_solar_data(req.latitude, req.longitude)
        metadata = {"source": "PVGIS TMY", "years": sorted(set(frame.index.year.tolist()))}
    if len(frame) < 24 or len(frame) > 8784:
        raise ValueError("Série precisa ter de 24h a um ano")
    if frame.index.tz is None:
        raise ValueError("Série deve conter timezone")
    frame.index = frame.index.tz_convert("UTC")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Horários precisam ser únicos e crescentes")
    if not np.all(np.diff(frame.index.view("int64")) == 3_600_000_000_000):
        raise ValueError("O passo precisa ser contínuo de exatamente uma hora")
    for key in ("ghi", "dni", "dhi", "temp_air", "wind_speed"):
        if key not in frame:
            raise ValueError("Dados meteorológicos não incluem " + key)
        values = pd.to_numeric(frame[key], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"Dados ausentes/não finitos em {key}")
        if key in {"ghi", "dni", "dhi"} and (values < 0).any():
            raise ValueError("Irradiância negativa")
    # Do not label a short series annual or extrapolate it to 365 days.
    first, last = frame.index[0], frame.index[-1]
    full_year = (
        len(frame) in (8760, 8784) and first.month == 1 and first.day == 1 and
        first.hour == 0 and last.month == 12 and last.day == 31 and
        last.hour == 23 and first.year == last.year and
        len(frame) == (8784 if calendar.isleap(first.year) else 8760)
    )
    metadata.update({"sample_count": len(frame), "full_utc_calendar_year": bool(full_year)})
    return frame, metadata


def _month_bins(df: pd.DataFrame, keys: tuple[str, ...]) -> list[dict]:
    result = []
    for month, subset in df.groupby(df.index.month):
        item = {"month_utc": int(month), "hours": len(subset)}
        item.update({key + "_kwh": round(float(subset[key].sum()) / 1000, 5) for key in keys})
        result.append(item)
    return result


def simulate_energy(req: EnergyRequest) -> dict:
    frame, metadata = _load_weather(req)
    panels = [obj for obj in req.objects if obj.kind == "panel"]
    resource = {m.id: m for m in req.design.module_catalog}
    meta_by_panel = {id: resource[req.design.module_model_ids[id]] for id in
                     [p.id for p in panels]}
    n = len(frame)
    # Complexity budget: explicit serial ray tests, NO background execution.
    intersections = n * len(panels) * req.sample_rows * req.sample_columns * (
        max(1, len(req.objects) - 1) + sum(len(mesh.triangles) for mesh in req.meshes)
    )
    if intersections > 8_000_000:
        raise ValueError("Limite do F5 síncrono atingido: reduza amostragem, painéis ou malhas")
    times = frame.index + pd.Timedelta(minutes=30)
    solar = pvlib.solarposition.get_solarposition(times, req.latitude, req.longitude)
    apparent_zenith = np.asarray(solar["apparent_zenith"], dtype=float)
    solar_az = np.asarray(solar["azimuth"], dtype=float)
    solar_elev = np.asarray(solar["apparent_elevation"], dtype=float)
    extra = np.asarray(pvlib.irradiance.get_extra_radiation(times), dtype=float)
    airmass = np.asarray(pvlib.atmosphere.get_relative_airmass(apparent_zenith),
                         dtype=float)
    irradiance = [np.asarray(frame[k], dtype=float) for k in ("dni", "ghi", "dhi")]
    results = pd.DataFrame(index=frame.index)
    orientation_cache: dict[tuple[float, float], tuple[np.ndarray, np.ndarray]] = {}
    per_panel = []
    shade_fracs: dict[str, np.ndarray] = {}
    for panel in panels:
        orientation = (panel.tilt, panel.azimuth)
        if orientation not in orientation_cache:
            poa = pvlib.irradiance.get_total_irradiance(
                surface_tilt=panel.tilt, surface_azimuth=panel.azimuth,
                solar_zenith=apparent_zenith, solar_azimuth=solar_az,
                dni=irradiance[0], ghi=irradiance[1], dhi=irradiance[2],
                dni_extra=extra, airmass=airmass, albedo=req.albedo,
                model=req.model,
            )
            orientation_cache[orientation] = tuple(
                np.clip(np.nan_to_num(np.asarray(poa[k], dtype=float)), 0, 1800)
                for k in ("poa_global", "poa_direct")
            )
        global_poa, direct_poa = orientation_cache[orientation]
        fractions = np.zeros(n, dtype=float)
        for index, (elev, az) in enumerate(zip(solar_elev, solar_az)):
            if not np.isfinite(elev) or elev <= 0:
                continue
            if direct_poa[index] <= 0:
                continue
            fraction, _ = fraction_blocked(
                panel, req.objects, direction_towards_sun(float(az), float(elev)),
                rows=req.sample_rows, columns=req.sample_columns, meshes=req.meshes,
            )
            fractions[index] = fraction if fraction is not None else 0
        shade_fracs[panel.id] = fractions
        shaded_poa = np.clip(global_poa - direct_poa * fractions, 0, None)
        spec = meta_by_panel[panel.id]
        # Faiman defaults (generic module thermal performance) and PVWatts.
        # No cell-substring or string electrical interaction is imposed here.
        baseline_cell = pvlib.temperature.faiman(
            global_poa, np.asarray(frame["temp_air"], dtype=float),
            np.asarray(frame["wind_speed"], dtype=float))
        shaded_cell = pvlib.temperature.faiman(
            shaded_poa, np.asarray(frame["temp_air"], dtype=float),
            np.asarray(frame["wind_speed"], dtype=float))
        ref_dc = np.clip(pvlib.pvsystem.pvwatts_dc(
            global_poa, baseline_cell, pdc0=spec.pmax_w,
            gamma_pdc=spec.gamma_pmax_pct_c / 100), 0, None)
        shaded_dc = np.clip(pvlib.pvsystem.pvwatts_dc(
            shaded_poa, shaded_cell, pdc0=spec.pmax_w,
            gamma_pdc=spec.gamma_pmax_pct_c / 100), 0, None)
        results["ref_" + panel.id] = ref_dc
        results["shade_" + panel.id] = shaded_dc
        per_panel.append({
            "id": panel.id, "model_id": spec.id,
            "reference_independent_dc_potential_kwh": round(float(ref_dc.sum()) / 1000, 4),
            "shaded_independent_dc_potential_kwh": round(float(shaded_dc.sum()) / 1000, 4),
            "direct_area_blocked_mean_daylight": round(float(
                np.mean(fractions[direct_poa > 0]) if (direct_poa > 0).any() else 0), 5),
        })
    results["dc_reference_potential_w"] = results[
        ["ref_" + p.id for p in panels]].sum(axis=1)
    results["dc_shaded_potential_w"] = results[
        ["shade_" + p.id for p in panels]].sum(axis=1)
    # Not a tracker model: PVWatts on the independent-sum DC upper-bound proxy.
    inverter_dc0 = req.design.inverter.rated_ac_power_w / 0.96
    results["ac_reference_proxy_w"] = np.clip(pvlib.inverter.pvwatts(
        results["dc_reference_potential_w"].to_numpy(), inverter_dc0), 0, None)
    results["ac_shaded_proxy_w"] = np.clip(pvlib.inverter.pvwatts(
        results["dc_shaded_potential_w"].to_numpy(), inverter_dc0), 0, None)
    strings = []
    mppt_totals: dict[str, dict[str, float]] = {
        x.id: {"reference_kwh": 0, "shaded_kwh": 0} for x in req.design.inverter.mppts}
    for s in req.design.strings:
        baseline = sum(float(results["ref_" + id].sum()) for id in s.module_ids) / 1000
        shaded = sum(float(results["shade_" + id].sum()) for id in s.module_ids) / 1000
        strings.append({"id": s.id, "mppt_id": s.mppt_id,
                        "unconstrained_dc_reference_kwh": round(baseline, 4),
                        "unconstrained_dc_shaded_kwh": round(shaded, 4)})
        if s.mppt_id in mppt_totals:
            mppt_totals[s.mppt_id]["reference_kwh"] += baseline
            mppt_totals[s.mppt_id]["shaded_kwh"] += shaded
    monthly = _month_bins(results, (
        "dc_reference_potential_w", "dc_shaded_potential_w",
        "ac_reference_proxy_w", "ac_shaded_proxy_w",
    ))
    reference = float(results["ac_reference_proxy_w"].sum()) / 1000
    shaded = float(results["ac_shaded_proxy_w"].sum()) / 1000
    loss_pct = 100 * (reference - shaded) / reference if reference > 0 else 0
    return {
        "model": "F5_PVWATTS_MODULE_POTENTIAL_V1",
        "validated_electrical_yield": False,
        "full_year": metadata["full_utc_calendar_year"],
        "period": {"start_utc": frame.index[0].isoformat(),
                   "end_utc": frame.index[-1].isoformat(), "hours": n},
        "weather": metadata,
        "assumptions": [
            "Hourly means at UTC hour starts; solar position evaluated at +30 min",
            "PVWatts DC per independent module; uniform effective-POA fraction",
            "Faiman generic temperature model; no calibrated thermal mounting",
            "Direct-beam geometric shade removed from POA; diffuse and ground retained",
            "No bypass/mismatch/string current constraint or true MPPT control",
            "String/MPPT sums represent unconstrained DC potential only",
            "PVWatts AC result is an indicative unconstrained-system proxy, not bankable AC yield",
            "Calendar months UTC, no annual extrapolation for partial weather data",
        ],
        "modules": per_panel,
        "strings": strings,
        "mppts": [{"id": id,
                   "unconstrained_dc_reference_kwh": round(v["reference_kwh"], 4),
                   "unconstrained_dc_shaded_kwh": round(v["shaded_kwh"], 4)}
                  for id, v in mppt_totals.items()],
        "summary": {
            "reference_ac_proxy_kwh": round(reference, 4),
            "shaded_ac_proxy_kwh": round(shaded, 4),
            "proxy_difference_percent": round(loss_pct, 4),
            "reference_dc_potential_kwh": round(float(results["dc_reference_potential_w"].sum()) / 1000, 4),
            "shaded_dc_potential_kwh": round(float(results["dc_shaded_potential_w"].sum()) / 1000, 4),
        },
        "monthly": monthly,
    }
