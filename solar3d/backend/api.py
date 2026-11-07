"""Solar 3D lab: solar ephemerides, separate from the existing HSP API.

All physical positions are produced by pvlib. The 3D client only renders
these coordinates; its shadow map is VISUAL, not a yield/loss simulation.
"""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator
from pvlib import solarposition

app = FastAPI(
    title="Solar 3D Lab — solar geometry",
    version="0.1.0",
    description="Isolated solar geometry service (not an electrical yield estimator).",
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "solar3d-geometry", "version": "0.1.0"}


@app.post("/solar3d/solar-day")
def solar_day(request: SolarDayRequest) -> dict:
    """Position of the sun during a *local civil day*, accounting for DST.

    Index is generated in the IANA time zone rather than assuming UTC-3
    for every geographical location. On historical DST transitions a day
    may have 23 or 25 hours. The end is exclusive.
    """
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
