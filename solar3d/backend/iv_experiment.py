"""F4.2 opt-in generic photovoltaic IV benchmark using open-source PVMismatch.

The stock STD72 cell physics are NOT calibrated to any catalog/module; this
endpoint is an education/algorithm-validation experiment. No claim of annual
production, commercial design fit, or interchangeability with PVsyst.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
import numpy as np


class IvExperimentRequest(BaseModel):
    modules_in_series: int = Field(default=3, ge=1, le=8)
    shaded_module_index: int = Field(default=0, ge=0)
    blocked_cell_indices: list[int] = Field(default_factory=lambda: list(range(12)), max_length=72)
    clear_irradiance_suns: float = Field(default=1.0, gt=0, le=1.2, allow_inf_nan=False)
    blocked_irradiance_suns: float = Field(default=0.2, ge=0, le=1.2, allow_inf_nan=False)
    cell_temperature_c: float = Field(default=25, ge=-15, le=85, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_cells(self):
        if self.shaded_module_index >= self.modules_in_series:
            raise ValueError("Índice do módulo sombreado fora da string")
        if len(set(self.blocked_cell_indices)) != len(self.blocked_cell_indices):
            raise ValueError("Índices de células repetidos")
        if any(i < 0 or i >= 72 for i in self.blocked_cell_indices):
            raise ValueError("Índice de célula fora de [0,71]")
        if self.blocked_irradiance_suns > self.clear_irradiance_suns:
            raise ValueError("A irradiância das células bloqueadas não pode superar a livre")
        return self


def _curve(system) -> dict:
    """Subsample a trace without fabricating an interpolation or missing MPP."""
    raw_v = np.asarray(system.Vsys, dtype=float)
    raw_i = np.asarray(system.Isys, dtype=float)
    valid = np.isfinite(raw_v) & np.isfinite(raw_i) & (raw_v >= 0) & (raw_i >= 0)
    v = raw_v[valid]
    i = raw_i[valid]
    if len(v) < 5:
        raise ValueError("Curva I–V inválida")
    ix = np.linspace(0, len(v) - 1, num=min(100, len(v))).astype(int)
    return {
        "v_v": [round(float(z), 4) for z in v[ix]],
        "i_a": [round(float(z), 4) for z in i[ix]],
        "p_w": [round(float(z), 4) for z in (v[ix] * i[ix])],
        "pmp_w": round(float(max(np.max(v * i), 0)), 4),
    }


def iv_experiment(req: IvExperimentRequest) -> dict:
    try:
        from pvmismatch.pvmismatch_lib.pvconstants import PVconstants
        from pvmismatch.pvmismatch_lib.pvmodule import PVmodule, STD72
        from pvmismatch.pvmismatch_lib.pvstring import PVstring
        from pvmismatch.pvmismatch_lib.pvsystem import PVsystem
    except ImportError as exc:
        raise RuntimeError("PVMismatch experimental não instalado") from exc
    pc = PVconstants(npts=101)
    generic = PVmodule(cell_pos=STD72, pvconst=pc)
    string = PVstring(numberMods=req.modules_in_series, pvmods=generic, pvconst=pc)
    system = PVsystem(numberStrs=1, pvstrs=string, pvconst=pc)
    system.setSuns(req.clear_irradiance_suns)
    system.setTemps(req.cell_temperature_c + 273.15)
    reference = _curve(system)
    if req.blocked_cell_indices:
        system.setSuns({
            0: {
                req.shaded_module_index: {
                    "Ee": req.blocked_irradiance_suns,
                    "cells": tuple(req.blocked_cell_indices),
                },
            },
        })
    shaded = _curve(system)
    if reference["pmp_w"] <= 0:
        raise ValueError("Potência de referência inválida")
    return {
        "model": "PVMismatch generic STD72 / 3 default bypass substrings",
        "model_calibrated_to_equipment": False,
        "experimental": True,
        "reference": reference,
        "shaded": shaded,
        "difference_pct": round(
            100 * (reference["pmp_w"] - shaded["pmp_w"]) / reference["pmp_w"], 3
        ),
        "limitations": [
            "STD72 legacy 72-cell generic layout: NOT a half-cut or HJT/TOPCon datasheet fit",
            "module Pmax/Voc/Vmp/Isc/Imp not calibrated to actual catalog entries",
            "shade cell selection does not yet map to arbitrary 3D F3 grid",
            "one generic series string only; no inverter/MPPT tracker",
            "instantaneous watts only, no meteorology or kWh",
            "PVMismatch version 4.1 (2019); numerical behaviour requires reference calibration",
        ],
    }
