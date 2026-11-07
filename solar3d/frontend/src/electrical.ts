/** F4 local electrical design. The backend is authoritative for safety checks.
 * The sample values below are ILLUSTRATIVE and are not any real datasheet.
 */
import type { SceneObject } from "./model";

export type ModuleSpec = {
  id: string; manufacturer: string; model: string;
  pmax_w: number; voc_v: number; vmp_v: number;
  isc_a: number; imp_a: number;
  beta_voc_pct_c: number; beta_vmp_pct_c: number;
  alpha_isc_pct_c: number; gamma_pmax_pct_c?: number | null; verified_datasheet: boolean;
};

export type MpptSpec = {
  id: string; min_voltage_v: number; max_voltage_v: number;
  max_input_current_a: number; max_short_circuit_current_a: number;
  max_parallel_strings: number;
};

export type InverterSpec = {
  id: string; manufacturer: string; model: string;
  max_dc_voltage_v: number; rated_ac_power_w: number;
  verified_datasheet: boolean; mppts: MpptSpec[];
};

export type ElectricalString = {
  id: string; mppt_id: string; module_ids: string[];
};

export type ElectricalDesign = {
  module_catalog: ModuleSpec[];
  module_model_ids: Record<string, string>;
  inverter: InverterSpec;
  strings: ElectricalString[];
  min_cell_temp_c: number;
  max_cell_temp_c: number;
};

export type ElectricalIssue = {
  code: string; severity: "error" | "warning"; scope: string; message: string;
};

export type ElectricalResult = {
  status: "invalid" | "review_required" | "preliminary_pass";
  electrical_only: true;
  ready_for_energy_simulation: false;
  summary: {
    panel_count: number; connected_panel_count: number;
    string_count: number; nameplate_connected_dc_w: number;
    inverter_ac_w: number; dc_ac_ratio: number;
  };
  strings: Array<{
    id: string; mppt_id: string; module_model_id: string;
    module_count: number; nameplate_dc_w: number;
    voc_cold_v: number; vmp_hot_v: number; vmp_cold_v: number;
    isc_hot_a: number; imp_proxy_a: number;
  }>;
  mppts: Array<{
    id: string; string_count: number; imp_proxy_total_a: number;
    isc_hot_total_a: number; nameplate_dc_w: number;
  }>;
  issues: ElectricalIssue[];
  assumptions: string[];
};

const demoModule: ModuleSpec = {
  id: "DEMO-550", manufacturer: "EXEMPLO (não real)",
  model: "Módulo 550 W — valores ilustrativos",
  pmax_w: 550, voc_v: 49, vmp_v: 41, isc_a: 14.2, imp_a: 13.42,
  beta_voc_pct_c: -0.28, beta_vmp_pct_c: -0.35, alpha_isc_pct_c: 0.04,
  gamma_pmax_pct_c: -0.30,
  verified_datasheet: false,
};

const demoMppt = (id: string): MpptSpec => ({
  id, min_voltage_v: 100, max_voltage_v: 550,
  max_input_current_a: 20, max_short_circuit_current_a: 25,
  max_parallel_strings: 2,
});

export function defaultElectricalDesign(objects: SceneObject[], wireDemo = false): ElectricalDesign {
  const panels = objects.filter((obj) => obj.kind === "panel").map((obj) => obj.id);
  const module_model_ids = Object.fromEntries(panels.map((id) => [id, demoModule.id]));
  const strings: ElectricalString[] = wireDemo && panels.length === 6
    ? [
        { id: "S1", mppt_id: "MPPT1", module_ids: panels.slice(0, 3) },
        { id: "S2", mppt_id: "MPPT2", module_ids: panels.slice(3, 6) },
      ]
    : [];
  return {
    module_catalog: [{ ...demoModule }],
    module_model_ids,
    inverter: {
      id: "DEMO-INV", manufacturer: "EXEMPLO (não real)",
      model: "Inversor 5 kW — valores ilustrativos",
      max_dc_voltage_v: 600, rated_ac_power_w: 5000,
      verified_datasheet: false,
      mppts: [demoMppt("MPPT1"), demoMppt("MPPT2")],
    },
    strings,
    min_cell_temp_c: 0,
    max_cell_temp_c: 65,
  };
}

