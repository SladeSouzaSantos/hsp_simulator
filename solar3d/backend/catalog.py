"""GreenCity OS equipment-export adapter — strict, fail-closed import.

Accepts explicitly exported Isar entity JSON objects, not a repository scrape
or live mobile database. Source values are preserved; missing beta_Vmp and
MPPT-specific capacities are NEVER guessed. 'verified' is always false until
an engineer checks source datasheets independently.
"""
from __future__ import annotations
import json
import math
from typing import Any

from pydantic import BaseModel, Field, model_validator

from solar3d.backend.electrical import ModuleSpec, InverterSpec, MpptSpec


class GreencityExport(BaseModel):
    format: str = Field(pattern=r"^greencity-os-equipment-v1$")
    modules: list[dict[str, Any]] = Field(default_factory=list, max_length=300)
    inverters: list[dict[str, Any]] = Field(default_factory=list, max_length=150)
    source_revision: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def require_nonempty(self):
        if not self.modules and not self.inverters:
            raise ValueError("Exportação vazia")
        return self


def _num(raw: dict[str, Any], key: str) -> float | None:
    v = raw.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if not math.isfinite(float(v)):
        return None
    return float(v)


def _identity(raw: dict[str, Any]) -> tuple[str, str] | None:
    brand, model = raw.get("manufacturer"), raw.get("modelName")
    if not isinstance(brand, str) or not isinstance(model, str):
        return None
    brand, model = brand.strip(), model.strip()
    if not brand or not model or len(brand) > 100 or len(model) > 120:
        return None
    return brand, model


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value.upper()).strip("-")[:55]


def _module(raw: dict[str, Any]) -> dict:
    problems: list[str] = []
    identity = _identity(raw)
    if identity is None:
        return {"status": "blocked", "problems": ["manufacturer/modelName inválidos"],
                "name": "", "data": None}
    brand, model = identity
    conversion = {
        "pmax_w": "powerWp",
        "voc_v": "vOc",
        "vmp_v": "vMp",
        "isc_a": "iSc",
        "imp_a": "iMp",
        "beta_voc_pct_c": "tempCoefVoc",
        "beta_vmp_pct_c": "tempCoefVmp",
        "alpha_isc_pct_c": "tempCoefIsc",
        "gamma_pmax_pct_c": "tempCoefPmax",
    }
    kwargs: dict[str, Any] = {}
    for target, source in conversion.items():
        val = _num(raw, source)
        if val is None:
            problems.append("Campo obrigatório ausente/não numérico: " + source)
        else:
            kwargs[target] = val
    if "tempCoefVmp" not in raw and "tempCoefPmax" in raw:
        problems.append("tempCoefPmax NÃO pode substituir tempCoefVmp")
    if problems:
        return {"status": "blocked", "name": f"{brand} {model}",
                "problems": problems, "data": None,
                "source": raw.get("source_url") if isinstance(raw.get("source_url"), str) else None}
    try:
        module = ModuleSpec(id="GC-" + _slug(brand + "-" + model),
                            manufacturer=brand, model=model,
                            verified_datasheet=False, **kwargs)
    except ValueError as exc:
        return {"status": "blocked", "name": f"{brand} {model}",
                "problems": [str(exc)], "data": None}
    return {"status": "review", "name": f"{brand} {model}", "problems": [
        "Conferir datasheet oficial e polaridade/unidades dos coeficientes"
    ], "data": module.model_dump(),
        "source": raw.get("source_url") if isinstance(raw.get("source_url"), str) else None}


