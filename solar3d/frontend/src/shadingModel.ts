import type { SolarSample } from "./model";

export type ShadingFrame = {
  blocked_fraction: number | null;
  blocked_cells: number[] | null;
};

export type ModuleShading = {
  id: string;
  name: string;
  direct_eligible_intervals: number;
  shaded_direct_intervals: number;
  mean_blocked_fraction_direct_eligible: number | null;
  frames: ShadingFrame[];
};

export type ShadingDayResult = {
  geometry_only: true;
  schema_version: number;
  model: string;
  quantity: string;
  timezone: string;
  local_date: string;
  sampling: { rows: number; columns: number; cells_per_module: number };
  solar_samples_utc: string[];
  modules: ModuleShading[];
  limitations: string[];
};

/** Reject stale scene/solar results instead of showing values at the wrong time. */
export function activeShading(
  result: ShadingDayResult | null,
  sample: SolarSample | null,
  sampleIndex: number,
  panelId: string
): ShadingFrame | null {
  if (!result || !sample ||
      result.solar_samples_utc[sampleIndex] !== sample.utc_time) return null;
  return result.modules.find((entry) => entry.id === panelId)?.frames[sampleIndex] ?? null;
}
