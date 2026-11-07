"""Unshaded hourly solar resource contract for GreenCity OS scene analysis.

The endpoint does not know obstacles, modules, strings, MPPTs, inverters,
or equipment output. A caller may apply a consistent geometric DIRECT
shadow mask to POA-direct and leave POA diffuse + ground unchanged.
It is NOT an electrical or panel-temperature energy-yield prediction.
"""
from __future__ import annotations

import calendar
from typing import Literal

import numpy as np
import pandas as pd
import pvlib
from pydantic import BaseModel, Field

from core.solar_physics import validate_weather


class HourlyResourceRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    inclinacao_graus: float = Field(default=15, ge=0, le=90, allow_inf_nan=False)
    azimute_graus: float = Field(default=0, ge=0, le=360, allow_inf_nan=False)
    albedo_solo: float = Field(default=0.2, ge=0, le=1, allow_inf_nan=False)
    modelo_transposicao: Literal["perez", "haydavies", "isotropic"] = "perez"
    fonte_dados: Literal["auto", "NASA POWER", "PVGIS"] = "auto"
    ano_utc: int | None = Field(default=None, ge=2001, le=2026)
    mes_utc: int | None = Field(default=None, ge=1, le=12)


def select_calendar_year(hourly: pd.DataFrame, year: int | None) -> tuple[pd.DataFrame, int]:
    """Choose an actually complete hourly UTC calendar year; never extrapolate."""
    if not isinstance(hourly, pd.DataFrame) or not isinstance(hourly.index, pd.DatetimeIndex):
        raise ValueError("Fonte meteorológica não retornou série horária")
    if hourly.index.tz is None:
        raise ValueError("Série meteorológica precisa possuir timezone")
    frame = hourly.copy()
    frame.index = frame.index.tz_convert("UTC")
    options = [int(year)] if year is not None else sorted(
        (int(y) for y in frame.index.year.unique()), reverse=True)
    for candidate in options:
        part = frame[frame.index.year == candidate].copy()
        hours = 8784 if calendar.isleap(candidate) else 8760
        if (len(part) != hours or part.index[0] != pd.Timestamp(f"{candidate}-01-01", tz="UTC")
                or part.index[-1] != pd.Timestamp(f"{candidate}-12-31 23:00", tz="UTC")):
            continue
        validate_weather(part)
        return part, candidate
    raise ValueError(
        f"Não existe ano civil UTC completo na fonte para ano_utc={year}; "
        "escolha um ano disponível na série horária"
    )


def resource_hourly(req: HourlyResourceRequest, repository) -> dict:
    provider = None if req.fonte_dados == "auto" else req.fonte_dados
    climate = repository.get_standardized_data(
        req.latitude, req.longitude, force_provider=provider)
    df, selected_year = select_calendar_year(climate.get("hourly"), req.ano_utc)
    # NASA POWER labels 1h intervals by their START. Mid-hour sun position
    # is consistent with the pre-existing /calcular POA engine.
    times = df.index + pd.Timedelta(minutes=30)
    solar = pvlib.solarposition.get_solarposition(
        times, latitude=req.latitude, longitude=req.longitude)
    zenith = np.asarray(solar["apparent_zenith"], dtype=float)
    azimuth = np.asarray(solar["azimuth"], dtype=float)
    elevation = np.asarray(solar["apparent_elevation"], dtype=float)
    ghi, dni, dhi = [np.asarray(df[k], dtype=float) for k in ("ghi", "dni", "dhi")]
    extra = np.asarray(pvlib.irradiance.get_extra_radiation(times), dtype=float)
    air = np.asarray(pvlib.atmosphere.get_relative_airmass(zenith), dtype=float)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=req.inclinacao_graus,
        surface_azimuth=req.azimute_graus,
        solar_zenith=zenith, solar_azimuth=azimuth,
        dni=dni, ghi=ghi, dhi=dhi, dni_extra=extra, airmass=air,
        albedo=req.albedo_solo, model=req.modelo_transposicao,
    )
    fields = {
        k: np.clip(np.nan_to_num(np.asarray(poa[k], dtype=float), nan=0., posinf=0.), 0, None)
        for k in ("poa_global", "poa_direct", "poa_sky_diffuse", "poa_ground_diffuse")
    }
    # Reuse the horizontal-plane identity guaranteed by /calcular. Some
    # synthetic/provider DNI+DHI sums can differ from the measured GHI.
    if req.inclinacao_graus == 0:
        fields["poa_global"] = ghi.copy()
        fields["poa_direct"] = np.clip(ghi-dhi, 0, None)
        fields["poa_sky_diffuse"] = np.minimum(dhi, ghi)
        fields["poa_ground_diffuse"] = np.zeros_like(ghi)
    # The annual HSP is daily-averaged irradiance on the module plane; it
    # contains no obstacle losses and no electrical effects.
    full = pd.DataFrame(fields, index=df.index)
    monthly = full["poa_global"].resample("D").sum().groupby(
        lambda timestamp: timestamp.month).mean().reindex(range(1, 13)) / 1000
    if monthly.isna().any():
        raise ValueError("Fonte sem cobertura completa dos doze meses")
    if req.mes_utc is not None:
        mask = np.asarray(df.index.month == req.mes_utc)
    else:
        mask = np.ones(len(df), dtype=bool)
    indices = np.flatnonzero(mask)
    samples = []
    for index in indices:
        samples.append({
            "inicio_utc": df.index[index].isoformat(),
            "azimute_solar_graus": round(float(azimuth[index]), 4),
            "elevacao_solar_aparente_graus": round(float(elevation[index]), 4),
            "ghi_w_m2": round(float(ghi[index]), 4),
            "dni_w_m2": round(float(dni[index]), 4),
            "dhi_w_m2": round(float(dhi[index]), 4),
            "poa_total_w_m2": round(float(fields["poa_global"][index]), 4),
            "poa_direta_w_m2": round(float(fields["poa_direct"][index]), 4),
            "poa_difusa_ceu_w_m2": round(float(fields["poa_sky_diffuse"][index]), 4),
            "poa_refletida_solo_w_m2": round(float(fields["poa_ground_diffuse"][index]), 4),
        })
    return {
        "schema_version": 1,
        "modelo": "recurso_solar_poa_horario_sem_obstaculos_v1",
        "sem_obstaculos": True,
        "sem_perdas_eletricas": True,
        "convencao": "azimute 0=N 90=L 180=S 270=O; horas UTC início do intervalo",
        "periodo": {
            "ano_utc": selected_year,
            "mes_utc": req.mes_utc,
            "passo_minutos": 60,
            "horas_retornadas": len(samples),
            "ano_completo_validado": True,
        },
        "orientacao": {
            "inclinacao_graus": req.inclinacao_graus,
            "azimute_graus": req.azimute_graus,
            "albedo_solo": req.albedo_solo,
            "modelo_transposicao": req.modelo_transposicao,
        },
        "fonte": climate.get("metadata", {}).get("source", req.fonte_dados),
        "hsp_referencia_mensal_kwh_m2_dia": [round(float(x), 6) for x in monthly],
        "amostras": samples,
        "limitacoes": [
            "Apenas irradiancia horaria de referencia; sem obstaculos e sem perda eletrica",
            "Data/hora UTC representam inicio da media horaria; posicao solar no meio da hora",
            "Amostras mensais opcionais preservam o HSP anual de referencia",
            "Em cenas 3D, subtraia somente a fracao bloqueada do POA direto",
            "Sem vista de ceu difusa, reflexoes locais nem obstrucao da face traseira",
            "Nao equivale a energia DC/AC nem a eficiencia de string ou MPPT",
        ],
    }