def _mppts(raw: dict[str, Any], count: int, name: str) -> tuple[list[dict] | None, list[str]]:
    problems = []
    config = raw.get("mpptConfigurationJson")
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except ValueError:
            config = None
            problems.append("mpptConfigurationJson é JSON inválido")
    if not isinstance(config, dict):
        config = {}
    currents = config.get("inputCurrentsA")
    short = config.get("shortCircuitCurrentsA")
    input_counts = config.get("stringsPerMppt")
    if not all(isinstance(v, list) and len(v) == count for v in (currents, short, input_counts)):
        problems.append(
            "Faltam inputCurrentsA, shortCircuitCurrentsA e stringsPerMppt "
            "individualizados para todos os MPPTs"
        )
        return None, problems
    min_v = _num(raw, "minMpptVoltage")
    max_v = _num(raw, "maxMpptVoltage")
    if min_v is None or max_v is None:
        problems.append("minMpptVoltage/maxMpptVoltage inválidos")
        return None, problems
    mppts = []
    for idx in range(count):
        try:
            mppts.append(MpptSpec(
                id=f"MPPT{idx + 1}",
                min_voltage_v=min_v, max_voltage_v=max_v,
                max_input_current_a=float(currents[idx]),
                max_short_circuit_current_a=float(short[idx]),
                max_parallel_strings=int(input_counts[idx]),
            ).model_dump())
        except (ValueError, TypeError, OverflowError) as exc:
            problems.append(f"MPPT{idx+1} inválido: {exc}")
    return (mppts if not problems else None), problems


def _inverter(raw: dict[str, Any]) -> dict:
    identity = _identity(raw)
    if identity is None:
        return {"status": "blocked", "problems": ["manufacturer/modelName inválidos"],
                "name": "", "data": None}
    brand, model = identity
    problems: list[str] = []
    count = _num(raw, "mpptCount")
    if count is None or not count.is_integer() or not 1 <= count <= 8:
        problems.append("mpptCount ausente ou inválido")
        mppts = None
    else:
        mppts, mppt_issues = _mppts(raw, int(count), model)
        problems.extend(mppt_issues)
    max_dc = _num(raw, "maxInputVoltage")
    nominal = _num(raw, "nominalPowerKw")
    if max_dc is None or nominal is None:
        problems.append("maxInputVoltage/nominalPowerKw inválidos")
    if problems:
        return {"status": "blocked", "name": f"{brand} {model}",
                "problems": problems, "data": None,
                "source": raw.get("source_url") if isinstance(raw.get("source_url"), str) else None}
    try:
        inverter = InverterSpec(
            id="GC-" + _slug(brand + "-" + model), manufacturer=brand,
            model=model, max_dc_voltage_v=max_dc,
            rated_ac_power_w=1000 * nominal, mppts=[MpptSpec(**x) for x in mppts],
            verified_datasheet=False,
        )
    except ValueError as exc:
        return {"status": "blocked", "name": f"{brand} {model}",
                "problems": [str(exc)], "data": None}
    return {"status": "review", "name": f"{brand} {model}",
            "problems": ["Conferir capacidades de entradas físicas e datasheet por MPPT"],
            "data": inverter.model_dump(),
            "source": raw.get("source_url") if isinstance(raw.get("source_url"), str) else None}


def preview_import(data: GreencityExport) -> dict:
    entries: list[dict] = []
    seen = set()
    for kind, source, fn in (
        ("module", data.modules, _module),
        ("inverter", data.inverters, _inverter),
    ):
        for raw in source:
            result = fn(raw)
            signature = (kind, result["name"].casefold().strip())
            if signature in seen:
                result = {**result, "status": "blocked", "data": None,
                          "problems": ["Fabricante/modelo duplicado na exportação"]}
            seen.add(signature)
            entries.append({"kind": kind, **result})
    ready = sum(x["status"] == "review" for x in entries)
    blocked = len(entries) - ready
    return {
        "format": "solar3d-staged-catalog-v1",
        "source": "greencity-os-equipment-v1",
        "source_revision": data.source_revision,
        "totals": {"entries": len(entries), "reviewable": ready, "blocked": blocked},
        "entries": entries,
        "warnings": [
            "Importação não aprova datasheets nem marca equipamentos como verificados.",
            "Itens sem dados de Vmp térmico ou limites individualizados dos MPPTs ficam bloqueados.",
            "Conferir manualmente fabricante/modelo, unidades e origem dos dados.",
        ],
    }
