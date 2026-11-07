"""Solar 3D Lab F4 — deterministic electrical topology checks (no yield prediction).

Pure, reproducible nameplate validation with conservative cold/hot cell-temp
assumptions. The input must be transcribed and checked against manufacturer
datasheets before installation use. These checks do NOT replace IEC/ABNT
design, wiring protection, thermal modelling, or a PVsyst-equivalent simulation.
"""
from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ModuleSpec(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    manufacturer: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=120)
    pmax_w: float = Field(gt=0, le=1500, allow_inf_nan=False)
    voc_v: float = Field(gt=0, le=200, allow_inf_nan=False)
    vmp_v: float = Field(gt=0, le=200, allow_inf_nan=False)
    isc_a: float = Field(gt=0, le=50, allow_inf_nan=False)
    imp_a: float = Field(gt=0, le=50, allow_inf_nan=False)
    beta_voc_pct_c: float = Field(ge=-1, le=0, allow_inf_nan=False)
    beta_vmp_pct_c: float = Field(ge=-1, le=0, allow_inf_nan=False)
    alpha_isc_pct_c: float = Field(ge=0, le=1, allow_inf_nan=False)
    verified_datasheet: bool = False

    @model_validator(mode="after")
    def basic_physics(self):
        if self.vmp_v >= self.voc_v or self.imp_a > self.isc_a:
            raise ValueError("Módulo: exigir Vmp < Voc e Imp <= Isc")
        return self