export function assignPanelToString(
  design: ElectricalDesign, stringId: string, panelId: string,
  panels: SceneObject[]
): ElectricalDesign {
  if (!panels.some((obj) => obj.kind === "panel" && obj.id === panelId) ||
      !design.strings.some((str) => str.id === stringId)) return design;
  // Toggle if selected string already contains panel; otherwise move it
  // atomically out of every other string before assigning.
  const target = design.strings.find((str) => str.id === stringId)!;
  const wasInTarget = target.module_ids.includes(panelId);
  return {
    ...design,
    strings: design.strings.map((str) => ({
      ...str,
      module_ids: str.id === stringId
        ? wasInTarget ? str.module_ids.filter((id) => id !== panelId)
          : [...str.module_ids.filter((id) => id !== panelId), panelId]
        : str.module_ids.filter((id) => id !== panelId),
    })),
  };
}

export function deleteModuleFromDesign(design: ElectricalDesign, panelId: string): ElectricalDesign {
  const module_model_ids = { ...design.module_model_ids };
  delete module_model_ids[panelId];
  return {
    ...design,
    module_model_ids,
    strings: design.strings.map((str) => ({
      ...str, module_ids: str.module_ids.filter((id) => id !== panelId),
    })),
  };
}

export function registerModule(design: ElectricalDesign, panelId: string): ElectricalDesign {
  return {
    ...design,
    module_model_ids: {
      ...design.module_model_ids,
      [panelId]: design.module_catalog[0]?.id ?? "",
    },
  };
}

const isRecord = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object" && !Array.isArray(v);
const isFiniteNumber = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);
const hasString = (v: unknown) => typeof v === "string" && v.length > 0 && v.length <= 120;
const isPositive = (v: unknown) => isFiniteNumber(v) && v > 0;

function isMppt(v: unknown): v is MpptSpec {
  return isRecord(v) && hasString(v.id) &&
    isPositive(v.min_voltage_v) && isPositive(v.max_voltage_v) &&
    isPositive(v.max_input_current_a) && isPositive(v.max_short_circuit_current_a) &&
    Number.isInteger(v.max_parallel_strings) && (v.max_parallel_strings as number) >= 1;
}

function isModule(v: unknown): v is ModuleSpec {
  return isRecord(v) && hasString(v.id) && hasString(v.manufacturer) &&
    hasString(v.model) && ["pmax_w", "voc_v", "vmp_v", "isc_a", "imp_a"].every((k) => isPositive(v[k])) &&
    ["beta_voc_pct_c", "beta_vmp_pct_c", "alpha_isc_pct_c"].every((k) => isFiniteNumber(v[k])) &&
    (v.gamma_pmax_pct_c === undefined || v.gamma_pmax_pct_c === null ||
      isFiniteNumber(v.gamma_pmax_pct_c)) &&
    typeof v.verified_datasheet === "boolean";
}

function isInverter(v: unknown): v is InverterSpec {
  return isRecord(v) && hasString(v.id) && hasString(v.manufacturer) &&
    hasString(v.model) && isPositive(v.max_dc_voltage_v) && isPositive(v.rated_ac_power_w) &&
    typeof v.verified_datasheet === "boolean" && Array.isArray(v.mppts) &&
    v.mppts.length >= 1 && v.mppts.length <= 8 && v.mppts.every(isMppt);
}

export function parseElectricalDesign(v: unknown): ElectricalDesign {
  if (!isRecord(v) || !Array.isArray(v.module_catalog) ||
      v.module_catalog.length < 1 || v.module_catalog.length > 50 ||
      !v.module_catalog.every(isModule) || !isInverter(v.inverter) ||
      !isRecord(v.module_model_ids) || !Object.values(v.module_model_ids).every(hasString) ||
      !Array.isArray(v.strings) || v.strings.length > 64 ||
      !v.strings.every((str) => isRecord(str) && hasString(str.id) &&
        hasString(str.mppt_id) && Array.isArray(str.module_ids) &&
        str.module_ids.length <= 100 && str.module_ids.every(hasString)) ||
      !isFiniteNumber(v.min_cell_temp_c) || !isFiniteNumber(v.max_cell_temp_c) ||
      v.min_cell_temp_c >= v.max_cell_temp_c) {
    throw new Error("Configuração elétrica inválida no projeto.");
  }
  return v as ElectricalDesign;
}
