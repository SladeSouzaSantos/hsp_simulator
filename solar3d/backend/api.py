"""Solar 3D lab: solar ephemerides and geometric direct-shadow sampling.

Independent of the HSP v2 REST API. Shadow fractions represent sampled
area blocking of direct-beam irradiance ONLY; no kWh or electrical losses.
"""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator, model_validator
from pvlib import solarposition

from solar3d.backend.shading import (
    SceneObject, direction_towards_sun, fraction_blocked,
)

app = FastAPI(
    title="Solar 3D Lab — solar geometry and direct-beam shading",
    version="0.2.0",
    description="Isolated geometry service. Does not estimate electrical generation.",
)


class SolarDayRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    local_date: date
    timezone: str = Field(default="America/Fortaleza", min_length=1, max_length=128)
    interval_minutes: int = Field(default=15, ge=5, le=60)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise ValueError("Informe um fuso horário IANA válido") from exc
        return value

    @field_validator("interval_minutes")
    @classmethod
    def valid_interval(cls, value: int) -> int:
        if 60 % value:
            raise ValueError("O intervalo precisa dividir uma hora exatamente")
        return value


class ShadingDayRequest(SolarDayRequest):
    objects: list[SceneObject] = Field(min_length=1, max_length=100)
    sample_rows: int = Field(default=6, ge=2, le=12)
    sample_columns: int = Field(default=4, ge=2, le=12)
    schema_version: int = Field(default=1, ge=1, le=1)

    @model_validator(mode="after")
    def validate_scene_budget(self):
        ids = [obj.id for obj in self.objects]
        if len(set(ids)) != len(ids):
            raise ValueError("Os IDs dos objetos devem ser únicos")
        panels = sum(obj.kind == "panel" for obj in self.objects)
        if panels == 0:
            raise ValueError("A cena precisa conter ao menos um módulo")
        if panels > 48:
            raise ValueError("Limite de 48 módulos nesta versão síncrona")
        # Conservatively budget all time steps; actual direct-sun count
        # is lower. Larger scenes need a queued/batched worker.
        steps = 25 * 60 // self.interval_minutes + 1
        complexity = (steps * panels * self.sample_rows *
                      self.sample_columns * max(1, len(self.objects) - 1))
        if complexity > 2_000_000:
            raise ValueError("Cena excede orçamento síncrono: diminua objetos ou amostragem")
        return self


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "solar3d-geometry", "version": "0.2.0"}


@app.post("/solar3d/solar-day")
def solar_day(request: SolarDayRequest) -> dict:
    """Position of the sun during a local civil day, including DST changes."""
    start = pd.Timestamp(request.local_date.isoformat(), tz=request.timezone)
    end = start + pd.DateOffset(days=1)
    times = pd.date_range(
        start=start,
        end=end,
        freq=f"{request.interval_minutes}min",
        inclusive="left",
    )
    sun = solarposition.get_solarposition(
        times,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    samples = []
    for timestamp, (_, data) in zip(times, sun.iterrows()):
        samples.append({
            "local_time": timestamp.isoformat(),
            "utc_time": timestamp.tz_convert("UTC").isoformat(),
            "azimuth_deg": round(float(data["azimuth"]), 6),
            "elevation_deg": round(float(data["elevation"]), 6),
            "apparent_elevation_deg": round(float(data["apparent_elevation"]), 6),
        })
    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "local_date": request.local_date.isoformat(),
        "timezone": request.timezone,
        "interval_minutes": request.interval_minutes,
        "convention": "azimuth 0=N, 90=E, 180=S, 270=W; elevation + above horizon",
        "samples": samples,
        "visual_only": True,
    }


@app.post("/solar3d/shading-day")
def shading_day(request: ShadingDayRequest) -> dict:
    """Compute geometric front-surface direct-beam blocked fraction.

    Every module is sampled on a regular grid of cell centers; all other
    solid objects and modules may occlude the Sun (opaque-body ray casting).
    Ineligible time steps (night or sun behind module) are returned as
    fraction=null, and excluded from the geometric average.
    """
    solar = solar_day(request)
    objects = request.objects
    modules = [obj for obj in objects if obj.kind == "panel"]
    directions = [
        direction_towards_sun(s["azimuth_deg"], s["apparent_elevation_deg"])
        for s in solar["samples"]
    ]
    results = []
    for panel in modules:
        frames = []
        eligible = []
        shaded_count = 0
        for direction in directions:
            fraction, cells = fraction_blocked(
                panel, objects, direction,
                columns=request.sample_columns, rows=request.sample_rows,
            )
            if fraction is not None:
                eligible.append(fraction)
                shaded_count += int(fraction > 0)
            frames.append({
                "blocked_fraction": None if fraction is None else round(fraction, 6),
                "blocked_cells": cells,
            })
        results.append({
            "id": panel.id,
            "name": panel.name,
            "direct_eligible_intervals": len(eligible),
            "shaded_direct_intervals": shaded_count,
            "mean_blocked_fraction_direct_eligible": (
                round(sum(eligible) / len(eligible), 6) if eligible else None
            ),
            "frames": frames,
        })
    return {
        "schema_version": 1,
        "geometry_only": True,
        "model": "ray_oriented_boxes_front_sampling_v1",
        "quantity": "fraction_of_direct_front_area",
        "latitude": request.latitude,
        "longitude": request.longitude,
        "local_date": request.local_date.isoformat(),
        "timezone": request.timezone,
        "interval_minutes": request.interval_minutes,
        "sampling": {
            "rows": request.sample_rows,
            "columns": request.sample_columns,
            "cells_per_module": request.sample_rows * request.sample_columns,
        },
        "solar_samples_utc": [s["utc_time"] for s in solar["samples"]],
        "modules": results,
        "limitations": [
            "no hourly irradiance weighting: geometric daytime average only",
            "direct beam only; no diffuse sky/ground or horizon",
            "uniform grid-center quadrature; discretization error",
            "opaque oriented boxes only; no vegetation translucency/mesh terrain",
            "no electrical loss, MPPT, strings, inverter AC or kWh simulation",
        ],
    }