class MpptSpec(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    min_voltage_v: float = Field(gt=0, le=2000, allow_inf_nan=False)
    max_voltage_v: float = Field(gt=0, le=2000, allow_inf_nan=False)
    max_input_current_a: float = Field(gt=0, le=500, allow_inf_nan=False)
    max_short_circuit_current_a: float = Field(gt=0, le=500, allow_inf_nan=False)
    max_parallel_strings: int = Field(ge=1, le=20)

    @model_validator(mode="after")
    def sensible_ranges(self):
        if self.max_voltage_v <= self.min_voltage_v:
            raise ValueError("MPPT: tensão máxima deve ser superior à mínima")
        if self.max_short_circuit_current_a < self.max_input_current_a:
            raise ValueError("MPPT: corrente de curto máxima inferior à corrente de entrada")
        return self


class InverterSpec(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    manufacturer: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=120)
    max_dc_voltage_v: float = Field(gt=0, le=2500, allow_inf_nan=False)
    rated_ac_power_w: float = Field(gt=0, le=10000000, allow_inf_nan=False)
    mppts: list[MpptSpec] = Field(min_length=1, max_length=8)
    verified_datasheet: bool = False

    @model_validator(mode="after")
    def check_mppt_ids(self):
        ids = [mppt.id for mppt in self.mppts]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs de MPPT devem ser exclusivos")
        for mppt in self.mppts:
            if mppt.max_voltage_v > self.max_dc_voltage_v:
                raise ValueError("Tensão máxima MPPT não pode superar limite DC absoluto")
        return self


class StringSpec(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    mppt_id: str = Field(min_length=1, max_length=50)
    module_ids: list[str] = Field(default_factory=list, max_length=100)


class ElectricalDesign(BaseModel):
    module_catalog: list[ModuleSpec] = Field(min_length=1, max_length=50)
    module_model_ids: dict[str, str] = Field(default_factory=dict)
    inverter: InverterSpec
    strings: list[StringSpec] = Field(default_factory=list, max_length=64)
    min_cell_temp_c: float = Field(ge=-50, le=65, allow_inf_nan=False)
    max_cell_temp_c: float = Field(ge=25, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_identity(self):
        ids = [spec.id for spec in self.module_catalog]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs dos modelos de módulos devem ser exclusivos")
        ids = [string.id for string in self.strings]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs de strings devem ser exclusivos")
        if self.min_cell_temp_c >= self.max_cell_temp_c:
            raise ValueError("Temperatura mínima da célula deve ser menor que a máxima")
        return self


class ElectricalValidationRequest(BaseModel):
    panel_ids: list[str] = Field(max_length=250)
    design: ElectricalDesign

    @model_validator(mode="after")
    def unique_panels(self):
        if len(set(self.panel_ids)) != len(self.panel_ids):
            raise ValueError("IDs de módulos 3D duplicados")
        if any(not s or len(s) > 120 for s in self.panel_ids):
            raise ValueError("ID de módulo 3D inválido")
        return self


def check_electrical_design(req: ElectricalValidationRequest) -> dict:
    """Validate physical nameplate limits and topology.

    Series => voltages add; parallel => currents add. Results at temperature
    extremes are approximate linear datasheet-coefficient extrapolations,
    not predictions of irradiance, bypass, power or AC output.
    """
    design = req.design
    panel_ids = set(req.panel_ids)
    modules = {module.id: module for module in design.module_catalog}
    trackers = {mppt.id: mppt for mppt in design.inverter.mppts}
    issues: list[dict] = []
    def issue(code: str, severity: Literal["error", "warning"], message: str,
              scope: str = "design") -> None:
        issues.append({"code": code, "severity": severity, "scope": scope, "message": message})

    if not design.inverter.verified_datasheet:
        issue("INVERTER_UNVERIFIED", "warning", "Dados do inversor não conferidos em datasheet.")
    for spec in design.module_catalog:
        if not spec.verified_datasheet and spec.id in set(design.module_model_ids.values()):
            issue("MODULE_UNVERIFIED", "warning",
                  f"Modelo {spec.model}: confira os parâmetros elétricos no datasheet.", spec.id)
    for panel in req.panel_ids:
        if panel not in design.module_model_ids:
            issue("MODEL_UNASSIGNED", "error", f"Módulo {panel} sem modelo elétrico.", panel)
        elif design.module_model_ids[panel] not in modules:
            issue("UNKNOWN_MODEL", "error", f"Módulo {panel} usa um modelo inexistente.", panel)
    for panel in design.module_model_ids:
        if panel not in panel_ids:
            issue("STALE_MODEL_ASSIGNMENT", "warning",
                  f"Associação de modelo do módulo removido {panel}.", panel)

    seen: set[str] = set()
    per_mppt: dict[str, list[dict]] = {id: [] for id in trackers}
    string_results: list[dict] = []
    total_dc_w = 0.0
    for string in design.strings:
        scope = string.id
        members = string.module_ids
        if string.mppt_id not in trackers:
            issue("UNKNOWN_MPPT", "error",
                  f"String {scope} usa MPPT não cadastrado: {string.mppt_id}.", scope)
        if not members:
            issue("EMPTY_STRING", "warning", f"String {scope} está vazia.", scope)
            continue
        if len(set(members)) != len(members):
            issue("DUPLICATE_IN_STRING", "error",
                  f"String {scope} repete módulo.", scope)
        for panel in members:
            if panel not in panel_ids:
                issue("UNKNOWN_PANEL", "error",
                      f"String {scope} referencia módulo inexistente {panel}.", scope)
            if panel in seen:
                issue("MULTIPLE_STRING_ASSIGNMENT", "error",
                      f"Módulo {panel} aparece em mais de uma string.", scope)
            seen.add(panel)
        spec_ids = [design.module_model_ids.get(id) for id in members]
        if any(id not in modules for id in spec_ids):
            issue("STRING_MODEL_MISSING", "error",
                  f"String {scope} possui módulos sem especificação válida.", scope)
            continue
        if len(set(spec_ids)) != 1:
            issue("MIXED_MODULES_IN_SERIES", "error",
                  f"String {scope} mistura modelos elétricos; modo conservador exige módulos idênticos.", scope)
            continue
        spec = modules[spec_ids[0]]
        n = len(members)
        cold_delta = design.min_cell_temp_c - 25
        hot_delta = design.max_cell_temp_c - 25
        voc_cold = n * spec.voc_v * (1 + spec.beta_voc_pct_c / 100 * cold_delta)
        vmp_cold = n * spec.vmp_v * (1 + spec.beta_vmp_pct_c / 100 * cold_delta)
        vmp_hot = n * spec.vmp_v * (1 + spec.beta_vmp_pct_c / 100 * hot_delta)
        isc_hot = spec.isc_a * (1 + spec.alpha_isc_pct_c / 100 * hot_delta)
        # Proxy only: Imp temperature dependence is not independently modeled.
        imp_proxy = spec.imp_a * (1 + spec.alpha_isc_pct_c / 100 * hot_delta)
        if min(voc_cold, vmp_cold, vmp_hot, isc_hot, imp_proxy) <= 0:
            issue("TEMP_EXTRAPOLATION_INVALID", "error",
                  f"String {scope}: extrapolação de temperatura não física.", scope)
            continue
        if voc_cold > design.inverter.max_dc_voltage_v + 1e-8:
            issue("INVERTER_MAX_VOC", "error",
                  f"String {scope}: Voc frio {voc_cold:.1f} V excede limite DC absoluto.", scope)
        if string.mppt_id in trackers:
            tracker = trackers[string.mppt_id]
            if vmp_hot < tracker.min_voltage_v - 1e-8:
                issue("MPPT_MIN_VMP", "error",
                      f"String {scope}: Vmp quente {vmp_hot:.1f} V abaixo do mínimo MPPT.", scope)
            if vmp_cold > tracker.max_voltage_v + 1e-8:
                issue("MPPT_MAX_VMP", "error",
                      f"String {scope}: Vmp frio {vmp_cold:.1f} V acima do máximo MPPT.", scope)
        result = {"id": scope, "mppt_id": string.mppt_id, "module_model_id": spec.id,
                  "module_count": n, "nameplate_dc_w": round(n * spec.pmax_w, 3),
                  "voc_cold_v": round(voc_cold, 3),
                  "vmp_hot_v": round(vmp_hot, 3), "vmp_cold_v": round(vmp_cold, 3),
                  "isc_hot_a": round(isc_hot, 3), "imp_proxy_a": round(imp_proxy, 3)}
        string_results.append(result)
        total_dc_w += n * spec.pmax_w
        if string.mppt_id in per_mppt:
            per_mppt[string.mppt_id].append(result)

    for panel in panel_ids - seen:
        issue("UNCONNECTED_PANEL", "warning",
              f"Módulo {panel} ainda não pertence a uma string.", panel)

    mppt_results: list[dict] = []
    for tracker_id, tracker in trackers.items():
        strings = per_mppt[tracker_id]
        if len([s for s in design.strings if s.mppt_id == tracker_id]) > tracker.max_parallel_strings:
            issue("MPPT_MAX_STRINGS", "error", f"{tracker_id}: número de strings acima do limite.", tracker_id)
        current = sum(s["imp_proxy_a"] for s in strings)
        short = sum(s["isc_hot_a"] for s in strings)
        if current > tracker.max_input_current_a + 1e-8:
            issue("MPPT_MAX_INPUT_CURRENT", "error",
                  f"{tracker_id}: soma das correntes estimadas {current:.1f} A excede limite.", tracker_id)
        if short > tracker.max_short_circuit_current_a + 1e-8:
            issue("MPPT_MAX_SHORT_CURRENT", "error",
                  f"{tracker_id}: soma Isc quente {short:.1f} A excede limite.", tracker_id)
        if len(strings) > 1:
            extremes = [s["vmp_hot_v"] for s in strings]
            ratio = (max(extremes) - min(extremes)) / max(extremes)
            if ratio > 0.05:
                issue("PARALLEL_STRING_VMP_MISMATCH", "error",
                      f"{tracker_id}: strings em paralelo têm Vmp quente diferentes (>5%).", tracker_id)
            elif ratio > 0.01:
                issue("PARALLEL_STRING_VMP_REVIEW", "warning",
                      f"{tracker_id}: strings em paralelo têm Vmp quente diferentes (>1%).", tracker_id)
        mppt_results.append({"id": tracker_id, "string_count": len(strings),
                             "imp_proxy_total_a": round(current, 3),
                             "isc_hot_total_a": round(short, 3),
                             "nameplate_dc_w": round(sum(s["nameplate_dc_w"] for s in strings), 3)})
    if total_dc_w > design.inverter.rated_ac_power_w:
        issue("DC_AC_RATIO", "warning",
              "Potência nominal DC excede AC. Verifique sobrecarregamento permitido e clipping.")
    has_errors = any(i["severity"] == "error" for i in issues)
    has_warnings = any(i["severity"] == "warning" for i in issues)
    return {
        "status": "invalid" if has_errors else "review_required" if has_warnings else "preliminary_pass",
        "electrical_only": True,
        "ready_for_energy_simulation": False,
        "summary": {
            "panel_count": len(panel_ids),
            "connected_panel_count": len(seen & panel_ids),
            "string_count": len(design.strings),
            "nameplate_connected_dc_w": round(total_dc_w, 3),
            "inverter_ac_w": design.inverter.rated_ac_power_w,
            "dc_ac_ratio": round(total_dc_w / design.inverter.rated_ac_power_w, 4),
        },
        "strings": string_results,
        "mppts": mppt_results,
        "issues": issues,
        "assumptions": [
            "nameplate values at STC and linear temperature coefficients",
            "min/max refer to solar CELL temperature, not ambient air temperature",
            "voltage checks at minimum/maximum assumed cell temperatures",
            "MPPT current uses conservative Imp proxy scaled with Isc coefficient",
            "no cable losses, parallel protection, grounding, fusing or code compliance",
            "no irradiance, bypass-diode or mismatch simulation and no DC/AC yield",
        ],
    }
